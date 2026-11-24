"""Read-only reports. Plain dicts with Decimals; the API layer formats them."""
from decimal import Decimal

from django.db.models import Sum

from .models import Account, JournalEntry, JournalLine, Partner

POSTED = JournalEntry.Status.POSTED
ZERO = Decimal("0")


def side(balance):
    """Which side a balance sits on: 'debit', 'credit' or '' when zero."""
    if balance > 0:
        return "debit"
    if balance < 0:
        return "credit"
    return ""


def balance_of(value):
    return {"amount": abs(value), "side": side(value)}


def net(lines):
    totals = lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    return (totals["d"] or ZERO) - (totals["c"] or ZERO)


def lines_of(company):
    return JournalLine.objects.filter(entry__company=company)


def incomplete_entries_count(company):
    return (
        lines_of(company)
        .filter(account__requires_partner=True, partner__isnull=True)
        .values("entry_id")
        .distinct()
        .count()
    )


def trial_balance(company, *, as_of=None):
    lines = lines_of(company).filter(entry__status=POSTED)
    if as_of:
        lines = lines.filter(entry__date__lte=as_of)
    sums = {
        row["account_id"]: row
        for row in lines.values("account_id").annotate(d=Sum("debit"), c=Sum("credit"))
    }

    rows = []
    for account in Account.objects.filter(company=company, pk__in=sums).order_by("code"):
        debit, credit = sums[account.pk]["d"] or ZERO, sums[account.pk]["c"] or ZERO
        balance = debit - credit
        rows.append(
            {
                "account_id": account.pk,
                "code": account.code,
                "name": account.name,
                "name_en": account.name_en,
                "debit": debit,
                "credit": credit,
                "balance_debit": balance if balance > 0 else ZERO,
                "balance_credit": -balance if balance < 0 else ZERO,
            }
        )

    def total(key):
        return sum((r[key] for r in rows), ZERO)

    return {
        "rows": rows,
        "total_debit": total("debit"),
        "total_credit": total("credit"),
        "total_balance_debit": total("balance_debit"),
        "total_balance_credit": total("balance_credit"),
        "is_balanced": total("debit") == total("credit"),
    }


def descendant_ids(company, account):
    """The account id plus the ids of all its sub-accounts."""
    ids = [account.pk]
    frontier = [account.pk]
    while frontier:
        frontier = list(
            Account.objects.filter(company=company, parent_id__in=frontier).values_list(
                "pk", flat=True
            )
        )
        ids.extend(frontier)
    return ids


def _by_status(lines, status):
    if status == "posted":
        return lines.filter(entry__status=POSTED)
    if status == "draft":
        return lines.exclude(entry__status=POSTED)
    return lines


def _brief(account):
    return {"id": account.pk, "code": account.code, "name": account.name, "name_en": account.name_en}


def general_ledger(company, *, account=None, date_from=None, date_to=None, status="posted"):
    """One ledger per account (or one for a parent account covering its children)."""
    if account is not None:
        targets = [account]
    else:
        used = lines_of(company).values_list("account_id", flat=True).distinct()
        targets = list(Account.objects.filter(company=company, is_leaf=True, pk__in=used))

    ledgers = []
    for target in targets:
        is_parent = not target.is_leaf
        ids = descendant_ids(company, target) if is_parent else [target.pk]
        base = _by_status(lines_of(company).filter(account_id__in=ids), status)

        opening = net(base.filter(entry__date__lt=date_from)) if date_from else ZERO

        period = base
        if date_from:
            period = period.filter(entry__date__gte=date_from)
        if date_to:
            period = period.filter(entry__date__lte=date_to)
        period = period.select_related("entry", "account", "partner").order_by(
            "entry__date", "entry_id", "id"
        )

        rows, balance, total_debit, total_credit = [], opening, ZERO, ZERO
        for line in period:
            balance += line.debit - line.credit
            total_debit += line.debit
            total_credit += line.credit
            rows.append(
                {
                    "date": line.entry.date,
                    "entry_id": line.entry_id,
                    "status": line.entry.status,
                    "description": line.entry.description,
                    "memo": line.memo,
                    "partner": (
                        {"id": line.partner_id, "name": line.partner.name} if line.partner_id else None
                    ),
                    "sub_account": _brief(line.account) if is_parent else None,
                    "debit": line.debit,
                    "credit": line.credit,
                    "balance": balance_of(balance),
                }
            )

        if account is None and not rows and opening == 0:
            continue
        ledgers.append(
            {
                "account": _brief(target),
                "is_parent": is_parent,
                "opening": balance_of(opening),
                "rows": rows,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "closing": balance_of(balance),
            }
        )
    return {"ledgers": ledgers}


def partner_statement(company, partner, *, date_from=None, date_to=None, status="all"):
    """A customer/supplier statement with posted and overall running balances.

    The status filter only hides rows; balances are always computed on every row.
    """
    all_lines = lines_of(company).filter(partner=partner)

    open_posted = open_all = ZERO
    if date_from:
        before = all_lines.filter(entry__date__lt=date_from)
        open_all = net(before)
        open_posted = net(before.filter(entry__status=POSTED))

    period = all_lines
    if date_from:
        period = period.filter(entry__date__gte=date_from)
    if date_to:
        period = period.filter(entry__date__lte=date_to)
    period = period.select_related("entry", "account").order_by("entry__date", "entry_id", "id")

    rows = []
    bal_posted, bal_all = open_posted, open_all
    posted_debit = posted_credit = draft_debit = draft_credit = ZERO

    for line in period:
        is_posted = line.entry.status == POSTED
        bal_all += line.debit - line.credit
        if is_posted:
            bal_posted += line.debit - line.credit
            posted_debit += line.debit
            posted_credit += line.credit
        else:
            draft_debit += line.debit
            draft_credit += line.credit

        if status == "posted" and not is_posted:
            continue
        if status == "draft" and is_posted:
            continue
        rows.append(
            {
                "date": line.entry.date,
                "entry_id": line.entry_id,
                "status": line.entry.status,
                "description": line.entry.description,
                "account": _brief(line.account),
                "memo": line.memo,
                "debit": line.debit,
                "credit": line.credit,
                "balance_posted": balance_of(bal_posted),
                "balance_all": balance_of(bal_all),
            }
        )

    draft_net = draft_debit - draft_credit
    return {
        "partner": {"id": partner.pk, "name": partner.name, "kind": partner.kind},
        "rows": rows,
        "opening_posted": balance_of(open_posted),
        "opening_all": balance_of(open_all),
        "posted_debit": posted_debit,
        "posted_credit": posted_credit,
        "draft_debit": draft_debit,
        "draft_credit": draft_credit,
        "closing_posted": balance_of(bal_posted),
        "closing_all": balance_of(bal_all),
        "draft_net": balance_of(draft_net),
        "has_draft": draft_debit > 0 or draft_credit > 0,
        "incomplete_entries": incomplete_entries_count(company),
    }
