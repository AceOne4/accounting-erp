from decimal import Decimal

import pytest

from accounting.models import JournalEntry
from core.models import Membership
from inventory import services
from inventory.models import InventoryLock, Product, StockReceipt, Unit, Warehouse

pytestmark = pytest.mark.django_db
Role = Membership.Role
B = "/api/v1/inventory/"


def receipt_body(main_wh, supplier, widget, qty="10", cost="2.50"):
    return {
        "date": "2026-11-01", "warehouse": main_wh.pk, "supplier": supplier.pk,
        "supplier_invoice": "INV-1",
        "lines": [{"product": widget.pk, "quantity": qty, "unit_cost": cost}],
    }


# ------------------------------------------------------------ master data
def test_master_data_roles(company, reviewer, accountant, sysadmin, unit, client_for):
    body = {"code": "P1", "name": "Pump", "unit": unit.pk}
    assert client_for(accountant, company).post(B + "products/", body, format="json").status_code == 403
    assert client_for(sysadmin, company).post(B + "products/", body, format="json").status_code == 403
    assert client_for(reviewer, company).post(B + "products/", body, format="json").status_code == 201
    services.release_lock(company)
    assert client_for(accountant, company).get(B + "products/").status_code == 200


def test_product_code_unique_per_company_and_immutable_after_moves(
    company, other_company, reviewer, unit, widget, receive, client_for
):
    client = client_for(reviewer, company)
    dup = client.post(B + "products/", {"code": "W1", "name": "Dup", "unit": unit.pk}, format="json")
    assert dup.status_code == 400
    # the same code is fine in another company
    other_unit = Unit.objects.create(company=other_company, name="Box")
    Product.objects.create(company=other_company, code="W1", name="Other", unit=other_unit)

    receive(widget, "1", "1")
    body = {"code": "CHANGED", "name": "Widget", "unit": unit.pk}
    assert client.put(f"{B}products/{widget.pk}/", body, format="json").status_code == 400
    body["code"] = "W1"
    body["name"] = "Widget v2"
    assert client.put(f"{B}products/{widget.pk}/", body, format="json").status_code == 200


def test_product_unit_must_belong_to_company(company, other_company, reviewer, client_for):
    foreign = Unit.objects.create(company=other_company, name="Foreign")
    r = client_for(reviewer, company).post(
        B + "products/", {"code": "P2", "name": "X", "unit": foreign.pk}, format="json"
    )
    assert r.status_code == 400


def test_product_delete_rules(company, reviewer, chief, unit, widget, receive, client_for):
    assert client_for(reviewer, company).delete(f"{B}products/{widget.pk}/").status_code == 403
    receive(widget, "1", "1")
    assert client_for(chief, company).delete(f"{B}products/{widget.pk}/").status_code == 409
    spare = Product.objects.create(company=company, code="S", name="Spare", unit=unit)
    assert client_for(chief, company).delete(f"{B}products/{spare.pk}/").status_code == 204


def test_product_search_and_tenant_isolation(
    company, other_company, chief, make_user, widget, gadget, unit, client_for
):
    client = client_for(chief, company)
    assert [p["code"] for p in client.get(B + "products/?q=gadg").json()["results"]] == ["G1"]
    outsider = make_user("out", other_company, Role.CHIEF)
    assert client_for(outsider, other_company).get(B + "products/").json()["results"] == []
    assert client_for(outsider, other_company).get(f"{B}products/{widget.pk}/").status_code == 404


