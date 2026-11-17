import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from grades import services
from grades.models import Assessment, Score


@pytest.mark.parametrize(
    "initial, grade",
    [
        ("100", 100),
        ("99.99", 99),
        ("98.40", 99),
        ("98.39", 98),
        ("61.60", 76),
        ("61.59", 75),
        ("60", 75),
        ("59.99", 74),
        ("56", 74),
        ("55.99", 73),
        ("4", 61),
        ("3.99", 60),
        ("0", 60),
    ],
)
def test_transmutation_table(initial, grade):
    assert services.transmute(Decimal(initial)) == grade


@pytest.mark.parametrize(
    "grade, label",
    [
        (90, "Outstanding"),
        (89, "Very Satisfactory"),
        (80, "Satisfactory"),
        (75, "Fairly Satisfactory"),
        (74, "Did Not Meet Expectations"),
    ],
)
def test_descriptors(grade, label):
    assert services.descriptor(grade) == label


def _assessment(section, component, hps, quarter=1, title="A"):
    return Assessment.objects.create(
        section=section,
        quarter=quarter,
        component=component,
        title=title,
        max_score=Decimal(hps),
        date=dt.date(2026, 9, 1),
    )


@pytest.mark.django_db
def test_quarter_grade_follows_deped_worked_example(section, learners):
    """Math/Science weights 40/40/20. WW 32/40 -> PS 80, PT 90/100 -> 90, QA 35/50 -> 70.
    Initial = 80*.4 + 90*.4 + 70*.2 = 32 + 36 + 14 = 82.00 -> transmuted 88."""
    juan = learners[0]
    ww1, ww2 = (
        _assessment(section, "WW", 20, title="Q1"),
        _assessment(section, "WW", 20, title="Q2"),
    )
    pt = _assessment(section, "PT", 100)
    qa = _assessment(section, "QA", 50)
    for a, raw in ((ww1, 15), (ww2, 17), (pt, 90), (qa, 35)):
        Score.objects.create(assessment=a, learner=juan, raw=Decimal(raw))
    _, rows = services.quarter_grades(section, 1)
    row = next(r for r in rows if r.learner == juan)
    assert row.components["WW"].ps == Decimal("80.00")
    assert row.components["WW"].ws == Decimal("32.00")
    assert row.components["PT"].ws == Decimal("36.00")
    assert row.components["QA"].ws == Decimal("14.00")
    assert row.initial == Decimal("82.00")
    assert row.quarterly == 88
    assert not row.partial
    assert row.descriptor == "Very Satisfactory"


@pytest.mark.django_db
def test_blank_score_counts_as_zero_but_the_hps_still_counts(section, learners):
    a, b = _assessment(section, "WW", 10, title="A"), _assessment(section, "WW", 10, title="B")
    Score.objects.create(assessment=a, learner=learners[0], raw=Decimal(10))
    _, rows = services.quarter_grades(section, 1)
    row = next(r for r in rows if r.learner == learners[0])
    assert row.components["WW"].ps == Decimal("50.00")
    assert row.scores[b.pk] is None


@pytest.mark.django_db
def test_partial_grade_uses_only_components_with_assessments(section, learners):
    """Only written work so far: the grade is the written-work PS, transmuted, marked partial."""
    a = _assessment(section, "WW", 20)
    Score.objects.create(assessment=a, learner=learners[0], raw=Decimal(16))
    _, rows = services.quarter_grades(section, 1)
    row = next(r for r in rows if r.learner == learners[0])
    assert row.initial == Decimal("80.00")
    assert row.quarterly == services.transmute(Decimal(80))
    assert row.partial


@pytest.mark.django_db
def test_no_assessments_means_no_grade(section, learners):
    assessments, rows = services.quarter_grades(section, 2)
    assert assessments == []
    assert all(r.quarterly is None for r in rows)


