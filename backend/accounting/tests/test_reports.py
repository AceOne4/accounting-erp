from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from accounting import reports, services
from accounting.models import Partner

pytestmark = pytest.mark.django_db


def line(account, debit=0, credit=0, partner=None):
    return services.LineInput(
        account=account, debit=Decimal(str(debit)), credit=Decimal(str(credit)), partner=partner
    )


@pytest.fixture
def user():
    return get_user_model().objects.create_user("sara", password="x")


@pytest.fixture
def books(company, user, account_of, customer):
    """Two posted entries, one draft. All on the customer's receivable except the cash one."""
    receivable, sales = account_of(company, "102"), account_of(company, "401")
    box = account_of(company, "1012")

    def entry(day, description, lines, post=True):
        e = services.create_entry(
            company=company, user=user, date=day, description=description, lines=lines
        )
        return services.post_entry(entry=e, user=user) if post else e

    entry(date(2026, 10, 1), "Invoice 1", [line(receivable, 1000, partner=customer), line(sales, credit=1000)])
    entry(date(2026, 11, 1), "Collection", [line(box, 400), line(receivable, credit=400, partner=customer)])
    entry(
        date(2026, 11, 5),
        "Invoice 2 (draft)",
        [line(receivable, 250, partner=customer), line(sales, credit=250)],
        post=False,
    )
    return company


def test_trial_balance_counts_only_posted_entries(books):
    result = reports.trial_balance(books)
    by_code = {row["code"]: row for row in result["rows"]}

    assert by_code["102"]["debit"] == Decimal("1000.00")
    assert by_code["102"]["credit"] == Decimal("400.00")
    assert by_code["102"]["balance_debit"] == Decimal("600.00")
    assert by_code["401"]["balance_credit"] == Decimal("1000.00")  # the draft 250 is not counted
    assert result["is_balanced"]
    assert result["total_debit"] == result["total_credit"] == Decimal("1400.00")
    assert result["total_balance_debit"] == result["total_balance_credit"]


def test_trial_balance_as_of_date(books):
    result = reports.trial_balance(books, as_of=date(2026, 10, 31))
    assert {row["code"] for row in result["rows"]} == {"102", "401"}
    assert result["total_debit"] == Decimal("1000.00")


def test_reports_never_mix_companies(books, other_company):
    assert reports.trial_balance(other_company)["rows"] == []
    assert reports.general_ledger(other_company)["ledgers"] == []


def test_general_ledger_running_balance_and_opening(books, account_of):
    receivable = account_of(books, "102")
    ledger = reports.general_ledger(books, account=receivable, date_from=date(2026, 10, 15))["ledgers"][0]

    assert ledger["opening"] == {"amount": Decimal("1000.00"), "side": "debit"}
    assert [r["description"] for r in ledger["rows"]] == ["Collection"]
    assert ledger["rows"][0]["balance"] == {"amount": Decimal("600.00"), "side": "debit"}
    assert ledger["closing"] == {"amount": Decimal("600.00"), "side": "debit"}


def test_general_ledger_status_filter(books, account_of):
    receivable = account_of(books, "102")
    posted = reports.general_ledger(books, account=receivable)["ledgers"][0]
    everything = reports.general_ledger(books, account=receivable, status="all")["ledgers"][0]
    drafts = reports.general_ledger(books, account=receivable, status="draft")["ledgers"][0]

    assert len(posted["rows"]) == 2
    assert len(everything["rows"]) == 3
    assert [r["description"] for r in drafts["rows"]] == ["Invoice 2 (draft)"]
    assert everything["closing"]["amount"] == Decimal("850.00")


def test_general_ledger_of_a_parent_account_covers_its_children(books, account_of):
    ledger = reports.general_ledger(books, account=account_of(books, "10"))["ledgers"][0]
    assert ledger["is_parent"]
    assert {r["sub_account"]["code"] for r in ledger["rows"]} == {"102", "1012"}
    assert ledger["closing"] == {"amount": Decimal("1000.00"), "side": "debit"}  # 600 + 400


def test_general_ledger_without_an_account_lists_only_active_accounts(books):
    codes = {ledger["account"]["code"] for ledger in reports.general_ledger(books, status="all")["ledgers"]}
    assert codes == {"102", "401", "1012"}


def test_partner_statement_separates_posted_and_draft(books, customer):
    statement = reports.partner_statement(books, customer)

    assert [r["description"] for r in statement["rows"]] == ["Invoice 1", "Collection", "Invoice 2 (draft)"]
    last = statement["rows"][-1]
    assert last["balance_posted"] == {"amount": Decimal("600.00"), "side": "debit"}
    assert last["balance_all"] == {"amount": Decimal("850.00"), "side": "debit"}
    assert statement["closing_posted"]["amount"] == Decimal("600.00")
    assert statement["closing_all"]["amount"] == Decimal("850.00")
    assert statement["draft_net"] == {"amount": Decimal("250.00"), "side": "debit"}
    assert statement["has_draft"]


def test_statement_filter_only_hides_rows(books, customer):
    only_posted = reports.partner_statement(books, customer, status="posted")
    assert [r["description"] for r in only_posted["rows"]] == ["Invoice 1", "Collection"]
    assert only_posted["closing_all"]["amount"] == Decimal("850.00")  # drafts still counted in the totals

    only_drafts = reports.partner_statement(books, customer, status="draft")
    assert [r["description"] for r in only_drafts["rows"]] == ["Invoice 2 (draft)"]
    assert only_drafts["rows"][0]["balance_all"]["amount"] == Decimal("850.00")


def test_statement_opening_balance(books, customer):
    statement = reports.partner_statement(books, customer, date_from=date(2026, 11, 1))
    assert statement["opening_posted"] == {"amount": Decimal("1000.00"), "side": "debit"}
    assert statement["opening_all"] == {"amount": Decimal("1000.00"), "side": "debit"}
    assert [r["description"] for r in statement["rows"]] == ["Collection", "Invoice 2 (draft)"]


def test_statement_ignores_other_partners(books, customer):
    stranger = Partner.objects.create(company=books, name="Delta", kind=Partner.Kind.CUSTOMER)
    statement = reports.partner_statement(books, stranger)
    assert statement["rows"] == []
    assert statement["closing_all"]["amount"] == 0
