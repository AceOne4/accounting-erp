import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from core.models import Membership

pytestmark = pytest.mark.django_db
Role = Membership.Role
U = "/api/v1/users/"
User = get_user_model()


@pytest.fixture
def admin(make_user, company):
    return make_user("root", company, Role.ADMIN)


@pytest.fixture
def new_user_body():
    return {"username": "mona", "first_name": "Mona", "password": "Str0ng-pass-91", "role": "accountant"}


def test_only_admin_manages_users(company, make_user, client_for, admin):
    for name, role in (("a", Role.ACCOUNTANT), ("r", Role.REVIEWER), ("c", Role.CHIEF)):
        user = make_user(name, company, role)
        assert client_for(user, company).get(U).status_code == 403
    assert client_for(admin, company).get(U).status_code == 200


def test_create_user_and_login(company, admin, client_for, new_user_body):
    r = client_for(admin, company).post(U, new_user_body, format="json")
    assert r.status_code == 201 and r.json()["role"] == "accountant"
    created = User.objects.get(username="mona")
    assert created.check_password("Str0ng-pass-91")
    assert Membership.objects.get(user=created).company == company

    cache.clear()
    client = APIClient()
    assert client.post("/api/v1/auth/token/", {"username": "mona", "password": "Str0ng-pass-91"}, format="json").status_code == 200


def test_create_rejects_weak_password_and_duplicates(company, admin, client_for, new_user_body):
    client = client_for(admin, company)
    assert client.post(U, {**new_user_body, "password": "123"}, format="json").status_code == 400
    assert client.post(U, new_user_body, format="json").status_code == 201
    assert client.post(U, new_user_body, format="json").status_code == 400  # taken
    assert client.post(U, {**new_user_body, "username": "MONA"}, format="json").status_code == 400
    assert client.post(U, {**new_user_body, "username": "x", "role": "god"}, format="json").status_code == 400


def test_list_is_company_scoped(company, other_company, admin, make_user, client_for):
    make_user("elsewhere", other_company, Role.ACCOUNTANT)
    names = [m["username"] for m in client_for(admin, company).get(U).json()]
    assert names == ["root"]


def test_change_role_and_not_own(company, admin, make_user, client_for):
    target = make_user("sam", company, Role.ACCOUNTANT)
    m = Membership.objects.get(user=target)
    client = client_for(admin, company)
    r = client.post(f"{U}{m.pk}/role/", {"role": "reviewer"}, format="json")
    assert r.status_code == 200 and r.json()["role"] == "reviewer"
    own = Membership.objects.get(user=admin)
    assert client.post(f"{U}{own.pk}/role/", {"role": "accountant"}, format="json").status_code == 400
    assert client.delete(f"{U}{own.pk}/").status_code == 400


def test_cannot_touch_another_companys_member(company, other_company, admin, make_user, client_for):
    outsider = make_user("out", other_company, Role.ACCOUNTANT)
    m = Membership.objects.get(user=outsider)
    client = client_for(admin, company)
    assert client.post(f"{U}{m.pk}/role/", {"role": "chief_accountant"}, format="json").status_code == 404
    assert client.delete(f"{U}{m.pk}/").status_code == 404
    assert client.post(f"{U}{m.pk}/password/", {"password": "Str0ng-pass-91"}, format="json").status_code == 404


def test_remove_member(company, admin, make_user, client_for):
    target = make_user("sam", company, Role.ACCOUNTANT)
    m = Membership.objects.get(user=target)
    assert client_for(admin, company).delete(f"{U}{m.pk}/").status_code == 204
    assert not Membership.objects.filter(pk=m.pk).exists()


def test_reset_password_only_for_single_company_users(company, other_company, admin, make_user, client_for):
    single = make_user("sam", company, Role.ACCOUNTANT)
    shared = make_user("dual", company, Role.ACCOUNTANT)
    Membership.objects.create(user=shared, company=other_company, role=Role.ACCOUNTANT)
    client = client_for(admin, company)

    ok = client.post(f"{U}{Membership.objects.get(user=single).pk}/password/", {"password": "Another-str0ng-7"}, format="json")
    assert ok.status_code == 204 and User.objects.get(pk=single.pk).check_password("Another-str0ng-7")
    refused = client.post(f"{U}{Membership.objects.get(user=shared, company=company).pk}/password/", {"password": "Another-str0ng-7"}, format="json")
    assert refused.status_code == 400
    weak = client.post(f"{U}{Membership.objects.get(user=single).pk}/password/", {"password": "1"}, format="json")
    assert weak.status_code == 400


# ------------------------------------------------------------------ token auth
def test_token_login_and_use(company, make_user):
    cache.clear()
    user = make_user("tok", company, Role.CHIEF)
    user.set_password("pass-Word-123")
    user.save()
    client = APIClient()
    r = client.post("/api/v1/auth/token/", {"username": "tok", "password": "pass-Word-123"}, format="json")
    assert r.status_code == 200
    key = r.json()["token"]

    api = APIClient()  # no session, no CSRF: the token alone authenticates
    api.credentials(HTTP_AUTHORIZATION=f"Token {key}")
    assert api.get("/api/v1/me/").json()["username"] == "tok"
    assert api.get("/api/v1/accounts/").status_code == 200

    assert api.post("/api/v1/auth/token/revoke/").status_code == 204
    assert api.get("/api/v1/me/").status_code in (401, 403)


def test_token_login_rejects_bad_password(company, make_user):
    cache.clear()
    make_user("tok", company, Role.CHIEF)
    r = APIClient().post("/api/v1/auth/token/", {"username": "tok", "password": "nope"}, format="json")
    assert r.status_code in (401, 403)
