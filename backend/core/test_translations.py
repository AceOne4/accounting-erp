import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def wrong_login(lang):
    cache.clear()
    return APIClient().post(
        "/api/v1/auth/token/", {"username": "x", "password": "y"}, format="json",
        HTTP_ACCEPT_LANGUAGE=lang,
    ).json()["detail"]


def test_api_messages_follow_accept_language():
    assert wrong_login("en") == "Wrong username or password"
    assert wrong_login("ar") == "اسم المستخدم أو كلمة المرور غير صحيحة"


def test_service_errors_are_translated(company, make_user, client_for):
    chief = make_user("chief", company, "chief_accountant")
    client = client_for(chief, company)
    body = {"kind": "deposit", "date": "2026-11-01", "amount": "0"}
    ar = client.post("/api/v1/treasury/vouchers/", body, format="json", HTTP_ACCEPT_LANGUAGE="ar")
    en = client.post("/api/v1/treasury/vouchers/", body, format="json", HTTP_ACCEPT_LANGUAGE="en")
    assert ar.status_code == en.status_code == 400
    assert "المبلغ" in str(ar.json()) and "amount" in str(en.json()).lower()


def test_every_message_is_translated():
    import subprocess, sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    done = subprocess.run([sys.executable, "scripts/make_messages.py", "--check"], cwd=root, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout
