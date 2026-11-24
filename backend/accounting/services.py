"""Business rules for journal entries. The API only calls these functions.

Rules ported from the old project:
- a line is debit or credit, positive, with a value, on a leaf account
- lines on receivable/payable accounts need a customer/supplier
- an entry can only be posted when it is balanced and complete
- posted entries never change
and added: everything is scoped to one company, and posting locks the entry row.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Account, JournalEntry, JournalLine, Partner

CENT = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class LineInput:
    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    partner: Partner | None = None
    memo: str = field(default="")


def _fail(number, message):
    raise ValidationError(_("Line %(n)s: %(message)s") % {"n": number, "message": message})


def validate_lines(company, lines):
    if not lines:
        raise ValidationError(_("The entry has no lines"))
    for number, line in enumerate(lines, start=1):
        if line.account.company_id != company.id:
            _fail(number, _("the account belongs to another company"))
        if line.partner is not None and line.partner.company_id != company.id:
            _fail(number, _("the customer/supplier belongs to another company"))
        if line.debit < 0 or line.credit < 0:
            _fail(number, _("amounts must be positive"))
        if line.debit != line.debit.quantize(CENT) or line.credit != line.credit.quantize(CENT):
            _fail(number, _("amounts have at most two decimal places"))
        if line.debit > 0 and line.credit > 0:
            _fail(number, _("a line must be either debit or credit, not both"))
        if line.debit == 0 and line.credit == 0:
            _fail(number, _("a line must have a value"))
        if not line.account.is_leaf:
            _fail(number, _("you cannot post entries to a parent account"))
        if line.account.requires_partner and line.partner is None:
            _fail(
                number,
                _("select the customer/supplier for the account (%(account)s)")
                % {"account": line.account.display_name},
            )


def _write_lines(entry, lines):
    for line in lines:
        JournalLine.objects.create(
            entry=entry,
            account=line.account,
            partner=line.partner,
            debit=line.debit,
            credit=line.credit,
            memo=line.memo,
        )


@transaction.atomic
def create_entry(*, company, user, date, description, lines, is_ai_generated=False):
    """Create a draft entry with its lines. Drafts may be unbalanced."""
    validate_lines(company, lines)
    entry = JournalEntry.objects.create(
        company=company,
        date=date,
        description=description,
        created_by=user,
        is_ai_generated=is_ai_generated,
    )
    _write_lines(entry, lines)
    return entry


def _locked_draft(entry):
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk, company_id=entry.company_id)
    if locked.status == JournalEntry.Status.POSTED:
        raise ValidationError(_("Posted entries cannot be changed"))
    return locked


@transaction.atomic
def update_entry(*, entry, date, description, lines):
    """Replace a draft's header and lines."""
    locked = _locked_draft(entry)
    validate_lines(locked.company, lines)
    locked.date = date
    locked.description = description
    locked.save()
    for old in list(locked.lines.all()):
        old.delete()
    _write_lines(locked, lines)
    return locked


@transaction.atomic
def delete_entry(*, entry):
    locked = _locked_draft(entry)
    for line in list(locked.lines.all()):
        line.delete()
    locked.delete()


@transaction.atomic
def post_entry(*, entry, user):
    """Post a draft: it must have lines, balance, and have its partners filled in."""
    locked = JournalEntry.objects.select_for_update().get(pk=entry.pk, company_id=entry.company_id)
    if locked.status == JournalEntry.Status.POSTED:
        raise ValidationError(_("The entry is already posted"))

    lines = list(locked.lines.select_related("account"))
    if not lines:
        raise ValidationError(_("The entry has no lines"))

    debit = sum((line.debit for line in lines), ZERO)
    credit = sum((line.credit for line in lines), ZERO)
    if debit != credit:
        raise ValidationError(
            _("The entry is unbalanced: debit %(debit)s / credit %(credit)s")
            % {"debit": debit, "credit": credit}
        )

    missing = [line for line in lines if line.account.requires_partner and line.partner_id is None]
    if missing:
        names = ", ".join(sorted({line.account.display_name for line in missing}))
        raise ValidationError(
            _("The entry is incomplete: select the customer/supplier on the lines of (%(accounts)s)")
            % {"accounts": names}
        )

    locked.status = JournalEntry.Status.POSTED
    locked.posted_at = timezone.now()
    locked.posted_by = user
    locked.save()
    return locked
