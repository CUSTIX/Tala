import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from grades.models import Assessment


@pytest.fixture
def quiz(section):
    return Assessment.objects.create(
        section=section,
        quarter=1,
        component="WW",
        title="Quiz 1",
        max_score=Decimal(20),
        date=dt.date(2026, 9, 1),
    )


@pytest.mark.django_db
def test_add_assessment_then_enter_scores(signed_in, section, learners):
    response = signed_in.post(
        reverse("grades:create", args=[section.pk]),
        {
            "quarter": 1,
            "component": "WW",
            "title": "Quiz 1",
            "max_score": "20",
            "date": "2026-09-01",
        },
    )
    quiz = Assessment.objects.get(section=section)
    assert response["Location"] == reverse("grades:scores", args=[section.pk, quiz.pk])
    signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]),
        {f"r-{learners[0].pk}": "18", f"r-{learners[1].pk}": "12.5", f"r-{learners[2].pk}": ""},
    )
    assert dict(quiz.scores.values_list("learner_id", "raw")) == {
        learners[0].pk: Decimal(18),
        learners[1].pk: Decimal("12.5"),
    }


@pytest.mark.django_db
def test_assessment_needs_a_score_or_items(signed_in, section):
    response = signed_in.post(
        reverse("grades:create", args=[section.pk]),
        {"quarter": 1, "component": "WW", "title": "Quiz", "date": "2026-09-01"},
    )
    assert response.status_code == 200
    assert not Assessment.objects.exists()


@pytest.mark.django_db
def test_bad_scores_are_reported_and_kept_in_the_form(signed_in, section, learners, quiz):
    response = signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{learners[0].pk}": "abc"}
    )
    assert response.status_code == 200 and b"is not a number" in response.content
    response = signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{learners[0].pk}": "25"}
    )
    assert b"between 0 and 20" in response.content
    assert not quiz.scores.exists()


@pytest.mark.django_db
def test_gradebook_shows_grades_and_exports_csv(signed_in, section, learners, quiz):
    signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{learners[0].pk}": "20"}
    )
    page = signed_in.get(reverse("grades:book", args=[section.pk]), {"q": 1})
    assert page.status_code == 200 and b"SO FAR" in page.content
    csv = signed_in.get(reverse("grades:book", args=[section.pk]), {"q": 1, "format": "csv"})
    rows = csv.content.decode().splitlines()
    assert "WW Quiz 1 (20)" in rows[0]
    assert rows[1].startswith('"Cruz, Juan",M,20.00,100.00,40.00')
    assert signed_in.get(reverse("grades:final", args=[section.pk])).status_code == 200
    assert signed_in.get(reverse("grades:book", args=[section.pk]), {"q": "x"}).status_code == 200


@pytest.mark.django_db
def test_items_answers_and_analysis_flow(signed_in, section, learners):
    response = signed_in.post(
        reverse("grades:create", args=[section.pk]),
        {"quarter": 1, "component": "WW", "title": "Quiz 2", "items": "3", "date": "2026-09-02"},
    )
    quiz = Assessment.objects.get(title="Quiz 2")
    assert quiz.max_score == 3
    assert response["Location"] == reverse("grades:items", args=[section.pk, quiz.pk])
    signed_in.post(
        reverse("grades:items", args=[section.pk, quiz.pk]),
        {"competencies": "Cells\nCells\nMicroscope"},
    )
    items = list(quiz.items.all())
    juan, paolo = learners[:2]
    response = signed_in.post(
        reverse("grades:responses", args=[section.pk, quiz.pk]),
        {
            f"t-{juan.pk}": "1",
            f"c-{juan.pk}-{items[0].pk}": "1",
            f"c-{juan.pk}-{items[1].pk}": "1",
            f"t-{paolo.pk}": "1",
            f"c-{paolo.pk}-{items[2].pk}": "1",
            # Andrea didn't take it; a ticked answer for her is ignored.
            f"c-{learners[2].pk}-{items[0].pk}": "1",
        },
    )
    assert response["Location"] == reverse("grades:analysis", args=[section.pk, quiz.pk])
    assert dict(quiz.scores.values_list("learner_id", "raw")) == {juan.pk: 2, paolo.pk: 1}
    page = signed_in.get(response["Location"])
    assert b"Least mastered" in page.content and b"50.00%" in page.content
    # Scores of an itemised quiz can't be typed over.
    signed_in.post(reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{juan.pk}": "0"})
    assert quiz.scores.get(learner=juan).raw == 2


@pytest.mark.django_db
def test_answers_page_redirects_until_items_exist(signed_in, section, quiz):
    response = signed_in.get(reverse("grades:responses", args=[section.pk, quiz.pk]))
    assert response["Location"] == reverse("grades:items", args=[section.pk, quiz.pk])


@pytest.mark.django_db
def test_cannot_itemise_a_quiz_that_has_total_scores(signed_in, section, learners, quiz):
    signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{learners[0].pk}": "5"}
    )
    signed_in.post(reverse("grades:items", args=[section.pk, quiz.pk]), {"competencies": "a\nb"})
    assert not quiz.items.exists()


@pytest.mark.django_db
def test_edit_cannot_lower_hps_below_existing_scores(signed_in, section, learners, quiz):
    signed_in.post(
        reverse("grades:scores", args=[section.pk, quiz.pk]), {f"r-{learners[0].pk}": "18"}
    )
    data = {
        "quarter": 1,
        "component": "WW",
        "title": "Quiz 1",
        "max_score": "10",
        "date": "2026-09-01",
    }
    response = signed_in.post(reverse("grades:edit", args=[section.pk, quiz.pk]), data)
    assert response.status_code == 200 and b"Lower them first" in response.content
    data["max_score"] = "25"
    signed_in.post(reverse("grades:edit", args=[section.pk, quiz.pk]), data)
    quiz.refresh_from_db()
    assert quiz.max_score == 25


@pytest.mark.django_db
def test_delete_assessment(signed_in, section, quiz):
    response = signed_in.post(reverse("grades:delete", args=[section.pk, quiz.pk]))
    assert response["Location"].endswith("?q=1")
    assert not Assessment.objects.exists()
