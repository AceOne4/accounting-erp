import pytest
from rest_framework.test import APIClient

from accounting.models import Account, JournalEntry, JournalLine, Partner
from core.models import Membership

pytestmark = pytest.mark.django_db

ENTRIES = "/api/v1/journal-entries/"
Role = Membership.Role


def payload(company, account_of, debit="1000.00", credit="1000.00", description="Cash sale"):
    return {
        "date": "2026-11-01",
        "description": description,
        "lines": [
            {"account": account_of(company, "1012").pk, "debit": debit},
            {"account": account_of(company, "401").pk, "credit": credit},
        ],
    }


@pytest.fixture
def accountant(make_user, company):
    return make_user("amr", company, Role.ACCOUNTANT)


@pytest.fixture
def reviewer(make_user, company):
    return make_user("rana", company, Role.REVIEWER)


@pytest.fixture
def chief(make_user, company):
    return make_user("chief", company, Role.CHIEF)


@pytest.fixture
def sysadmin(make_user, company):
    return make_user("admin", company, Role.ADMIN)


# ---------- access and tenancy ----------


def test_anonymous_requests_are_rejected():
    assert APIClient().get(ENTRIES).status_code in (401, 403)


def test_single_membership_needs_no_header(accountant, client_for):
    assert client_for(accountant).get(ENTRIES).status_code == 200


def test_non_member_cannot_use_a_company(accountant, other_company, client_for):
    response = client_for(accountant, other_company).get(ENTRIES)
    assert response.status_code == 403


def test_two_memberships_require_the_header(make_user, company, other_company, client_for):
    user = make_user("both", company, Role.CHIEF)
    make_user("both", other_company, Role.ACCOUNTANT)
    assert client_for(user).get(ENTRIES).status_code == 400
    assert client_for(user, company).get(ENTRIES).status_code == 200
    assert client_for(user, other_company).get(ENTRIES).status_code == 200


def test_bad_company_header(accountant, client_for):
    client = client_for(accountant)
    client.defaults["HTTP_X_COMPANY_ID"] = "abc"
    assert client.get(ENTRIES).status_code == 400


def test_company_data_is_isolated(
    company, other_company, accountant, make_user, client_for, account_of
):
    outsider = make_user("outsider", other_company, Role.CHIEF)
    created = client_for(accountant).post(ENTRIES, payload(company, account_of), format="json")
    assert created.status_code == 201, created.content

    theirs = client_for(outsider)
    assert theirs.get(ENTRIES).json()["count"] == 0
    assert theirs.get(f"{ENTRIES}{created.json()['id']}/").status_code == 404
    assert theirs.post(f"{ENTRIES}{created.json()['id']}/post/").status_code == 404


def test_lines_cannot_reference_another_companys_account(
    company, other_company, accountant, client_for, account_of
):
    body = payload(company, account_of)
    body["lines"][0]["account"] = account_of(other_company, "1012").pk
    response = client_for(accountant).post(ENTRIES, body, format="json")
    assert response.status_code == 400
    assert JournalEntry.objects.count() == 0


# ---------- roles ----------


def test_accountant_creates_but_cannot_post(company, accountant, client_for, account_of):
    client = client_for(accountant)
    created = client.post(ENTRIES, payload(company, account_of), format="json")
    assert created.status_code == 201
    assert client.post(f"{ENTRIES}{created.json()['id']}/post/").status_code == 403


def test_reviewer_posts_but_cannot_create(company, accountant, reviewer, client_for, account_of):
    created = client_for(accountant).post(ENTRIES, payload(company, account_of), format="json")
    entry_id = created.json()["id"]

    review = client_for(reviewer)
    assert review.post(ENTRIES, payload(company, account_of), format="json").status_code == 403
    posted = review.post(f"{ENTRIES}{entry_id}/post/")
    assert posted.status_code == 200
    assert posted.json()["status"] == "posted"
    assert posted.json()["posted_by"] == "rana"


def test_system_admin_reads_but_cannot_write(company, sysadmin, client_for, account_of):
    client = client_for(sysadmin)
    assert client.get(ENTRIES).status_code == 200
    assert client.get("/api/v1/reports/trial-balance/").status_code == 200
    assert client.post(ENTRIES, payload(company, account_of), format="json").status_code == 403


