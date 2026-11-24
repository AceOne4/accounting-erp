from decimal import Decimal

import pytest

from accounting import services as accounting
from accounting.models import JournalEntry
from core.models import Membership
from inventory import services as inventory
from treasury import services as treasury

pytestmark = pytest.mark.django_db
Role = Membership.Role


@pytest.fixture
def chief(make_user, company):
    return make_user("chief", company, Role.CHIEF)


@pytest.fixture
def receipt(company, chief):
    from accounting.models import Partner
    from inventory.models import Product, Unit, Warehouse

    unit = Unit.objects.create(company=company, name="Piece")
    product = Product.objects.create(company=company, code="W", name="W", unit=unit)
    wh = Warehouse.objects.create(company=company, code="M", name="Main")
    supplier = Partner.objects.create(company=company, name="D", kind="supplier")
    return inventory.create_receipt(
        company=company, user=chief, date="2026-11-01", warehouse=wh, supplier=supplier,
        lines=[inventory.ReceiptLineInput(product, Decimal("2"), Decimal("5"))],
    )


def edit_body(account_of, company):
    return {
        "date": "2026-11-02", "description": "hacked",
        "lines": [
            {"account": account_of(company, "1012").pk, "debit": "10.00"},
            {"account": account_of(company, "401").pk, "credit": "10.00"},
        ],
    }


def test_receipt_entry_cannot_be_edited_or_deleted_directly(company, chief, receipt, account_of, client_for):
    client = client_for(chief, company)
    url = f"/api/v1/journal-entries/{receipt.journal_entry_id}/"
    assert receipt.journal_entry.source == "receipt"
    assert client.put(url, edit_body(account_of, company), format="json").status_code == 400
    assert client.delete(url).status_code == 400
    assert client.get(url).json()["source"] == "receipt"
    assert JournalEntry.objects.get(pk=receipt.journal_entry_id).description != "hacked"


def test_linked_entry_can_still_be_posted(company, chief, receipt, client_for):
    r = client_for(chief, company).post(f"/api/v1/journal-entries/{receipt.journal_entry_id}/post/")
    assert r.status_code == 200 and r.json()["status"] == "posted"


def test_receipt_still_manages_its_own_entry(company, chief, receipt):
    from inventory.models import Warehouse

    inventory.update_receipt(
        receipt=receipt, date="2026-11-03", warehouse=Warehouse.objects.get(company=company),
        supplier=receipt.supplier,
        lines=[inventory.ReceiptLineInput(receipt.lines.first().product, Decimal("1"), Decimal("4"))],
    )
    receipt.refresh_from_db()
    assert receipt.journal_entry.date.isoformat() == "2026-11-03"
    inventory.delete_receipt(receipt=receipt)
    assert not JournalEntry.objects.exists()


def test_cash_count_adjustment_is_locked_for_edit_but_can_be_dropped(company, chief, account_of, client_for):
    treasury.create_voucher(company=company, user=chief, kind="fund", date="2026-11-01", amount="100.00", post_now=True)
    count = treasury.record_cash_count(
        company=company, user=chief, box=account_of(company, "1011"), count_date="2026-11-02",
        quantities={"50": 1}, adjust=True,
    )
    client = client_for(chief, company)
    url = f"/api/v1/journal-entries/{count.entry_id}/"
    assert client.put(url, edit_body(account_of, company), format="json").status_code == 400
    assert client.delete(url).status_code == 204
    count.refresh_from_db()
    assert count.entry is None  # the count record survives


def test_manual_and_voucher_entries_stay_editable(company, chief, account_of, client_for):
    entry, *_ = treasury.create_voucher(company=company, user=chief, kind="deposit", date="2026-11-01", amount="10.00")
    assert entry.source == ""
    r = client_for(chief, company).put(f"/api/v1/journal-entries/{entry.pk}/", edit_body(account_of, company), format="json")
    assert r.status_code == 200
