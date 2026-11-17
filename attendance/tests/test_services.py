import pytest
from django.core.exceptions import ValidationError

from attendance import selectors, services
from attendance.models import Mark, Via
from classroom.models import Section


@pytest.mark.django_db
def test_save_marks_creates_updates_and_clears(section, learners, monday):
    a, b, c, _ = learners
    services.save_marks(section, monday, {a.pk: "P", b.pk: "L", c.pk: "A"}, Via.LIST)
    services.save_marks(section, monday, {a.pk: "E", b.pk: ""}, Via.SEATS)
    assert selectors.statuses_on(section, monday) == {a.pk: "E", c.pk: "A"}
    assert Mark.objects.get(learner=a).via == Via.SEATS


@pytest.mark.django_db
def test_save_marks_refuses_other_learners_and_bad_status(section, learners, monday, other_teacher):
    other = Section.objects.create(teacher=other_teacher, name="X", subject="Y")
    with pytest.raises(ValidationError):
        services.save_marks(other, monday, {learners[0].pk: "P"}, Via.LIST)
    with pytest.raises(ValidationError):
        services.save_marks(section, monday, {learners[0].pk: "Z"}, Via.LIST)
    with pytest.raises(ValidationError):
        services.save_marks(section, monday, {learners[0].pk: "P"}, "telepathy")


@pytest.mark.django_db
def test_qr_marks_present_or_late_and_refuses_other_classes(
    section, learners, monday, other_teacher
):
    juan = learners[0]
    assert services.mark_by_qr(section, monday, f"TALA:{juan.qr_code}") == juan
    assert selectors.statuses_on(section, monday)[juan.pk] == "P"
    services.mark_by_qr(section, monday, juan.qr_code, late=True)
    assert selectors.statuses_on(section, monday)[juan.pk] == "L"
    other = Section.objects.create(teacher=other_teacher, name="X", subject="Y")
    with pytest.raises(ValidationError):
        services.mark_by_qr(other, monday, f"TALA:{juan.qr_code}")
    with pytest.raises(ValidationError):
        services.mark_by_qr(section, monday, "TALA:nope")


@pytest.mark.django_db
def test_mark_rest_absent_only_fills_unmarked(section, learners, monday):
    services.save_marks(section, monday, {learners[0].pk: "P"}, Via.LIST)
    assert services.mark_rest_absent(section, monday) == 3
    statuses = selectors.statuses_on(section, monday)
    assert statuses[learners[0].pk] == "P"
    assert list(statuses.values()).count("A") == 3


@pytest.mark.django_db
def test_month_report_and_rates(section, learners, monday):
    import datetime as dt

    a = learners[0]
    services.save_marks(section, monday, {a.pk: "P"}, Via.LIST)
    services.save_marks(section, monday + dt.timedelta(days=1), {a.pk: "A"}, Via.LIST)
    services.save_marks(section, monday + dt.timedelta(days=2), {a.pk: "E"}, Via.LIST)
    report = selectors.month_report(section, monday)
    row = next(r for r in report.rows if r.learner == a)
    assert row.cells == ["P", "A", "E"]
    assert row.totals == {"P": 1, "A": 1, "E": 1}
    assert report.previous.month == 10 and report.next.month == 12
    assert selectors.section_rates(section)[a.pk] == 50, "excused days don't count against"
    assert selectors.learner_totals(a) == {
        "present": 1,
        "late": 0,
        "excused": 1,
        "absent": 1,
        "days": 3,
    }