def test_only_chief_can_delete_and_only_drafts(company, accountant, chief, client_for, account_of):
    draft = client_for(accountant).post(ENTRIES, payload(company, account_of), format="json").json()
    assert client_for(accountant).delete(f"{ENTRIES}{draft['id']}/").status_code == 403

    boss = client_for(chief)
    assert boss.delete(f"{ENTRIES}{draft['id']}/").status_code == 204

    other = boss.post(ENTRIES, payload(company, account_of), format="json").json()
    assert boss.post(f"{ENTRIES}{other['id']}/post/").status_code == 200
    assert boss.delete(f"{ENTRIES}{other['id']}/").status_code == 400
    assert JournalEntry.objects.filter(pk=other["id"]).exists()


# ---------- entries ----------


def test_money_is_returned_as_strings_with_totals(company, accountant, client_for, account_of):
    response = client_for(accountant).post(
        ENTRIES, payload(company, account_of, debit="1000.50", credit="1000.50"), format="json"
    )
    data = response.json()
    assert data["total_debit"] == "1000.50"
    assert data["total_credit"] == "1000.50"
    assert data["lines"][0]["debit"] == "1000.50"
    assert data["status"] == "draft"
    assert data["created_by"] == "amr"
    assert data["missing_partner_lines"] == 0


def test_unbalanced_entry_saves_as_draft_and_post_explains_why(
    company, accountant, chief, client_for, account_of
):
    created = client_for(accountant).post(
        ENTRIES, payload(company, account_of, debit="1000", credit="900"), format="json"
    )
    assert created.status_code == 201
    response = client_for(chief).post(f"{ENTRIES}{created.json()['id']}/post/")
    assert response.status_code == 400
    assert "unbalanced" in response.json()[0]


def test_invalid_line_is_reported_with_its_number(company, accountant, client_for, account_of):
    body = payload(company, account_of)
    body["lines"][1]["account"] = account_of(company, "10").pk  # a parent account
    response = client_for(accountant).post(ENTRIES, body, format="json")
    assert response.status_code == 400
    assert "Line 2" in response.json()[0]


def test_draft_can_be_edited_posted_cannot(company, accountant, chief, client_for, account_of):
    client = client_for(accountant)
    entry = client.post(ENTRIES, payload(company, account_of), format="json").json()

    body = payload(company, account_of, debit="75", credit="75", description="Edited")
    edited = client.put(f"{ENTRIES}{entry['id']}/", body, format="json")
    assert edited.status_code == 200
    assert edited.json()["description"] == "Edited"
    assert edited.json()["total_debit"] == "75.00"

    client_for(chief).post(f"{ENTRIES}{entry['id']}/post/")
    again = client.put(f"{ENTRIES}{entry['id']}/", body, format="json")
    assert again.status_code == 400


def test_filters_and_incomplete_entries(company, accountant, chief, client_for, account_of, customer):
    client = client_for(chief)
    first = client.post(ENTRIES, payload(company, account_of, description="Alpha"), format="json").json()
    client.post(ENTRIES, payload(company, account_of, description="Beta"), format="json")
    client.post(f"{ENTRIES}{first['id']}/post/")

    assert client.get(ENTRIES, {"status": "posted"}).json()["count"] == 1
    assert client.get(ENTRIES, {"q": "beta"}).json()["count"] == 1
    assert client.get(ENTRIES, {"date_from": "2026-12-01"}).json()["count"] == 0
    assert client.get(ENTRIES, {"status": "nonsense"}).status_code == 400

    # an old entry that lacks its customer: only possible from imported or legacy data
    legacy = JournalEntry.objects.create(
        company=company, date="2026-11-02", description="Legacy", created_by=chief
    )
    JournalLine.objects.create(entry=legacy, account=account_of(company, "102"), debit=10)
    flagged = client.get(ENTRIES, {"incomplete": "true"}).json()
    assert flagged["count"] == 1
    assert flagged["results"][0]["missing_partner_lines"] == 1


# ---------- accounts and partners ----------


def test_only_chief_manages_accounts(company, accountant, chief, client_for):
    body = {"code": "9001", "name": "Test", "type": "expense", "parent": None, "is_leaf": True}
    assert client_for(accountant).post("/api/v1/accounts/", body, format="json").status_code == 403
    assert client_for(chief).post("/api/v1/accounts/", body, format="json").status_code == 201
    duplicate = client_for(chief).post("/api/v1/accounts/", body, format="json")
    assert duplicate.status_code == 400