# --------------------------------------------------------------- receipts
def test_receipt_lifecycle(company, reviewer, chief, accountant, main_wh, supplier, widget, client_for):
    body = receipt_body(main_wh, supplier, widget)
    assert client_for(accountant, company).post(B + "receipts/", body, format="json").status_code == 403

    created = client_for(reviewer, company).post(B + "receipts/", body, format="json")
    assert created.status_code == 201
    data = created.json()
    assert data["number"].startswith("RC-")
    assert data["total_cost"] == "25.00" and data["journal_entry_status"] == "draft"
    assert data["lines"][0]["line_total"] == "25.00" and data["locked_reason"] == ""

    changed = receipt_body(main_wh, supplier, widget, qty="4", cost="3.00")
    updated = client_for(reviewer, company).put(f"{B}receipts/{data['id']}/", changed, format="json")
    assert updated.status_code == 200 and updated.json()["total_cost"] == "12.00"

    # only the chief accountant can delete
    assert client_for(reviewer, company).delete(f"{B}receipts/{data['id']}/").status_code == 403
    assert client_for(chief, company).delete(f"{B}receipts/{data['id']}/").status_code == 204
    assert not StockReceipt.objects.exists() and not JournalEntry.objects.exists()


def test_posted_receipt_cannot_change(company, reviewer, chief, main_wh, supplier, widget, receive, client_for):
    receipt = receive(widget, "10", "2")
    from accounting import services as accounting

    accounting.post_entry(entry=receipt.journal_entry, user=chief)
    r = client_for(reviewer, company).put(
        f"{B}receipts/{receipt.pk}/", receipt_body(main_wh, supplier, widget), format="json"
    )
    assert r.status_code == 400
    assert client_for(chief, company).delete(f"{B}receipts/{receipt.pk}/").status_code == 400
    detail = client_for(chief, company).get(f"{B}receipts/{receipt.pk}/").json()
    assert detail["locked_reason"]


def test_receipt_validation_errors_are_400(company, reviewer, main_wh, supplier, widget, client_for):
    client = client_for(reviewer, company)
    body = receipt_body(main_wh, supplier, widget)
    assert client.post(B + "receipts/", {**body, "lines": []}, format="json").status_code == 400
    bad = receipt_body(main_wh, supplier, widget, qty="1.0005")
    assert client.post(B + "receipts/", bad, format="json").status_code == 400
    assert not StockReceipt.objects.exists()


def test_receipt_rejects_other_companys_objects(
    company, other_company, reviewer, main_wh, supplier, widget, client_for
):
    foreign_wh = Warehouse.objects.create(company=other_company, code="X", name="X")
    body = receipt_body(foreign_wh, supplier, widget)
    assert client_for(reviewer, company).post(B + "receipts/", body, format="json").status_code == 400


# -------------------------------------------------------------- transfers
def test_transfer_api(company, reviewer, chief, accountant, main_wh, second_wh, widget, receive, client_for):
    receive(widget, "10", "2")
    body = {
        "date": "2026-11-05", "from_warehouse": main_wh.pk, "to_warehouse": second_wh.pk,
        "lines": [{"product": widget.pk, "quantity": "4"}],
    }
    assert client_for(accountant, company).post(B + "transfers/", body, format="json").status_code == 403
    created = client_for(reviewer, company).post(B + "transfers/", body, format="json")
    assert created.status_code == 201 and created.json()["number"].startswith("TR-")

    too_much = {**body, "lines": [{"product": widget.pk, "quantity": "100"}]}
    r = client_for(reviewer, company).post(B + "transfers/", too_much, format="json")
    assert r.status_code == 400

    same = {**body, "to_warehouse": main_wh.pk}
    assert client_for(reviewer, company).post(B + "transfers/", same, format="json").status_code == 400

    assert client_for(reviewer, company).delete(f"{B}transfers/{created.json()['id']}/").status_code == 403
    assert client_for(chief, company).delete(f"{B}transfers/{created.json()['id']}/").status_code == 204
    assert services.available_qty(widget.pk, main_wh.pk) == Decimal("10")


