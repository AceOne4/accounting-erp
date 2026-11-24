from decimal import Decimal

import pytest

from accounting.models import Partner
from core.models import Membership
from inventory import services
from inventory.models import Product, Unit, Warehouse

Role = Membership.Role


@pytest.fixture
def chief(make_user, company):
    return make_user("chief", company, Role.CHIEF)


@pytest.fixture
def accountant(make_user, company):
    return make_user("amr", company, Role.ACCOUNTANT)


@pytest.fixture
def reviewer(make_user, company):
    return make_user("rana", company, Role.REVIEWER)


@pytest.fixture
def sysadmin(make_user, company):
    return make_user("root", company, Role.ADMIN)


@pytest.fixture
def unit(company):
    return Unit.objects.create(company=company, name="Piece", name_en="Piece")


@pytest.fixture
def main_wh(company):
    return Warehouse.objects.create(company=company, code="MAIN", name="Main")


@pytest.fixture
def second_wh(company):
    return Warehouse.objects.create(company=company, code="B2", name="Branch")


@pytest.fixture
def widget(company, unit):
    return Product.objects.create(company=company, code="W1", name="Widget", unit=unit)


@pytest.fixture
def gadget(company, unit):
    return Product.objects.create(company=company, code="G1", name="Gadget", unit=unit)


@pytest.fixture
def supplier(company):
    return Partner.objects.create(company=company, name="Delta", kind=Partner.Kind.SUPPLIER)


@pytest.fixture
def receive(company, chief, main_wh, supplier):
    def make(product, qty, cost, date="2026-11-01", warehouse=None):
        return services.create_receipt(
            company=company, user=chief, date=date, warehouse=warehouse or main_wh,
            supplier=supplier,
            lines=[services.ReceiptLineInput(product, Decimal(qty), Decimal(cost))],
        )

    return make
