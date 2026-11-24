from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounting.models import JournalEntry, Partner
from core.models import Membership
from treasury import services
from treasury.models import CashCount

pytestmark = pytest.mark.django_db
Role = Membership.Role
D = Decimal


@pytest.fixture
def accountant(make_user, company):
    return make_user("amr", company, Role.ACCOUNTANT)


@pytest.fixture
def chief(make_user, company):
    return make_user("chief", company, Role.CHIEF)


@pytest.fixture
def reviewer(make_user, company):
    return make_user("rana", company, Role.REVIEWER)


@pytest.fixture
def supplier(company):
    return Partner.objects.create(company=company, name="Delta", kind=Partner.Kind.SUPPLIER)


def voucher(company, user, kind, **kw):
    args = dict(company=company, user=user, kind=kind, date="2026-11-01", amount="100.00")
    args.update(kw)
    return services.create_voucher(**args)


def balances(entry):
    return {(l.account.code, l.debit, l.credit) for l in entry.lines.select_related("account")}


# ------------------------------------------------------------------ services
def test_collect_hits_collections_box_and_customer(company, accountant, customer):
    entry, posted, error = voucher(company, accountant, "collect", partner=customer)
    assert (posted, error) == (False, "")
    assert balances(entry) == {("1012", D("100"), D("0")), ("102", D("0"), D("100"))}
    assert entry.lines.get(account__code="102").partner == customer
    assert entry.lines.get(account__code="1012").partner is None
    assert customer.name in entry.description


@pytest.mark.parametrize(
    "kind,debit,credit",
    [("deposit", "103", "1012"), ("fund", "1011", "103")],
)
def test_partnerless_kinds(company, accountant, kind, debit, credit):
    entry, *_ = voucher(company, accountant, kind)
    assert balances(entry) == {(debit, D("100"), D("0")), (credit, D("0"), D("100"))}


def test_refund_and_supplier_payment(company, accountant, customer, supplier, account_of):
    entry, *_ = voucher(company, accountant, "refund", partner=customer)
    assert balances(entry) == {("102", D("100"), D("0")), ("1012", D("0"), D("100"))}
    entry, *_ = voucher(company, accountant, "supplier", partner=supplier)
    assert balances(entry) == {("201", D("100"), D("0")), ("1011", D("0"), D("100"))}
    assert entry.lines.get(account__code="201").partner == supplier


def test_expense_needs_a_leaf_expense_account(company, accountant, account_of):
    entry, *_ = voucher(company, accountant, "expense", expense_account=account_of(company, "512"))
    assert balances(entry) == {("512", D("100"), D("0")), ("1011", D("0"), D("100"))}
    with pytest.raises(ValidationError):
        voucher(company, accountant, "expense")
    with pytest.raises(ValidationError):
        voucher(company, accountant, "expense", expense_account=account_of(company, "401"))
    with pytest.raises(ValidationError):  # a parent expense account
        voucher(company, accountant, "expense", expense_account=account_of(company, "51"))


def test_partner_rules(company, accountant, customer, supplier, other_company):
    with pytest.raises(ValidationError):
        voucher(company, accountant, "collect")
    with pytest.raises(ValidationError):  # supplier on a customer operation
        voucher(company, accountant, "collect", partner=supplier)
    with pytest.raises(ValidationError):
        voucher(company, accountant, "supplier", partner=customer)
    foreign = Partner.objects.create(company=other_company, name="X", kind="customer")
    with pytest.raises(ValidationError):
        voucher(company, accountant, "collect", partner=foreign)
    both = Partner.objects.create(company=company, name="Both", kind="both")
    voucher(company, accountant, "collect", partner=both)
    voucher(company, accountant, "supplier", partner=both)


@pytest.mark.parametrize("amount", ["0", "-5", "10.005", "abc", "NaN"])
def test_bad_amounts(company, accountant, amount):
    with pytest.raises(ValidationError):
        voucher(company, accountant, "deposit", amount=amount)


def test_post_now(company, chief, customer):
    entry, posted, error = voucher(company, chief, "deposit", post_now=True)
    assert posted and error == "" and entry.status == JournalEntry.Status.POSTED


def test_posting_failure_keeps_the_draft(company, chief, monkeypatch):
    def refuse(**kwargs):
        raise ValidationError("The period is closed")

    monkeypatch.setattr(services.accounting, "post_entry", refuse)
    entry, posted, error = voucher(company, chief, "deposit", post_now=True)
    assert not posted and error == "The period is closed"
    assert JournalEntry.objects.get(pk=entry.pk).status == JournalEntry.Status.DRAFT


def test_missing_treasury_accounts(company, accountant):
    company_without = type(company).objects.create(name="Bare")
    with pytest.raises(ValidationError):
        services.treasury_accounts(company_without)


def test_box_figures_split_posted_and_pending(company, chief, account_of):
    voucher(company, chief, "fund", amount="500.00", post_now=True)
    voucher(company, chief, "fund", amount="200.00")  # stays draft
    figures = services.box_figures(company, account_of(company, "1011"))
    assert (figures["posted"], figures["pending"], figures["book"]) == (D("500"), D("200"), D("700"))


def test_figures_are_company_scoped(company, other_company, chief, make_user, account_of):
    voucher(company, chief, "fund", amount="500.00", post_now=True)
    figures = services.box_figures(other_company, account_of(other_company, "1011"))
    assert figures["book"] == D("0")


# --------------------------------------------------------------- cash counts
def fund_box(company, chief, amount="1000.00"):
    voucher(company, chief, "fund", amount=amount, post_now=True)