def test_account_code_may_repeat_across_companies(other_company, make_user, client_for, company):
    chief = make_user("boss2", other_company, Role.CHIEF)
    body = {"code": "7000", "name": "X", "type": "expense", "is_leaf": True}
    first = client_for(chief, other_company).post("/api/v1/accounts/", body, format="json")
    assert first.status_code == 201
    assert not Account.objects.filter(company=company, code="7000").exists()


def test_account_rules(company, chief, client_for, account_of):
    client = client_for(chief)

    # a child needs a non-leaf parent
    body = {"code": "9002", "name": "Child", "type": "asset", "parent": account_of(company, "102").pk}
    assert client.post("/api/v1/accounts/", body, format="json").status_code == 400

    # an account with no entries may become a parent
    unused = account_of(company, "109")
    unused_body = {"code": "109", "name": "Other", "type": "asset", "is_leaf": False}
    assert client.put(f"/api/v1/accounts/{unused.pk}/", unused_body, format="json").status_code == 200
    unused.refresh_from_db()
    assert not unused.is_leaf

    # but not once it has entries
    entry = client.post(ENTRIES, payload(company, account_of), format="json")
    assert entry.status_code == 201
    sales = account_of(company, "401")
    stay_leaf = {"code": "401", "name": "Sales", "type": "revenue", "is_leaf": False}
    assert client.put(f"/api/v1/accounts/{sales.pk}/", stay_leaf, format="json").status_code == 400

    # and an account that has children cannot be turned back into a leaf
    parent = account_of(company, "11")
    to_leaf = {"code": "11", "name": "Fixed assets", "type": "asset", "is_leaf": True}
    assert client.put(f"/api/v1/accounts/{parent.pk}/", to_leaf, format="json").status_code == 400


def test_partner_crud_and_protection(company, accountant, chief, client_for, account_of):
    client = client_for(accountant)
    created = client.post(
        "/api/v1/partners/", {"name": "Al Nour", "kind": "customer", "is_active": True}, format="json"
    )
    assert created.status_code == 201
    partner_id = created.json()["id"]
    assert client.delete(f"/api/v1/partners/{partner_id}/").status_code == 403

    partner = Partner.objects.get(pk=partner_id)
    body = {
        "date": "2026-11-01",
        "description": "Sale",
        "lines": [
            {"account": account_of(company, "102").pk, "debit": "10", "partner": partner_id},
            {"account": account_of(company, "401").pk, "credit": "10"},
        ],
    }
    assert client.post(ENTRIES, body, format="json").status_code == 201
    assert client_for(chief).delete(f"/api/v1/partners/{partner.pk}/").status_code == 409


# ---------- reports ----------


def test_reports_over_the_api(company, accountant, chief, client_for, account_of, customer):
    client = client_for(chief)
    body = {
        "date": "2026-11-01",
        "description": "Invoice",
        "lines": [
            {"account": account_of(company, "102").pk, "debit": "300", "partner": customer.pk},
            {"account": account_of(company, "401").pk, "credit": "300"},
        ],
    }
    entry = client.post(ENTRIES, body, format="json").json()
    client.post(f"{ENTRIES}{entry['id']}/post/")

    trial = client.get("/api/v1/reports/trial-balance/").json()
    assert trial["is_balanced"] is True
    assert trial["total_debit"] == "300.00"

    ledger = client.get("/api/v1/reports/general-ledger/", {"account": account_of(company, "102").pk}).json()
    assert ledger["ledgers"][0]["closing"] == {"amount": "300.00", "side": "debit"}

    statement = client.get("/api/v1/reports/partner-statement/", {"partner": customer.pk}).json()
    assert statement["partner"]["name"] == "Al Nour"
    assert statement["closing_posted"] == {"amount": "300.00", "side": "debit"}


def test_report_parameters_are_validated(company, chief, client_for, customer, other_company):
    client = client_for(chief)
    assert client.get("/api/v1/reports/partner-statement/").status_code == 400
    assert client.get("/api/v1/reports/trial-balance/", {"as_of": "not-a-date"}).status_code == 400
    reversed_dates = {"partner": customer.pk, "date_from": "2026-12-01", "date_to": "2026-01-01"}
    assert client.get("/api/v1/reports/partner-statement/", reversed_dates).status_code == 400
    foreign = Partner.objects.create(company=other_company, name="X", kind="customer")
    assert client.get("/api/v1/reports/partner-statement/", {"partner": foreign.pk}).status_code == 404
