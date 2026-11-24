"""Treasury rules: vouchers (journal entries between the boxes, bank, customers and
suppliers) and cash counts. All amounts are Decimal; the API never sends floats."""
from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext as _

from accounting import services as accounting
from accounting.models import Account, JournalEntry, JournalLine, Partner
from accounting.services import LineInput

from .models import CashCount

EXPENSES_BOX = "1011"
COLLECTIONS_BOX = "1012"
BANK = "103"
CUSTOMERS = "102"
SUPPLIERS = "201"
CASH_DIFF = "510"
REQUIRED_CODES = [EXPENSES_BOX, COLLECTIONS_BOX, BANK, CUSTOMERS, SUPPLIERS, CASH_DIFF]

# Egyptian pound banknotes and coins. Change for another currency.
DENOMINATIONS = [Decimal(x) for x in ("200", "100", "50", "20", "10", "5", "1", "0.5", "0.25")]

ZERO = Decimal("0")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Kind:
    debit: str | None  # None: the caller picks an expense account
    credit: str
    partner: str | None = None  # "customer" / "supplier" when a partner is required

    @property
    def needs_account(self):
        return self.debit is None


KINDS = {
    "collect": Kind(COLLECTIONS_BOX, CUSTOMERS, "customer"),
    "refund": Kind(CUSTOMERS, COLLECTIONS_BOX, "customer"),
    "deposit": Kind(BANK, COLLECTIONS_BOX),
    "fund": Kind(EXPENSES_BOX, BANK),
    "expense": Kind(None, EXPENSES_BOX),
    "supplier": Kind(SUPPLIERS, EXPENSES_BOX, "supplier"),
}


def treasury_accounts(company):
    found = {a.code: a for a in Account.objects.filter(company=company, code__in=REQUIRED_CODES)}
    if len(found) != len(REQUIRED_CODES):
        missing = ", ".join(c for c in REQUIRED_CODES if c not in found)
        raise ValidationError(
            _("The treasury accounts are missing for this company: %(codes)s") % {"codes": missing}
        )
    return found


def _net(lines):
    total = lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    return (total["d"] or ZERO) - (total["c"] or ZERO)


def box_figures(company, account):
    """Posted, pending (draft) and book balance of one account."""
    lines = JournalLine.objects.filter(entry__company=company, account=account)
    posted = _net(lines.filter(entry__status=JournalEntry.Status.POSTED))
    pending = _net(lines.exclude(entry__status=JournalEntry.Status.POSTED))
    return {"account": account, "posted": posted, "pending": pending, "book": posted + pending}


def _money(value, field):
    try:
        amount = Decimal(value)
    except Exception:
        raise ValidationError({field: _("Enter a valid amount")})
    if not amount.is_finite() or amount != amount.quantize(CENT) or amount < CENT:
        raise ValidationError({field: _("The amount must be at least 0.01 with two decimal places")})
    return amount


def _description(kind, partner, account):
    texts = {
        "collect": _("Collection from %(partner)s"),
        "refund": _("Refund to %(partner)s"),
        "deposit": _("Deposit of collections to the bank"),
        "fund": _("Check withdrawal to fund the expenses box"),
        "expense": _("Expense: %(account)s"),
        "supplier": _("Payment to supplier %(partner)s"),
    }
    return texts[kind] % {
        "partner": partner.name if partner else "",
        "account": account.display_name if account else "",
    }


def create_voucher(
    *, company, user, kind, date, amount, partner=None, expense_account=None,
    reference="", note="", post_now=False,
):
    """Create the draft entry for a treasury operation, optionally posting it.

    Returns (entry, posted, post_error). A posting failure leaves the draft in place.
    The caller must have checked that the user may post before passing post_now.
    """
    config = KINDS.get(kind)
    if config is None:
        raise ValidationError({"kind": _("Unknown operation")})
    amount = _money(amount, "amount")
    accounts = treasury_accounts(company)

    if config.partner:
        if partner is None:
            raise ValidationError(
                {"partner": _("You must select the customer / supplier for this operation")}
            )
        if partner.company_id != company.pk or not partner.is_active:
            raise ValidationError({"partner": _("Select an active customer/supplier of this company")})
        if partner.kind not in (Partner.Kind.BOTH, config.partner):
            raise ValidationError(
                {"partner": _("The selected customer/supplier type does not match this operation")}
            )
    else:
        partner = None

    if config.needs_account:
        if expense_account is None:
            raise ValidationError({"expense_account": _("Select the expense account")})
        if (
            expense_account.company_id != company.pk
            or expense_account.type != Account.Type.EXPENSE
            or not expense_account.is_leaf
        ):
            raise ValidationError({"expense_account": _("Select a leaf expense account")})
        debit_account = expense_account
    else:
        debit_account = accounts[config.debit]
    credit_account = accounts[config.credit]

    description = _description(kind, partner, debit_account)
    if reference:
        description += f" - {reference}"
    if note:
        description += f" - {note}"
    memo = reference[:300]
    partner_codes = (CUSTOMERS, SUPPLIERS)

    entry = accounting.create_entry(
        company=company,
        user=user,
        date=date,
        description=description[:500],
        lines=[
            LineInput(
                debit_account, debit=amount,
                partner=partner if debit_account.code in partner_codes else None, memo=memo,
            ),
            LineInput(
                credit_account, credit=amount,
                partner=partner if credit_account.code in partner_codes else None, memo=memo,
            ),
        ],
    )

    if not post_now:
        return entry, False, ""
    try:
        entry = accounting.post_entry(entry=entry, user=user)
    except ValidationError as error:
        return entry, False, error.messages[0]
    return entry, True, ""


def _parse_breakdown(quantities):
    total = ZERO
    breakdown = {}
    allowed = {str(d): d for d in DENOMINATIONS}
    for key, qty in (quantities or {}).items():
        if str(key) not in allowed:
            raise ValidationError({"quantities": _("Unknown denomination %(den)s") % {"den": key}})
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            raise ValidationError(
                {"quantities": _("Invalid quantity for %(den)s") % {"den": key}}
            )
        breakdown[str(key)] = qty
        total += allowed[str(key)] * qty
    return total, breakdown


@transaction.atomic
def record_cash_count(*, company, user, box, count_date, quantities, notes="", adjust=False):
    """Save a cash count. With adjust, also create the draft shortage/overage entry.

    The caller must have checked that the user may create entries before adjust.
    """
    accounts = treasury_accounts(company)
    if box.pk not in (accounts[EXPENSES_BOX].pk, accounts[COLLECTIONS_BOX].pk):
        raise ValidationError({"box": _("Select a cash box")})

    total, breakdown = _parse_breakdown(quantities)
    book = box_figures(company, box)["book"]
    difference = total - book

    entry = None
    if adjust and difference != 0:
        amount = abs(difference)
        cash_diff = accounts[CASH_DIFF]
        if difference < 0:
            text = _("Cash shortage adjustment - %(box)s")
            debit_account, credit_account = cash_diff, box
        else:
            text = _("Cash overage adjustment - %(box)s")
            debit_account, credit_account = box, cash_diff
        entry = accounting.create_entry(
            company=company,
            user=user,
            date=count_date,
            description=text % {"box": box.display_name},
            lines=[
                LineInput(debit_account, debit=amount),
                LineInput(credit_account, credit=amount),
            ],
            source="cash_count",
        )

    return CashCount.objects.create(
        company=company, box=box, count_date=count_date, counted_total=total,
        book_balance=book, difference=difference, breakdown=breakdown, notes=notes[:300],
        counted_by=user, entry=entry,
    )