def test_count_totals_and_difference(company, chief, account_of):
    fund_box(company, chief)
    box = account_of(company, "1011")
    count = services.record_cash_count(
        company=company, user=chief, box=box, count_date="2026-11-02",
        quantities={"200": 4, "100": 1, "0.5": 3}, notes="evening",
    )
    assert count.counted_total == D("901.50")
    assert count.book_balance == D("1000.00")
    assert count.difference == D("-98.50")
    assert count.entry is None
    assert count.breakdown == {"200": 4, "100": 1, "0.5": 3}


def test_count_with_adjustment_shortage(company, chief, account_of):
    fund_box(company, chief)
    box = account_of(company, "1011")
    count = services.record_cash_count(
        company=company, user=chief, box=box, count_date="2026-11-02",
        quantities={"200": 4}, adjust=True,
    )
    assert balances(count.entry) == {("510", D("200"), D("0")), ("1011", D("0"), D("200"))}
    assert count.entry.status == JournalEntry.Status.DRAFT


def test_count_with_adjustment_overage(company, chief, account_of):
    fund_box(company, chief, "100.00")
    box = account_of(company, "1011")
    count = services.record_cash_count(
        company=company, user=chief, box=box, count_date="2026-11-02",
        quantities={"100": 2}, adjust=True,
    )
    assert balances(count.entry) == {("1011", D("100"), D("0")), ("510", D("0"), D("100"))}


def test_no_adjustment_when_difference_is_zero(company, chief, account_of):
    fund_box(company, chief, "100.00")
    count = services.record_cash_count(
        company=company, user=chief, box=account_of(company, "1011"),
        count_date="2026-11-02", quantities={"100": 1}, adjust=True,
    )
    assert count.difference == 0 and count.entry is None


def test_count_rejects_bad_input(company, chief, account_of):
    box = account_of(company, "1011")
    for quantities in ({"7": 1}, {"100": -1}, {"100": 1.5}, {"100": True}):
        with pytest.raises(ValidationError):
            services.record_cash_count(
                company=company, user=chief, box=box, count_date="2026-11-02",
                quantities=quantities,
            )
    with pytest.raises(ValidationError):  # the bank is not a cash box
        services.record_cash_count(
            company=company, user=chief, box=account_of(company, "103"),
            count_date="2026-11-02", quantities={"100": 1},
        )
    assert CashCount.objects.count() == 0


# ----------------------------------------------------------------------- API
V = "/api/v1/treasury/vouchers/"
C = "/api/v1/treasury/cash-counts/"
O = "/api/v1/treasury/overview/"


def test_overview(company, chief, client_for):
    fund_box(company, chief, "300.00")
    response = client_for(chief, company).get(O)
    assert response.status_code == 200
    boxes = {b["code"]: b for b in response.json()["boxes"]}
    assert boxes["1011"]["book"] == "300.00"
    assert boxes["103"]["book"] == "-300.00"
    assert response.json()["denominations"][0] == "200"
    assert len(response.json()["recent_entries"]) == 1


def test_voucher_api_roles(company, accountant, reviewer, chief, customer, client_for):
    body = {"kind": "collect", "date": "2026-11-01", "amount": "50.00", "partner": customer.pk}
    assert client_for(reviewer, company).post(V, body, format="json").status_code == 403

    response = client_for(accountant, company).post(V, body, format="json")
    assert response.status_code == 201
    assert response.json()["posted"] is False

    # an accountant cannot post
    denied = client_for(accountant, company).post(V, {**body, "post_now": True}, format="json")
    assert denied.status_code == 403

    posted = client_for(chief, company).post(V, {**body, "post_now": True}, format="json")
    assert posted.status_code == 201 and posted.json()["posted"] is True


def test_voucher_api_validation_and_tenancy(company, other_company, accountant, customer, client_for):
    client = client_for(accountant, company)
    r = client.post(V, {"kind": "collect", "date": "2026-11-01", "amount": "50"}, format="json")
    assert r.status_code == 400 and "partner" in r.json()
    foreign = Partner.objects.create(company=other_company, name="X", kind="customer")
    r = client.post(
        V, {"kind": "collect", "date": "2026-11-01", "amount": "50", "partner": foreign.pk},
        format="json",
    )
    assert r.status_code == 400
    r = client.post(V, {"kind": "deposit", "date": "2026-11-01", "amount": "0"}, format="json")
    assert r.status_code == 400


def test_cash_count_api(company, chief, accountant, reviewer, account_of, client_for):
    fund_box(company, chief, "1000.00")
    box = account_of(company, "1011").pk
    body = {"box": box, "count_date": "2026-11-02", "quantities": {"200": 4}, "adjust": True}

    assert client_for(reviewer, company).post(C, body, format="json").status_code == 403
    response = client_for(accountant, company).post(C, body, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["difference"] == "-200.00" and data["entry"] is not None

    listing = client_for(reviewer, company).get(C)
    assert listing.status_code == 200 and len(listing.json()["results"]) == 1


def test_cash_count_api_is_company_scoped(
    company, other_company, chief, make_user, client_for, account_of
):
    fund_box(company, chief)
    outsider = make_user("out", other_company, Role.CHIEF)
    assert client_for(outsider, other_company).get(C).json()["results"] == []
    bad_box = {"box": account_of(company, "1011").pk, "quantities": {"100": 1}}
    r = client_for(outsider, other_company).post(C, bad_box, format="json")
    assert r.status_code == 400
