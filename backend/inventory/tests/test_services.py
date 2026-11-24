from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounting import services as accounting
from accounting.models import JournalEntry, Partner
from inventory import services
from inventory.models import (
    InventoryLock, Product, StockLayer, StockMove, StockReceipt, Unit, Warehouse,
)

pytestmark = pytest.mark.django_db
D = Decimal


def qty(product, warehouse):
    return services.available_qty(product.pk, warehouse.pk)


def transfer(company, user, frm, to, product, amount, date="2026-11-05"):
    return services.create_transfer(
        company=company, user=user, date=date, from_warehouse=frm, to_warehouse=to,
        lines=[services.TransferLineInput(product, D(amount))],
    )


# ---------------------------------------------------------------- receipts
def test_receipt_builds_layers_moves_and_draft_entry(company, receive, widget, main_wh, supplier):
    receipt = receive(widget, "10", "2.5")
    assert receipt.number == "RC-00001"
    assert qty(widget, main_wh) == D("10")

    move = StockMove.objects.get()
    assert (move.quantity, move.value, move.doc_type) == (D("10"), D("25.00"), "receipt")

    entry = receipt.journal_entry
    assert entry.status == JournalEntry.Status.DRAFT
    lines = {(l.account.code, l.debit, l.credit) for l in entry.lines.select_related("account")}
    assert lines == {("105", D("25"), D("0")), ("210", D("0"), D("25"))}
    assert entry.lines.get(account__code="210").partner == supplier


def test_receipt_with_zero_cost_has_no_entry(receive, widget):
    assert receive(widget, "5", "0").journal_entry is None


def test_receipt_validation(company, chief, main_wh, supplier, widget, other_company, customer):
    def make(**kw):
        args = dict(
            company=company, user=chief, date="2026-11-01", warehouse=main_wh, supplier=supplier,
            lines=[services.ReceiptLineInput(widget, D("1"), D("1"))],
        )
        args.update(kw)
        return services.create_receipt(**args)

    with pytest.raises(ValidationError):
        make(lines=[])
    with pytest.raises(ValidationError):
        make(supplier=customer)  # a customer-only partner
    with pytest.raises(ValidationError):
        make(lines=[services.ReceiptLineInput(widget, D("0"), D("1"))])
    with pytest.raises(ValidationError):
        make(lines=[services.ReceiptLineInput(widget, D("1.0005"), D("1"))])
    with pytest.raises(ValidationError):
        make(lines=[services.ReceiptLineInput(widget, D("1"), D("-1"))])
    foreign_unit = Unit.objects.create(company=other_company, name="X")
    foreign = Product.objects.create(company=other_company, code="F", name="F", unit=foreign_unit)
    with pytest.raises(ValidationError):
        make(lines=[services.ReceiptLineInput(foreign, D("1"), D("1"))])
    inactive = Warehouse.objects.create(company=company, code="OLD", name="Old", is_active=False)
    with pytest.raises(ValidationError):
        make(warehouse=inactive)
    assert StockReceipt.objects.count() == 0 and StockLayer.objects.count() == 0


def test_missing_inventory_accounts_roll_back(company, chief, main_wh, supplier, widget):
    from accounting.models import Account

    Account.objects.filter(company=company, code="210").delete()
    with pytest.raises(ValidationError):
        services.create_receipt(
            company=company, user=chief, date="2026-11-01", warehouse=main_wh, supplier=supplier,
            lines=[services.ReceiptLineInput(widget, D("1"), D("1"))],
        )
    assert StockReceipt.objects.count() == 0


def test_update_receipt_rebuilds_everything(company, receive, widget, gadget, main_wh, supplier):
    receipt = receive(widget, "10", "2")
    entry_id = receipt.journal_entry_id
    services.update_receipt(
        receipt=receipt, date="2026-11-02", warehouse=main_wh, supplier=supplier,
        lines=[services.ReceiptLineInput(gadget, D("4"), D("3"))],
    )
    assert qty(widget, main_wh) == 0 and qty(gadget, main_wh) == D("4")
    assert StockMove.objects.count() == 1
    receipt.refresh_from_db()
    assert receipt.journal_entry_id == entry_id  # same entry, new lines
    assert sum(l.debit for l in receipt.journal_entry.lines.all()) == D("12")


def test_update_to_zero_cost_removes_the_entry(company, receive, widget, main_wh, supplier):
    receipt = receive(widget, "10", "2")
    services.update_receipt(
        receipt=receipt, date="2026-11-02", warehouse=main_wh, supplier=supplier,
        lines=[services.ReceiptLineInput(widget, D("10"), D("0"))],
    )
    receipt.refresh_from_db()
    assert receipt.journal_entry is None
    assert not JournalEntry.objects.exists()


