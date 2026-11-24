import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounting.chart import seed_default_chart
from accounting.models import Account, Partner
from core.models import Company, Membership


@pytest.fixture(autouse=True)
def english_by_default():
    """Production defaults to Arabic; tests assert on English text unless they switch language."""
    from django.utils import translation

    with translation.override("en"):
        yield


@pytest.fixture
def company(db):
    company = Company.objects.create(name="Nile Trading")
    seed_default_chart(company)
    return company


@pytest.fixture
def other_company(db):
    company = Company.objects.create(name="Delta Foods")
    seed_default_chart(company)
    return company


@pytest.fixture
def make_user(db):
    def make(username, company, role):
        user, _ = get_user_model().objects.get_or_create(username=username)
        Membership.objects.update_or_create(user=user, company=company, defaults={"role": role})
        return user

    return make


@pytest.fixture
def client_for():
    def make(user, company=None):
        client = APIClient()
        client.defaults["HTTP_ACCEPT_LANGUAGE"] = "en"
        client.force_login(user)
        if company is not None:
            client.defaults["HTTP_X_COMPANY_ID"] = str(company.pk)
        return client

    return make


@pytest.fixture
def account_of():
    def get(company, code):
        return Account.objects.get(company=company, code=code)

    return get


@pytest.fixture
def customer(company):
    return Partner.objects.create(company=company, name="Al Nour", kind=Partner.Kind.CUSTOMER)
