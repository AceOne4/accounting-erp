import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import Company, Membership

pytestmark = pytest.mark.django_db


def test_health_is_public():
    res = APIClient().get("/api/v1/health/")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_me_requires_login():
    assert APIClient().get("/api/v1/me/").status_code in (401, 403)


def test_me_lists_only_own_companies():
    User = get_user_model()
    user = User.objects.create_user("sara", password="x")
    other = User.objects.create_user("omar", password="x")
    mine = Company.objects.create(name="Nile Trading")
    theirs = Company.objects.create(name="Delta Foods")
    Membership.objects.create(user=user, company=mine, role=Membership.Role.REVIEWER)
    Membership.objects.create(user=other, company=theirs, role=Membership.Role.ACCOUNTANT)

    client = APIClient()
    client.force_login(user)
    data = client.get("/api/v1/me/").json()
    assert data["companies"] == [{"id": mine.id, "name": "Nile Trading", "role": "reviewer"}]


def test_one_membership_per_user_and_company():
    user = get_user_model().objects.create_user("sara", password="x")
    company = Company.objects.create(name="Nile Trading")
    Membership.objects.create(user=user, company=company, role="reviewer")
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(user=user, company=company, role="accountant")


def test_openapi_schema_builds():
    res = APIClient().get("/api/schema/")
    assert res.status_code == 200
    assert b"/api/v1/health/" in res.content