@pytest.mark.django_db
def test_final_grade_averages_quarters_so_far(section, learners):
    for quarter, raw in ((1, 20), (2, 10)):
        a = _assessment(section, "WW", 20, quarter=quarter)
        Score.objects.create(assessment=a, learner=learners[0], raw=Decimal(raw))
    row = next(r for r in services.final_grades(section) if r.learner == learners[0])
    assert row.quarters[:2] == [100, services.transmute(Decimal(50))]
    assert row.final == round((100 + services.transmute(Decimal(50))) / 2)
    assert row.quarters[2:] == [None, None]


@pytest.mark.django_db
def test_save_scores_rejects_out_of_range_and_other_classes(section, learners, other_teacher):
    a = _assessment(section, "WW", 20)
    with pytest.raises(ValidationError):
        services.save_scores(a, {learners[0].pk: Decimal(21)})
    with pytest.raises(ValidationError):
        services.save_scores(a, {learners[0].pk: Decimal(-1)})
    with pytest.raises(ValidationError):
        services.save_scores(a, {999999: Decimal(5)})
    services.save_scores(a, {learners[0].pk: Decimal("19.5"), learners[1].pk: None})
    assert a.scores.get().raw == Decimal("19.5")
    services.save_scores(a, {learners[0].pk: None})
    assert not a.scores.exists()


@pytest.mark.django_db
def test_items_responses_and_item_analysis(section, learners):
    quiz = _assessment(section, "WW", 1)
    services.set_items(quiz, ["Cells", "Cells", "Microscope", "Microscope"])
    quiz.refresh_from_db()
    assert quiz.max_score == 4
    items = list(quiz.items.all())
    juan, paolo, andrea, maria = learners
    right = {(juan.pk, items[0].pk), (juan.pk, items[1].pk), (juan.pk, items[2].pk)}
    right |= {(paolo.pk, items[0].pk), (paolo.pk, items[1].pk)}
    right |= {
        (andrea.pk, items[0].pk),
        (andrea.pk, items[1].pk),
        (andrea.pk, items[2].pk),
        (andrea.pk, items[3].pk),
    }
    services.save_responses(quiz, right, {juan.pk, paolo.pk, andrea.pk})
    scores = dict(quiz.scores.values_list("learner_id", "raw"))
    assert scores == {juan.pk: 3, paolo.pk: 2, andrea.pk: 4}, "Maria didn't take it: blank, not 0"
    a = services.item_analysis(quiz)
    assert a.takers == 3
    assert a.mean == Decimal("3.00")
    assert a.mps == Decimal("75.00")
    assert a.level == "Moving towards mastery"
    least = a.competencies[0]
    assert least.competency == "Microscope" and least.percent == Decimal("50.00")
    assert not least.mastered
    assert a.competencies[1].mastered


@pytest.mark.django_db
def test_responses_refuse_answers_for_learners_who_did_not_take_it(section, learners):
    quiz = _assessment(section, "WW", 1)
    services.set_items(quiz, ["x"])
    item = quiz.items.get()
    with pytest.raises(ValidationError):
        services.save_responses(quiz, {(learners[0].pk, item.pk)}, set())


@pytest.mark.django_db
def test_shrinking_items_drops_extra_items(section, learners):
    quiz = _assessment(section, "WW", 1)
    services.set_items(quiz, ["a", "b", "c"])
    services.set_items(quiz, ["a", "b"])
    assert list(quiz.items.values_list("number", flat=True)) == [1, 2]
    with pytest.raises(ValidationError):
        services.set_items(quiz, [])


@pytest.mark.parametrize(
    "mps, level",
    [
        (96, "Mastered"),
        (86, "Closely approximating mastery"),
        (66, "Moving towards mastery"),
        (35, "Average mastery"),
        (15, "Low mastery"),
        (5, "Very low mastery"),
        (4, "Absolutely no mastery"),
    ],
)
def test_mps_levels(mps, level):
    assert services.mps_level(Decimal(mps)) == level
