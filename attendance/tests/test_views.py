import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from attendance import selectors


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["seats", "list", "roll"])
def test_take_page_in_each_mode(signed_in, section, learners, mode):
    response = signed_in.get(reverse("attendance:take", args=[section.pk]), {"mode": mode})
    assert response.status_code == 200
    assert b'name="s-' in response.content, "radio buttons always exist (works without JS)"


@pytest.mark.django_db
def test_save_attendance_for_a_past_day(signed_in, section, learners):
    day = timezone.localdate() - dt.timedelta(days=2)
    juan, paolo = learners[:2]
    response = signed_in.post(
        reverse("attendance:take", args=[section.pk]),
        {"date": day.isoformat(), "mode": "seats", f"s-{juan.pk}": "P", f"s-{paolo.pk}": "A"},
    )
    assert response.status_code == 302
    assert selectors.statuses_on(section, day) == {juan.pk: "P", paolo.pk: "A"}


@pytest.mark.django_db
def test_future_dates_become_today(signed_in, section, learners):
    future = timezone.localdate() + dt.timedelta(days=5)
    signed_in.post(
        reverse("attendance:take", args=[section.pk]),
        {"date": future.isoformat(), f"s-{learners[0].pk}": "P"},
    )
    assert selectors.statuses_on(section, timezone.localdate()) == {learners[0].pk: "P"}
    assert (
        signed_in.get(
            reverse("attendance:take", args=[section.pk]), {"date": "not-a-date"}
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_rest_absent(signed_in, section, learners):
    signed_in.post(reverse("attendance:take", args=[section.pk]), {"action": "rest_absent"})
    assert len(selectors.statuses_on(section, timezone.localdate())) == 4


@pytest.mark.django_db
def test_bad_status_is_reported_not_saved(signed_in, section, learners):
    signed_in.post(reverse("attendance:take", args=[section.pk]), {f"s-{learners[0].pk}": "Z"})
    assert selectors.statuses_on(section, timezone.localdate()) == {}


@pytest.mark.django_db
def test_scan_marks_today_and_returns_json(signed_in, section, learners):
    juan = learners[0]
    url = reverse("attendance:scan_mark", args=[section.pk])
    data = signed_in.post(url, {"code": f"TALA:{juan.qr_code}"}).json()
    assert data == {"name": "Juan Cruz", "status": "Present", "marked": 1}
    data = signed_in.post(url, {"code": f"TALA:{juan.qr_code}", "late": "1"}).json()
    assert data["status"] == "Late"
    response = signed_in.post(url, {"code": "TALA:unknown"})
    assert response.status_code == 404 and "error" in response.json()
    assert signed_in.get(reverse("attendance:scan", args=[section.pk])).status_code == 200


@pytest.mark.django_db
def test_monthly_report_and_csv(signed_in, section, learners):
    today = timezone.localdate()
    signed_in.post(reverse("attendance:take", args=[section.pk]), {f"s-{learners[0].pk}": "P"})
    url = reverse("attendance:report", args=[section.pk])
    page = signed_in.get(url, {"month": today.strftime("%Y-%m")})
    assert page.status_code == 200 and b"st-P" in page.content
    csv = signed_in.get(url, {"month": today.strftime("%Y-%m"), "format": "csv"})
    assert csv["Content-Type"] == "text/csv"
    lines = csv.content.decode().splitlines()
    assert lines[0].startswith("Learner,Sex,") and "Cruz, Juan" in lines[1]
    assert signed_in.get(url, {"month": "garbage"}).status_code == 200
