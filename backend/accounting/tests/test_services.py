from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounting import services
from accounting.chart import DEFAULT_CHART, seed_default_chart
from accounting.models import Account, JournalEntry, JournalLine
from core.models import Company

pytestmark = pytest.mark.django_db

DAY = "2026-11-01"


def line(account, debit=0, credit=0, partner=None, memo=""):
    return services.LineInput(
        account=account,
        debit=Decimal(str(debit)),
        credit=Decimal(str(credit)),
        partner=partner,
        memo=memo,
    )


@pytest.fixture
def user():
    return get_user_model().objects.create_user("sara", password="x")


@pytest.fixture
def cash_sale(company, account_of):
    """Lines of a balanced cash sale."""
    return [
        line(account_of(company, "1012"), debit=1000),
        line(account_of(company, "401"), credit=1000),
    ]


def make_entry(company, user, lines, **kwargs):
    return services.create_entry(
        company=company, user=user, date=DAY, description="Cash sale", lines=lines, **kwargs
    )


def test_create_draft_then_post(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    assert entry.status == JournalEntry.Status.DRAFT
    assert entry.lines.count() == 2

    posted = services.post_entry(entry=entry, user=user)
    assert posted.status == JournalEntry.Status.POSTED
    assert posted.posted_by == user
    assert posted.posted_at is not None


def test_unbalanced_entry_saves_as_draft_but_cannot_post(company, user, account_of):
    entry = make_entry(
        company,
        user,
        [line(account_of(company, "1012"), debit=1000), line(account_of(company, "401"), credit=900)],
    )
    with pytest.raises(ValidationError, match="unbalanced"):
        services.post_entry(entry=entry, user=user)
    entry.refresh_from_db()
    assert entry.status == JournalEntry.Status.DRAFT


def test_entry_needs_lines(company, user):
    with pytest.raises(ValidationError, match="no lines"):
        make_entry(company, user, [])


def test_post_twice_is_rejected(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    services.post_entry(entry=entry, user=user)
    with pytest.raises(ValidationError, match="already posted"):
        services.post_entry(entry=entry, user=user)


def test_receivable_line_needs_a_partner(company, user, account_of, customer):
    receivable = account_of(company, "102")
    sales = account_of(company, "401")
    with pytest.raises(ValidationError, match="customer/supplier"):
        make_entry(company, user, [line(receivable, debit=500), line(sales, credit=500)])

    entry = make_entry(
        company, user, [line(receivable, debit=500, partner=customer), line(sales, credit=500)]
    )
    assert services.post_entry(entry=entry, user=user).status == JournalEntry.Status.POSTED


def test_cannot_post_to_a_parent_account(company, user, account_of):
    with pytest.raises(ValidationError, match="parent account"):
        make_entry(
            company,
            user,
            [line(account_of(company, "10"), debit=10), line(account_of(company, "401"), credit=10)],
        )


@pytest.mark.parametrize(
    "debit, credit, message",
    [
        (10, 10, "not both"),
        (0, 0, "must have a value"),
        (-5, 0, "positive"),
        ("1.005", 0, "two decimal places"),
    ],
)
def test_line_rules(company, user, account_of, debit, credit, message):
    bad = line(account_of(company, "1012"), debit=debit, credit=credit)
    with pytest.raises(ValidationError, match=message):
        make_entry(company, user, [bad, line(account_of(company, "401"), credit=10)])


def test_account_from_another_company_is_rejected(company, other_company, user, account_of):
    foreign = account_of(other_company, "1012")
    with pytest.raises(ValidationError, match="another company"):
        make_entry(company, user, [line(foreign, debit=10), line(account_of(company, "401"), credit=10)])


def test_nothing_is_saved_when_a_later_line_is_invalid(company, user, account_of):
    with pytest.raises(ValidationError):
        make_entry(
            company,
            user,
            [line(account_of(company, "1012"), debit=10), line(account_of(company, "10"), credit=10)],
        )
    assert JournalEntry.objects.count() == 0
    assert JournalLine.objects.count() == 0


def test_update_replaces_a_drafts_lines(company, user, cash_sale, account_of):
    entry = make_entry(company, user, cash_sale)
    services.update_entry(
        entry=entry,
        date=DAY,
        description="Changed",
        lines=[line(account_of(company, "1012"), debit=50), line(account_of(company, "403"), credit=50)],
    )
    entry.refresh_from_db()
    assert entry.description == "Changed"
    assert sorted(entry.lines.values_list("debit", "credit")) == [(0, 50), (50, 0)]


def test_posted_entry_cannot_be_updated_or_deleted(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    services.post_entry(entry=entry, user=user)

    with pytest.raises(ValidationError, match="cannot be changed"):
        services.update_entry(entry=entry, date=DAY, description="x", lines=cash_sale)
    with pytest.raises(ValidationError):
        services.delete_entry(entry=entry)
    assert entry.lines.count() == 2


def test_models_refuse_to_touch_posted_data_directly(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    services.post_entry(entry=entry, user=user)
    entry.refresh_from_db()

    entry.description = "tampered"
    with pytest.raises(ValidationError):
        entry.save()
    with pytest.raises(ValidationError):
        entry.delete()

    posted_line = entry.lines.first()
    posted_line.memo = "tampered"
    with pytest.raises(ValidationError):
        posted_line.save()
    with pytest.raises(ValidationError):
        posted_line.delete()
    with pytest.raises(ValidationError):
        JournalLine.objects.create(entry=entry, account=posted_line.account, debit=1)


def test_delete_draft(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    services.delete_entry(entry=entry)
    assert not JournalEntry.objects.filter(pk=entry.pk).exists()


def test_history_records_changes(company, user, cash_sale):
    entry = make_entry(company, user, cash_sale)
    services.post_entry(entry=entry, user=user)
    statuses = [h.status for h in entry.history.order_by("history_date", "history_id")]
    assert statuses == ["draft", "posted"]


def test_default_chart_is_consistent_and_repeatable(company):
    count = Account.objects.filter(company=company).count()
    assert count == len(DEFAULT_CHART)

    created, updated = seed_default_chart(company)
    assert (created, updated) == (0, count)

    treasury = Account.objects.get(company=company, code="101")
    assert not treasury.is_leaf
    assert set(treasury.children.values_list("code", flat=True)) == {"1011", "1012"}
    assert Account.objects.get(company=company, code="102").requires_partner
    assert Account.objects.get(company=company, code="201").requires_partner


def test_same_account_code_is_allowed_in_each_company(company, other_company):
    assert Company.objects.count() == 2
    assert Account.objects.filter(code="101").count() == 2
