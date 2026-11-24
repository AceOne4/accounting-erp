"""Inventory rules: FIFO layers, goods receipts (with their draft journal entry),
transfers, stock counts, reports and the single-user lock. The API only calls these."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from accounting import services as accounting
from accounting.models import Account, JournalEntry, JournalLine, Partner
from accounting.services import LineInput

from .models import (
    InventoryLock,
    LayerConsumption,
    Product,
    StockCount,
    StockCountLine,
    StockLayer,
    StockMove,
    StockReceipt,
    StockReceiptLine,
    StockTransfer,
    StockTransferLine,
    Warehouse,
)

INVENTORY = "105"  # inventory
GRNI = "210"  # goods received not invoiced
LOCK_MINUTES = 15
CENT = Decimal("0.01")
ZERO = Decimal("0")
QTY = Decimal("0.001")
COST = Decimal("0.0001")


def money(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ReceiptLineInput:
    product: Product
    quantity: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class TransferLineInput:
    product: Product
    quantity: Decimal


# ------------------------------------------------------------- validation
def _check_qty(value, number, minimum=QTY):
    if value != value.quantize(QTY) or value < minimum:
        raise ValidationError(
            _("Line %(n)s: the quantity must be at least %(min)s with up to 3 decimal places")
            % {"n": number, "min": minimum}
        )


def _check_product(company, product, number):
    if product.company_id != company.pk or not product.is_active:
        raise ValidationError(_("Line %(n)s: select an active product") % {"n": number})


def _check_warehouse(company, warehouse):
    if warehouse.company_id != company.pk or not warehouse.is_active:
        raise ValidationError(_("Select an active warehouse"))


def available_qty(product_id, warehouse_id):
    total = StockLayer.objects.filter(product_id=product_id, warehouse_id=warehouse_id).aggregate(
        q=Sum("qty_remaining")
    )["q"]
    return total or ZERO


def ensure_accounts(company):
    found = set(
        Account.objects.filter(company=company, code__in=[INVENTORY, GRNI]).values_list(
            "code", flat=True
        )
    )
    if len(found) != 2:
        raise ValidationError(_("The inventory accounts (105, 210) are missing for this company"))


def consume_fifo(company, product_id, warehouse_id, qty, move):
    """Take qty from the oldest layers. Returns the cost taken."""
    layers = (
        StockLayer.objects.select_for_update()
        .filter(company=company, product_id=product_id, warehouse_id=warehouse_id, qty_remaining__gt=0)
        .order_by("fifo_key", "id")
    )
    need = qty
    total = ZERO
    for layer in layers:
        if need <= 0:
            break
        take = min(layer.qty_remaining, need)
        layer.qty_remaining -= take
        layer.save(update_fields=["qty_remaining"])
        LayerConsumption.objects.create(
            move=move, layer=layer, quantity=take, unit_cost=layer.unit_cost
        )
        total += take * layer.unit_cost
        need -= take
    if need > 0:
        raise ValidationError(_("Insufficient stock"))
    return money(total)


# --------------------------------------------------------------- receipts
def receipt_lock_reason(receipt):
    """Why a receipt cannot be edited or deleted ('' when it can)."""
    if receipt.pk is None:
        return ""
    entry = receipt.journal_entry
    if entry and entry.status == JournalEntry.Status.POSTED:
        return _("Its journal entry is already posted")
    used = (
        StockLayer.objects.filter(receipt_line__receipt=receipt)
        .exclude(qty_remaining=F("qty_in"))
        .exists()
    )
    if used:
        return _("Part of this receipt was already issued or transferred")
    return ""


def _validate_receipt(company, warehouse, supplier, lines):
    _check_warehouse(company, warehouse)
    if (
        supplier.company_id != company.pk
        or not supplier.is_active
        or supplier.kind not in (Partner.Kind.SUPPLIER, Partner.Kind.BOTH)
    ):
        raise ValidationError(_("Select an active supplier of this company"))
    if not lines:
        raise ValidationError(_("Add at least one line"))
    for number, line in enumerate(lines, start=1):
        _check_product(company, line.product, number)
        _check_qty(line.quantity, number)
        if line.unit_cost < 0 or line.unit_cost != line.unit_cost.quantize(COST):
            raise ValidationError(
                _("Line %(n)s: the unit cost cannot be negative and has up to 4 decimal places")
                % {"n": number}
            )


def _rebuild_receipt(receipt, lines):
    """Replace lines, layers and moves, then re-sync the draft entry."""
    StockMove.objects.filter(
        company=receipt.company, doc_type=StockMove.DocType.RECEIPT, doc_id=receipt.pk
    ).delete()
    StockLayer.objects.filter(receipt_line__receipt=receipt).delete()
    receipt.lines.all().delete()

    total = ZERO
    for line in lines:
        saved = StockReceiptLine.objects.create(
            receipt=receipt, product=line.product, quantity=line.quantity, unit_cost=line.unit_cost
        )
        layer = StockLayer.objects.create(
            company=receipt.company, product=line.product, warehouse=receipt.warehouse,
            unit_cost=line.unit_cost, qty_in=line.quantity, qty_remaining=line.quantity,
            doc_date=receipt.date, receipt_line=saved,
        )
        StockLayer.objects.filter(pk=layer.pk).update(fifo_key=layer.pk)
        value = saved.line_total()
        StockMove.objects.create(
            company=receipt.company, product=line.product, warehouse=receipt.warehouse,
            date=receipt.date, doc_type=StockMove.DocType.RECEIPT, doc_id=receipt.pk,
            doc_number=receipt.number, quantity=line.quantity, value=value,
        )
        total += value
    _sync_receipt_entry(receipt, total)


def _sync_receipt_entry(receipt, total):
    company = receipt.company
    ensure_accounts(company)
    inventory = Account.objects.get(company=company, code=INVENTORY)
    grni = Account.objects.get(company=company, code=GRNI)
    entry = receipt.journal_entry

    if total <= 0:
        if entry:
            StockReceipt.objects.filter(pk=receipt.pk).update(journal_entry=None)
            receipt.journal_entry = None
            accounting.delete_entry(entry=entry)
        return

    description = ("%s %s - %s" % (_("Goods receipt"), receipt.number, receipt.supplier.name))[:500]
    lines = [
        LineInput(inventory, debit=total, memo=receipt.number),
        LineInput(grni, credit=total, partner=receipt.supplier, memo=receipt.number),
    ]
    if entry is None:
        entry = accounting.create_entry(
            company=company, user=receipt.created_by, date=receipt.date,
            description=description, lines=lines,
        )
        StockReceipt.objects.filter(pk=receipt.pk).update(journal_entry=entry)
        receipt.journal_entry = entry
    else:
        accounting.update_entry(entry=entry, date=receipt.date, description=description, lines=lines)


@transaction.atomic
def create_receipt(
    *, company, user, date, warehouse, supplier, lines, supplier_invoice="", notes=""
):
    _validate_receipt(company, warehouse, supplier, lines)
    ensure_accounts(company)
    receipt = StockReceipt.objects.create(
        company=company, date=date, warehouse=warehouse, supplier=supplier,
        supplier_invoice=supplier_invoice, notes=notes, created_by=user,
    )
    _rebuild_receipt(receipt, lines)
    return receipt


@transaction.atomic
def update_receipt(
    *, receipt, date, warehouse, supplier, lines, supplier_invoice="", notes=""
):
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk, company=receipt.company)
    reason = receipt_lock_reason(receipt)
    if reason:
        raise ValidationError(reason)
    _validate_receipt(receipt.company, warehouse, supplier, lines)
    receipt.date, receipt.warehouse, receipt.supplier = date, warehouse, supplier
    receipt.supplier_invoice, receipt.notes = supplier_invoice, notes
    receipt.save()
    _rebuild_receipt(receipt, lines)
    return receipt


@transaction.atomic
def delete_receipt(*, receipt):
    receipt = StockReceipt.objects.select_for_update().get(pk=receipt.pk, company=receipt.company)
    reason = receipt_lock_reason(receipt)
    if reason:
        raise ValidationError(reason)
    entry = receipt.journal_entry
    StockMove.objects.filter(
        company=receipt.company, doc_type=StockMove.DocType.RECEIPT, doc_id=receipt.pk
    ).delete()
    StockLayer.objects.filter(receipt_line__receipt=receipt).delete()
    receipt.delete()
    if entry:
        accounting.delete_entry(entry=entry)


# -------------------------------------------------------------- transfers
def transfer_lock_reason(transfer):
    if transfer.pk is None:
        return ""
    used = (
        StockLayer.objects.filter(transfer_line__transfer=transfer)
        .exclude(qty_remaining=F("qty_in"))
        .exists()
    )
    if used:
        return _("Part of this transfer was already issued or transferred")
    return ""


@transaction.atomic
def create_transfer(*, company, user, date, from_warehouse, to_warehouse, lines, notes=""):
    _check_warehouse(company, from_warehouse)
    _check_warehouse(company, to_warehouse)
    if from_warehouse.pk == to_warehouse.pk:
        raise ValidationError(_("The source and destination warehouses must be different"))
    if not lines:
        raise ValidationError(_("Add at least one line"))
    for number, line in enumerate(lines, start=1):
        _check_product(company, line.product, number)
        _check_qty(line.quantity, number)

    transfer = StockTransfer.objects.create(
        company=company, date=date, from_warehouse=from_warehouse, to_warehouse=to_warehouse,
        notes=notes, created_by=user,
    )
    for line in lines:
        saved = StockTransferLine.objects.create(
            transfer=transfer, product=line.product, quantity=line.quantity
        )
        out_move = StockMove.objects.create(
            company=company, product=line.product, warehouse=from_warehouse, date=date,
            doc_type=StockMove.DocType.TRANSFER_OUT, doc_id=transfer.pk,
            doc_number=transfer.number, quantity=-line.quantity, value=ZERO,
        )
        total = consume_fifo(company, line.product.pk, from_warehouse.pk, line.quantity, out_move)
        StockMove.objects.filter(pk=out_move.pk).update(value=-total)
        StockMove.objects.create(
            company=company, product=line.product, warehouse=to_warehouse, date=date,
            doc_type=StockMove.DocType.TRANSFER_IN, doc_id=transfer.pk,
            doc_number=transfer.number, quantity=line.quantity, value=total,
        )
        # the destination receives the same layers, with the same costs and order
        for c in out_move.consumptions.select_related("layer"):
            StockLayer.objects.create(
                company=company, product=line.product, warehouse=to_warehouse,
                unit_cost=c.unit_cost, qty_in=c.quantity, qty_remaining=c.quantity,
                doc_date=c.layer.doc_date, fifo_key=c.layer.fifo_key, transfer_line=saved,
            )
    return transfer


@transaction.atomic
def delete_transfer(*, transfer):
    transfer = StockTransfer.objects.select_for_update().get(
        pk=transfer.pk, company=transfer.company
    )
    reason = transfer_lock_reason(transfer)
    if reason:
        raise ValidationError(reason)
    StockLayer.objects.filter(transfer_line__transfer=transfer).delete()
    consumptions = LayerConsumption.objects.filter(
        move__company=transfer.company,
        move__doc_type=StockMove.DocType.TRANSFER_OUT,
        move__doc_id=transfer.pk,
    ).select_related("layer")
    for c in consumptions:
        layer = c.layer
        layer.qty_remaining += c.quantity
        layer.save(update_fields=["qty_remaining"])
    StockMove.objects.filter(
        company=transfer.company,
        doc_type__in=[StockMove.DocType.TRANSFER_OUT, StockMove.DocType.TRANSFER_IN],
        doc_id=transfer.pk,
    ).delete()
    transfer.delete()


# ------------------------------------------------------------ stock counts
@transaction.atomic
def create_count(*, company, user, warehouse, quantities, notes=""):
    """quantities: list of (product, counted_qty). Records book vs counted; posts nothing."""
    _check_warehouse(company, warehouse)
    if not quantities:
        raise ValidationError(_("Enter at least one counted quantity"))
    seen = set()
    for number, (product, qty) in enumerate(quantities, start=1):
        _check_product(company, product, number)
        _check_qty(qty, number, minimum=ZERO)
        if product.pk in seen:
            raise ValidationError(_("Line %(n)s: the product is repeated") % {"n": number})
        seen.add(product.pk)

    count = StockCount.objects.create(
        company=company, warehouse=warehouse, counted_by=user, notes=notes
    )
    for product, qty in quantities:
        book = available_qty(product.pk, warehouse.pk)
        StockCountLine.objects.create(
            count=count, product=product, book_qty=book, counted_qty=qty, difference=qty - book
        )
    return count


# ---------------------------------------------------------------- reports
def _gl_net(company, account, posted_only):
    lines = JournalLine.objects.filter(entry__company=company, account=account)
    if posted_only:
        lines = lines.filter(entry__status=JournalEntry.Status.POSTED)
    total = lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    return (total["d"] or ZERO) - (total["c"] or ZERO)


def stock_levels(company, warehouse=None, q=""):
    """Quantity, value and average cost per product and warehouse, plus the comparison
    of the whole stock value with the inventory account (105) in the ledger."""
    all_layers = StockLayer.objects.filter(company=company, qty_remaining__gt=0)
    stock_total = money(sum((l.qty_remaining * l.unit_cost for l in all_layers), ZERO))

    layers = all_layers
    if warehouse:
        layers = layers.filter(warehouse=warehouse)
    if q:
        layers = layers.filter(
            Q(product__code__icontains=q) | Q(product__name__icontains=q)
            | Q(product__name_en__icontains=q)
        )

    grouped = {}
    for layer in layers.select_related("product__unit", "warehouse"):
        row = grouped.setdefault(
            (layer.product_id, layer.warehouse_id),
            {"product": layer.product, "warehouse": layer.warehouse, "qty": ZERO, "value": ZERO},
        )
        row["qty"] += layer.qty_remaining
        row["value"] += layer.qty_remaining * layer.unit_cost

    rows = sorted(grouped.values(), key=lambda r: (r["product"].code, r["warehouse"].code))
    for row in rows:
        row["value"] = money(row["value"])
        row["avg"] = (row["value"] / row["qty"]).quantize(COST, rounding=ROUND_HALF_UP) if row["qty"] else ZERO
    total_value = sum((r["value"] for r in rows), ZERO)

    ledger = None
    inventory = Account.objects.filter(company=company, code=INVENTORY).first()
    if inventory:
        ledger_all = _gl_net(company, inventory, False)
        ledger = {
            "posted": _gl_net(company, inventory, True),
            "all": ledger_all,
            "difference": stock_total - ledger_all,
        }
    return {"rows": rows, "total_value": total_value, "stock_total": stock_total, "ledger": ledger}


def item_card(company, product, warehouse=None, date_from=None, date_to=None):
    moves = StockMove.objects.filter(company=company, product=product)
    if warehouse:
        moves = moves.filter(warehouse=warehouse)
    open_q = open_v = ZERO
    if date_from:
        before = moves.filter(date__lt=date_from).aggregate(q=Sum("quantity"), v=Sum("value"))
        open_q, open_v = before["q"] or ZERO, before["v"] or ZERO
        moves = moves.filter(date__gte=date_from)
    if date_to:
        moves = moves.filter(date__lte=date_to)

    rows, run_q, run_v = [], open_q, open_v
    for move in moves.select_related("warehouse").order_by("date", "id"):
        run_q += move.quantity
        run_v += move.value
        rows.append({"move": move, "run_q": run_q, "run_v": run_v})
    return {"opening_qty": open_q, "opening_value": open_v, "rows": rows}


# ------------------------------------------------------------------- lock
@transaction.atomic
def acquire_lock(company, user):
    """Returns None when `user` now holds the company's lock, else the lock row
    (held by somebody else). Every call by the holder refreshes the idle timer."""
    lock, _created = InventoryLock.objects.select_for_update().get_or_create(company=company)
    now = timezone.now()
    expired = lock.last_activity is None or now - lock.last_activity > timedelta(minutes=LOCK_MINUTES)
    if lock.user_id in (None, user.pk) or expired:
        lock.user = user
        lock.last_activity = now
        lock.save()
        return None
    return lock


def release_lock(company, user=None):
    locks = InventoryLock.objects.filter(company=company)
    if user is not None:
        locks = locks.filter(user=user)
    locks.update(user=None, last_activity=None)


def lock_minutes_left(lock):
    if lock.last_activity is None:
        return 0
    left = timedelta(minutes=LOCK_MINUTES) - (timezone.now() - lock.last_activity)
    return max(1, int(left.total_seconds() // 60) + 1)


def active_lock(company):
    """The lock row while somebody holds it (not expired), else None."""
    lock = InventoryLock.objects.filter(company=company).select_related("user").first()
    if lock is None or lock.user_id is None or lock.last_activity is None:
        return None
    if timezone.now() - lock.last_activity > timedelta(minutes=LOCK_MINUTES):
        return None
    return lock