# ------------------------------------------------------------------ counts
def test_count_api(company, accountant, reviewer, main_wh, widget, receive, client_for):
    receive(widget, "10", "2")
    body = {"warehouse": main_wh.pk, "lines": [{"product": widget.pk, "counted_qty": "8"}]}
    assert client_for(reviewer, company).post(B + "counts/", body, format="json").status_code == 403
    r = client_for(accountant, company).post(B + "counts/", body, format="json")
    assert r.status_code == 201
    services.release_lock(company)  # the accountant is done; the reviewer reads next
    line = r.json()["lines"][0]
    assert (line["book_qty"], line["counted_qty"], line["difference"]) == ("10.000", "8.000", "-2.000")
    assert len(client_for(reviewer, company).get(B + "counts/").json()["results"]) == 1
    services.release_lock(company)
    empty = {"warehouse": main_wh.pk, "lines": []}
    assert client_for(accountant, company).post(B + "counts/", empty, format="json").status_code == 400


# ----------------------------------------------------------------- reports
def test_report_endpoints(company, chief, widget, main_wh, second_wh, receive, client_for):
    receive(widget, "10", "2")
    client = client_for(chief, company)
    levels = client.get(B + "reports/stock-levels/").json()
    assert levels["stock_total"] == "20.00" and levels["rows"][0]["avg_cost"] == "2.0000"
    assert levels["ledger"]["difference"] == "0.00"

    card = client.get(f"{B}reports/item-card/?product={widget.pk}").json()
    assert card["rows"][0]["qty_in"] == "10.000" and card["rows"][0]["balance_value"] == "20.00"

    assert client.get(B + "reports/item-card/").status_code == 400
    assert client.get(f"{B}reports/stock-levels/?warehouse=999999").status_code == 404


def test_reports_do_not_leak_across_companies(
    company, other_company, make_user, widget, receive, client_for
):
    receive(widget, "10", "2")
    outsider = make_user("out", other_company, Role.CHIEF)
    client = client_for(outsider, other_company)
    assert client.get(B + "reports/stock-levels/").json()["rows"] == []
    assert client.get(f"{B}reports/item-card/?product={widget.pk}").status_code == 404


# -------------------------------------------------------------------- lock
def test_second_user_is_locked_out_until_release(
    company, chief, reviewer, accountant, client_for
):
    first = client_for(reviewer, company)
    assert first.get(B + "warehouses/").status_code == 200  # reviewer takes the lock

    blocked = client_for(accountant, company).get(B + "warehouses/")
    assert blocked.status_code == 423
    assert blocked.json()["holder"] == "rana" and blocked.json()["minutes_left"] >= 1

    # the lock status endpoint never takes the lock and is always readable
    status = client_for(accountant, company).get(B + "lock/").json()
    assert status["locked"] and not status["held_by_me"] and status["holder"] == "rana"

    # the chief accountant can always enter
    assert client_for(chief, company).get(B + "warehouses/").status_code == 200

    # leaving the module frees it
    assert first.post(B + "lock/release/").status_code == 200
    assert client_for(accountant, company).get(B + "warehouses/").status_code == 200


def test_force_release_needs_override(company, reviewer, accountant, chief, client_for):
    client_for(reviewer, company).get(B + "warehouses/")
    assert client_for(accountant, company).post(B + "lock/force-release/").status_code == 403
    assert client_for(chief, company).post(B + "lock/force-release/").json()["locked"] is False
    assert client_for(accountant, company).get(B + "warehouses/").status_code == 200


def test_idle_lock_expires(company, reviewer, accountant, client_for):
    client_for(reviewer, company).get(B + "warehouses/")
    InventoryLock.objects.update(
        last_activity=InventoryLock.objects.get().last_activity - services.timedelta(minutes=16)
    )
    assert client_for(accountant, company).get(B + "warehouses/").status_code == 200


def test_lock_is_per_company(company, other_company, reviewer, make_user, client_for):
    client_for(reviewer, company).get(B + "warehouses/")
    other = make_user("zed", other_company, Role.REVIEWER)
    assert client_for(other, other_company).get(B + "warehouses/").status_code == 200


def test_treasury_and_accounting_ignore_the_inventory_lock(company, reviewer, accountant, client_for):
    client_for(reviewer, company).get(B + "warehouses/")
    assert client_for(accountant, company).get("/api/v1/accounts/").status_code == 200
