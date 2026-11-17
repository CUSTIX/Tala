import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.demo import create_demo_teacher, purge_expired

ROOT = Path(settings.BASE_DIR)


@pytest.mark.django_db
def test_home_page_offers_the_demo(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Try the demo" in response.content


@pytest.mark.django_db
def test_signed_in_home_goes_to_dashboard(signed_in):
    assert signed_in.get("/")["Location"] == reverse("classroom:dashboard")


@pytest.mark.django_db
def test_security_headers(client):
    response = client.get("/")
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert "camera=(self)" in response["Permissions-Policy"]
    assert response["X-Frame-Options"] == "DENY"


def test_no_inline_script_or_style_in_templates():
    """The CSP blocks inline JS and inline styles; this keeps templates honest."""
    for path in ROOT.glob("*/templates/**/*.html"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", text) or "json_script" in text, path
        assert not re.search(r"\son[a-z]+=", text), f"inline event handler in {path}"
        assert " style=" not in text, f"inline style in {path}"


@pytest.mark.django_db
def test_demo_creates_a_private_teacher_and_signs_in(client):
    response = client.post(reverse("accounts:demo"))
    assert response["Location"] == reverse("classroom:dashboard")
    user = get_user_model().objects.get(is_demo=True)
    assert user.sections.count() == 3
    assert not user.has_usable_password()
    dashboard = client.get(reverse("classroom:dashboard"))
    assert b"Grade 7 - Sampaguita" in dashboard.content and b"DEMO" in dashboard.content
    # A second click while signed in reuses the same demo.
    client.post(reverse("accounts:demo"))
    assert get_user_model().objects.filter(is_demo=True).count() == 1


@pytest.mark.django_db
def test_demo_is_rate_limited_per_ip(client, settings):
    settings.DEMO_ACCOUNTS_PER_HOUR = 1
    assert client.post(reverse("accounts:demo")).status_code == 302
    client.logout()
    assert client.post(reverse("accounts:demo")).status_code == 429


@pytest.mark.django_db
def test_demo_needs_post(client):
    assert client.get(reverse("accounts:demo")).status_code == 405


@pytest.mark.django_db
def test_purge_deletes_only_expired_demo_accounts(teacher):
    import datetime as dt

    from django.utils import timezone

    old = create_demo_teacher(seed=1)
    old.date_joined = timezone.now() - dt.timedelta(hours=30)
    old.save()
    fresh = create_demo_teacher(seed=2)
    assert purge_expired(24) == 1
    assert set(get_user_model().objects.values_list("pk", flat=True)) == {teacher.pk, fresh.pk}


@pytest.mark.django_db
def test_login_is_rate_limited(client, settings):
    settings.LOGINS_PER_WINDOW = 2
    url = reverse("accounts:login")
    for _ in range(2):
        assert client.post(url, {"username": "x", "password": "y"}).status_code == 200
    assert client.post(url, {"username": "x", "password": "y"}).status_code == 429


@pytest.mark.django_db
def test_real_teacher_can_sign_in(client, teacher):
    response = client.post(
        reverse("accounts:login"), {"username": "ana", "password": "pw-not-used-1"}
    )
    assert response["Location"] == reverse("classroom:dashboard")


@pytest.mark.django_db
def test_health_endpoints(client):
    assert client.get("/livez/").content == b"ok"
    assert client.get("/healthz/").content == b"ok"


@pytest.mark.django_db
def test_404_page_is_friendly(client):
    response = client.get("/nope/")
    assert response.status_code == 404