def test_posted_entry_locks_the_receipt(company, receive, widget, main_wh, supplier, chief):
    receipt = receive(widget, "10", "2")
    accounting.post_entry(entry=receipt.journal_entry, user=chief)
    receipt.refresh_from_db()
    assert services.receipt_lock_reason(receipt)
    with pytest.raises(ValidationError):
        services.delete_receipt(receipt=receipt)
    with pytest.raises(ValidationError):
        services.update_receipt(
            receipt=receipt, date="2026-11-02", warehouse=main_wh, supplier=supplier,
            lines=[services.ReceiptLineInput(widget, D("1"), D("1"))],
        )
    assert qty(widget, main_wh) == D("10")


def test_delete_receipt_removes_stock_and_draft_entry(receive, widget, main_wh):
    receipt = receive(widget, "10", "2")
    services.delete_receipt(receipt=receipt)
    assert qty(widget, main_wh) == 0
    assert not StockMove.objects.exists() and not JournalEntry.objects.exists()


def test_used_stock_locks_the_receipt(company, chief, receive, widget, main_wh, second_wh):
    receipt = receive(widget, "10", "2")
    transfer(company, chief, main_wh, second_wh, widget, "3")
    receipt.refresh_from_db()
    assert services.receipt_lock_reason(receipt)
    with pytest.raises(ValidationError):
        services.delete_receipt(receipt=receipt)


# ----------------------------------------------------------------- FIFO / transfers
def test_transfer_consumes_oldest_layers_first_and_keeps_costs(
    company, chief, receive, widget, main_wh, second_wh
):
    receive(widget, "10", "1", date="2026-11-01")  # cheap, older
    receive(widget, "10", "5", date="2026-11-02")
    t = transfer(company, chief, main_wh, second_wh, widget, "15")

    assert qty(widget, main_wh) == D("5") and qty(widget, second_wh) == D("15")
    out = StockMove.objects.get(doc_type="transfer_out")
    inn = StockMove.objects.get(doc_type="transfer_in")
    assert out.value == D("-35.00") and inn.value == D("35.00")  # 10*1 + 5*5
    remaining = StockLayer.objects.get(warehouse=main_wh, qty_remaining__gt=0)
    assert remaining.unit_cost == D("5") and remaining.qty_remaining == D("5")
    costs = sorted(
        (l.unit_cost, l.qty_remaining) for l in StockLayer.objects.filter(warehouse=second_wh)
    )
    assert costs == [(D("1"), D("10")), (D("5"), D("5"))]
    assert t.number.startswith("TR-")


def test_destination_keeps_fifo_order(company, chief, receive, widget, main_wh, second_wh):
    receive(widget, "5", "1", date="2026-11-01")  # first in
    receive(widget, "5", "9", date="2026-11-02", warehouse=second_wh)
    transfer(company, chief, main_wh, second_wh, widget, "5")
    # issue from the second warehouse: the transferred cheap layer (older key) goes first
    move = StockMove.objects.create(
        company=company, product=widget, warehouse=second_wh, date="2026-11-06",
        doc_type="transfer_out", doc_id=0, quantity=D("-5"), value=D("0"),
    )
    total = services.consume_fifo(company, widget.pk, second_wh.pk, D("5"), move)
    assert total == D("5.00")  # the cost-1 layer came first


def test_transfer_validation(company, chief, receive, widget, main_wh, second_wh):
    receive(widget, "5", "1")
    with pytest.raises(ValidationError):
        transfer(company, chief, main_wh, main_wh, widget, "1")
    with pytest.raises(ValidationError):
        transfer(company, chief, main_wh, second_wh, widget, "6")  # insufficient
    with pytest.raises(ValidationError):
        services.create_transfer(
            company=company, user=chief, date="2026-11-05", from_warehouse=main_wh,
            to_warehouse=second_wh, lines=[],
        )
    assert qty(widget, main_wh) == D("5")  # the failed one rolled back completely
    assert not StockMove.objects.filter(doc_type__startswith="transfer").exists()


def test_delete_transfer_restores_stock(company, chief, receive, widget, main_wh, second_wh):
    receive(widget, "10", "2")
    t = transfer(company, chief, main_wh, second_wh, widget, "4")
    services.delete_transfer(transfer=t)
    assert qty(widget, main_wh) == D("10") and qty(widget, second_wh) == 0
    assert not StockMove.objects.filter(doc_type__startswith="transfer").exists()


def test_cannot_delete_transfer_whose_stock_moved_on(
    company, chief, receive, widget, main_wh, second_wh
):
    receive(widget, "10", "2")
    t = transfer(company, chief, main_wh, second_wh, widget, "4")
    transfer(company, chief, second_wh, main_wh, widget, "1")
    t.refresh_from_db()
    assert services.transfer_lock_reason(t)
    with pytest.raises(ValidationError):
        services.delete_transfer(transfer=t)


# ------------------------------------------------------------------ counts
def test_stock_count_records_book_vs_counted(company, chief, receive, widget, gadget, main_wh):
    receive(widget, "10", "2")
    count = services.create_count(
        company=company, user=chief, warehouse=main_wh,
        quantities=[(widget, D("8")), (gadget, D("1"))],
    )
    lines = {l.product.code: (l.book_qty, l.counted_qty, l.difference) for l in count.lines.all()}
    assert lines == {"W1": (D("10"), D("8"), D("-2")), "G1": (D("0"), D("1"), D("1"))}
    assert count.number.startswith("CNT-")


def test_stock_count_validation(company, chief, widget, main_wh):
    with pytest.raises(ValidationError):
        services.create_count(company=company, user=chief, warehouse=main_wh, quantities=[])
    with pytest.raises(ValidationError):
        services.create_count(
            company=company, user=chief, warehouse=main_wh,
            quantities=[(widget, D("1")), (widget, D("2"))],
        )
    with pytest.raises(ValidationError):
        services.create_count(
            company=company, user=chief, warehouse=main_wh, quantities=[(widget, D("-1"))]
        )


# ----------------------------------------------------------------- reports
def test_stock_levels_and_ledger_comparison(company, chief, receive, widget, gadget, main_wh):
    receipt = receive(widget, "10", "2")
    receive(gadget, "3", "10")
    report = services.stock_levels(company)
    assert report["stock_total"] == D("50.00")
    assert [(r["product"].code, r["qty"], r["value"], r["avg"]) for r in report["rows"]] == [
        ("G1", D("3"), D("30.00"), D("10")),
        ("W1", D("10"), D("20.00"), D("2")),
    ]
    assert report["ledger"]["all"] == D("50.00") and report["ledger"]["difference"] == 0
    assert report["ledger"]["posted"] == 0

    accounting.post_entry(entry=receipt.journal_entry, user=chief)
    assert services.stock_levels(company)["ledger"]["posted"] == D("20.00")
    assert [r["product"].code for r in services.stock_levels(company, q="widg")["rows"]] == ["W1"]


def test_item_card_running_balance_and_opening(company, chief, receive, widget, main_wh, second_wh):
    receive(widget, "10", "2", date="2026-11-01")
    transfer(company, chief, main_wh, second_wh, widget, "4", date="2026-11-05")
    card = services.item_card(company, widget, main_wh)
    assert [(r["move"].quantity, r["run_q"], r["run_v"]) for r in card["rows"]] == [
        (D("10"), D("10"), D("20.00")),
        (D("-4"), D("6"), D("12.00")),
    ]
    later = services.item_card(company, widget, main_wh, date_from="2026-11-03")
    assert (later["opening_qty"], later["opening_value"]) == (D("10"), D("20.00"))
    assert len(later["rows"]) == 1


def test_reports_are_company_scoped(company, other_company, receive, widget):
    receive(widget, "10", "2")
    assert services.stock_levels(other_company)["rows"] == []
    assert services.stock_levels(other_company)["stock_total"] == 0


# -------------------------------------------------------------------- lock
def test_lock_single_user_and_expiry(company, chief, accountant):
    assert services.acquire_lock(company, chief) is None
    assert services.acquire_lock(company, chief) is None  # the holder keeps it
    holder = services.acquire_lock(company, accountant)
    assert holder is not None and holder.user == chief
    assert services.lock_minutes_left(holder) >= 1

    InventoryLock.objects.update(
        last_activity=InventoryLock.objects.get().last_activity
        - services.timedelta(minutes=services.LOCK_MINUTES + 1)
    )
    assert services.active_lock(company) is None
    assert services.acquire_lock(company, accountant) is None  # idle holder lost it


def test_release_only_own_lock(company, chief, accountant):
    services.acquire_lock(company, chief)
    services.release_lock(company, accountant)
    assert services.active_lock(company) is not None
    services.release_lock(company, chief)
    assert services.active_lock(company) is None


def test_locks_are_per_company(company, other_company, chief, make_user):
    other_user = make_user("zed", other_company, "chief_accountant")
    assert services.acquire_lock(company, chief) is None
    assert services.acquire_lock(other_company, other_user) is None


# ----------------------------------------------------- numbering per company
def test_document_numbers_are_counted_per_company(company, other_company, chief, make_user, widget, receive, supplier):
    from accounting.models import Partner
    from inventory.models import Product, Unit, Warehouse

    first = receive(widget, "1", "1")
    second = receive(widget, "1", "1")
    assert (first.number, second.number) == ("RC-00001", "RC-00002")

    other_user = make_user("zed", other_company, "chief_accountant")
    unit = Unit.objects.create(company=other_company, name="Box")
    product = Product.objects.create(company=other_company, code="W", name="W", unit=unit)
    wh = Warehouse.objects.create(company=other_company, code="M", name="Main")
    sup = Partner.objects.create(company=other_company, name="S", kind="supplier")
    theirs = services.create_receipt(
        company=other_company, user=other_user, date="2026-11-01", warehouse=wh, supplier=sup,
        lines=[services.ReceiptLineInput(product, D("1"), D("1"))],
    )
    assert theirs.number == "RC-00001"  # the other company starts at 1


def test_failed_document_does_not_burn_a_number(company, chief, main_wh, supplier, widget, receive):
    with pytest.raises(ValidationError):
        services.create_receipt(
            company=company, user=chief, date="2026-11-01", warehouse=main_wh, supplier=supplier, lines=[],
        )
    assert receive(widget, "1", "1").number == "RC-00001"
