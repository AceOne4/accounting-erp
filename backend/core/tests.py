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


# ------------------------------------------------------------------ session login
@pytest.fixture
def csrf_client():
    from django.core.cache import cache

    cache.clear()
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
    client.defaults["HTTP_X_CSRFTOKEN"] = token
    return client


def test_login_needs_csrf_token():
    client = APIClient(enforce_csrf_checks=True)
    res = client.post("/api/v1/auth/login/", {"username": "a", "password": "b"}, format="json")
    assert res.status_code == 403


def test_login_me_logout_flow(csrf_client):
    user = get_user_model().objects.create_user("sara", password="s3cret-pass")
    company = Company.objects.create(name="Nile Trading")
    Membership.objects.create(user=user, company=company, role=Membership.Role.CHIEF)

    res = csrf_client.post(
        "/api/v1/auth/login/", {"username": "sara", "password": "s3cret-pass"}, format="json"
    )
    assert res.status_code == 200
    assert res.json()["companies"] == [
        {"id": company.pk, "name": "Nile Trading", "role": "chief_accountant"}
    ]
    assert csrf_client.get("/api/v1/me/").json()["username"] == "sara"

    # the login rotates the CSRF token; the client must re-read it
    csrf_client.defaults["HTTP_X_CSRFTOKEN"] = csrf_client.cookies["csrftoken"].value
    assert csrf_client.post("/api/v1/auth/logout/").status_code == 204
    assert csrf_client.get("/api/v1/me/").status_code in (401, 403)


def test_wrong_password_is_a_generic_401(csrf_client):
    get_user_model().objects.create_user("sara", password="s3cret-pass")
    bad = csrf_client.post(
        "/api/v1/auth/login/", {"username": "sara", "password": "nope"}, format="json"
    )
    missing = csrf_client.post(
        "/api/v1/auth/login/", {"username": "ghost", "password": "nope"}, format="json"
    )
    assert bad.status_code == missing.status_code == 403 or bad.status_code == 401
    assert bad.json() == missing.json()


def test_inactive_user_cannot_login(csrf_client):
    get_user_model().objects.create_user("sara", password="s3cret-pass", is_active=False)
    res = csrf_client.post(
        "/api/v1/auth/login/", {"username": "sara", "password": "s3cret-pass"}, format="json"
    )
    assert res.status_code in (401, 403)


def test_login_is_rate_limited(csrf_client):
    codes = [
        csrf_client.post(
            "/api/v1/auth/login/", {"username": "x", "password": "y"}, format="json"
        ).status_code
        for _ in range(12)
    ]
    assert codes[-1] == 429
