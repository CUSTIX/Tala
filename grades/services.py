"""Class record math (DepEd Order No. 8, s. 2015) and item analysis.

For each component (written work, performance tasks, quarterly assessment):
    percentage score  PS = total raw score / total highest possible score x 100
    weighted score    WS = PS x component weight (depends on the subject, see classroom.WEIGHTS)
initial grade = sum of the weighted scores; quarterly grade = initial grade transmuted.

Transmutation table: an initial grade of 60 or more maps to 75-100 in steps of 1.6; below 60 maps
to 60-74 in steps of 4. So 60.00-61.59 -> 75, 98.40-99.99 -> 99, 100 -> 100, 0-3.99 -> 60.

Decimals throughout, never floats. Blank scores count as zero for that learner (the HPS still
counts), matching how a paper class record is totalled. Before every component has at least one
assessment, the grade is computed over the components that do and marked partial.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from classroom.models import Learner, Section
from core.numbers import plain
from grades.models import Assessment, Component, Item, Response, Score

TWO = Decimal("0.01")
HUNDRED = Decimal(100)
COMPONENTS = [c.value for c in Component]


def r2(value: Decimal) -> Decimal:
    return value.quantize(TWO, rounding=ROUND_HALF_UP)


def transmute(initial: Decimal) -> int:
    initial = max(Decimal(0), min(HUNDRED, Decimal(initial)))
    if initial >= 60:
        return min(100, 75 + math.floor((initial - 60) / Decimal("1.6")))
    return 60 + math.floor(initial / 4)


DESCRIPTORS = [
    (90, "Outstanding"),
    (85, "Very Satisfactory"),
    (80, "Satisfactory"),
    (75, "Fairly Satisfactory"),
    (0, "Did Not Meet Expectations"),
]


def descriptor(grade: int) -> str:
    return next(label for floor, label in DESCRIPTORS if grade >= floor)


@dataclass
class ComponentResult:
    raw: Decimal
    hps: Decimal
    ps: Decimal | None  # None: no assessment in this component yet
    ws: Decimal | None


@dataclass
class GradeRow:
    learner: Learner
    components: dict[str, ComponentResult]
    initial: Decimal | None
    quarterly: int | None
    partial: bool
    scores: dict[int, Decimal | None] = field(default_factory=dict)  # assessment id -> raw

    @property
    def descriptor(self) -> str:
        return descriptor(self.quarterly) if self.quarterly is not None else ""


def quarter_grades(section: Section, quarter: int) -> tuple[list[Assessment], list[GradeRow]]:
    assessments = list(
        section.assessments.filter(quarter=quarter).annotate(item_count=Count("items"))
    )
    raw = {
        (s.learner_id, s.assessment_id): s.raw
        for s in Score.objects.filter(assessment__in=assessments).only(
            "learner_id", "assessment_id", "raw"
        )
    }
    hps = defaultdict(Decimal)
    for a in assessments:
        hps[a.component] += a.max_score
    weights = section.weights
    present = [c for c in COMPONENTS if hps[c]]
    weight_total = sum((weights[c] for c in present), Decimal(0))
    rows = []
    for learner in section.learners.all():
        totals = defaultdict(Decimal)
        scores = {}
        for a in assessments:
            value = raw.get((learner.pk, a.pk))
            scores[a.pk] = value
            totals[a.component] += value or 0
        components = {}
        for c in COMPONENTS:
            if hps[c]:
                ps = r2(totals[c] / hps[c] * HUNDRED)
                components[c] = ComponentResult(totals[c], hps[c], ps, r2(ps * weights[c]))
            else:
                components[c] = ComponentResult(Decimal(0), Decimal(0), None, None)
        if present:
            weighted = sum((components[c].ws for c in present), Decimal(0))
            initial = r2(weighted / weight_total)  # weight_total is 1 once all components exist
            quarterly = transmute(initial)
        else:
            initial = quarterly = None
        rows.append(
            GradeRow(learner, components, initial, quarterly, len(present) < 3, scores=scores)
        )
    return assessments, rows


@dataclass
class FinalRow:
    learner: Learner
    quarters: list[int | None]
    final: int | None

    @property
    def descriptor(self) -> str:
        return descriptor(self.final) if self.final is not None else ""

    @property
    def passed(self) -> bool | None:
        return None if self.final is None else self.final >= 75


def final_grades(section: Section) -> list[FinalRow]:
    """Final grade = average of the quarterly grades so far, rounded to a whole number."""
    by_quarter = [
        {r.learner.pk: r.quarterly for r in quarter_grades(section, q)[1]} for q in (1, 2, 3, 4)
    ]
    rows = []
    for learner in section.learners.all():
        quarters = [grades.get(learner.pk) for grades in by_quarter]
        done = [g for g in quarters if g is not None]
        final = (
            int((Decimal(sum(done)) / len(done)).quantize(Decimal(1), ROUND_HALF_UP))
            if done
            else None
        )
        rows.append(FinalRow(learner, quarters, final))
    return rows


# ---- Writing scores ----------------------------------------------------------------------------


@transaction.atomic
def save_scores(assessment: Assessment, values: dict[int, Decimal | None]) -> None:
    """learner id -> raw score (None clears it). Each score must be within 0 and the HPS."""
    learner_ids = set(assessment.section.learners.values_list("pk", flat=True))
    if set(values) - learner_ids:
        raise ValidationError("Some learners are not in this class.")
    errors = [v for v in values.values() if v is not None and not (0 <= v <= assessment.max_score)]
    if errors:
        raise ValidationError(f"Scores must be between 0 and {plain(assessment.max_score)}.")
    clear = [pk for pk, v in values.items() if v is None]
    Score.objects.filter(assessment=assessment, learner_id__in=clear).delete()
    keep = {pk: v for pk, v in values.items() if v is not None}
    existing = {s.learner_id: s for s in assessment.scores.filter(learner_id__in=keep)}
    new, changed = [], []
    for pk, v in keep.items():
        if pk in existing:
            if existing[pk].raw != v:
                existing[pk].raw = v
                changed.append(existing[pk])
        else:
            new.append(Score(assessment=assessment, learner_id=pk, raw=v))
    Score.objects.bulk_create(new)
    Score.objects.bulk_update(changed, ["raw", "updated_at"])


# ---- Items and item analysis -------------------------------------------------------------------


@transaction.atomic
def set_items(assessment: Assessment, competencies: list[str]) -> None:
    """Define the quiz items, one competency per item (blank allowed). One point per item, so the
    HPS becomes the number of items. Answers to items that remain are kept."""
    if not 1 <= len(competencies) <= 100:
        raise ValidationError("A quiz has 1 to 100 items.")
    existing = {i.number: i for i in assessment.items.all()}
    for number, competency in enumerate(competencies, start=1):
        competency = competency.strip()[:160]
        if number in existing:
            if existing[number].competency != competency:
                existing[number].competency = competency
                existing[number].save(update_fields=["competency", "updated_at"])
        else:
            Item.objects.create(assessment=assessment, number=number, competency=competency)
    assessment.items.filter(number__gt=len(competencies)).delete()
    assessment.max_score = Decimal(len(competencies))
    assessment.save(update_fields=["max_score", "updated_at"])
    _scores_from_items(assessment)


@transaction.atomic
def save_responses(assessment: Assessment, correct: set[tuple[int, int]], learners: set[int]):
    """`learners` took the quiz; `correct` holds the (learner id, item id) pairs they answered
    right, every other item is wrong. Learners not in `learners` didn't take it: their answers and
    score are cleared (a missed quiz is blank, not zero). Scores are recomputed from the items."""
    items = {i.pk for i in assessment.items.all()}
    valid_learners = set(assessment.section.learners.values_list("pk", flat=True))
    if learners - valid_learners or {i for _, i in correct} - items:
        raise ValidationError("Unknown learner or item.")
    if {pk for pk, _ in correct} - learners:
        raise ValidationError("Answers given for a learner who didn't take the quiz.")
    Response.objects.filter(item__assessment=assessment).delete()
    assessment.scores.exclude(learner_id__in=learners).delete()
    Response.objects.bulk_create(
        Response(item_id=i, learner_id=pk, correct=(pk, i) in correct)
        for pk in learners
        for i in items
    )
    _scores_from_items(assessment, learners)


def _scores_from_items(assessment: Assessment, learners: set[int] | None = None) -> None:
    answered = defaultdict(int)
    seen = set()
    responses = Response.objects.filter(item__assessment=assessment)
    if learners is not None:
        responses = responses.filter(learner_id__in=learners)
    for learner_id, correct in responses.values_list("learner_id", "correct"):
        seen.add(learner_id)
        answered[learner_id] += int(correct)
    if seen:
        save_scores(assessment, {pk: Decimal(answered[pk]) for pk in seen})


MPS_LEVELS = [
    (96, "Mastered"),
    (86, "Closely approximating mastery"),
    (66, "Moving towards mastery"),
    (35, "Average mastery"),
    (15, "Low mastery"),
    (5, "Very low mastery"),
    (0, "Absolutely no mastery"),
]
MASTERY = Decimal(75)  # an item or competency answered right by 75% or more is mastered


def mps_level(mps: Decimal) -> str:
    return next(label for floor, label in MPS_LEVELS if mps >= floor)


@dataclass
class ItemStat:
    item: Item
    correct: int
    answered: int

    @property
    def percent(self) -> Decimal:
        return r2(Decimal(self.correct) / self.answered * HUNDRED) if self.answered else Decimal(0)

    @property
    def mastered(self) -> bool:
        return self.percent >= MASTERY


@dataclass
class CompetencyStat:
    competency: str
    items: list[int]
    percent: Decimal

    @property
    def mastered(self) -> bool:
        return self.percent >= MASTERY


@dataclass
class Analysis:
    takers: int
    mean: Decimal | None
    mps: Decimal | None
    level: str
    highest: Decimal | None
    lowest: Decimal | None
    items: list[ItemStat]
    competencies: list[CompetencyStat]  # least mastered first


def item_analysis(assessment: Assessment) -> Analysis:
    raws = list(assessment.scores.values_list("raw", flat=True))
    takers = len(raws)
    mean = r2(sum(raws, Decimal(0)) / takers) if takers else None
    mps = r2(mean / assessment.max_score * HUNDRED) if mean is not None else None
    counts = defaultdict(lambda: [0, 0])
    for item_id, correct in Response.objects.filter(item__assessment=assessment).values_list(
        "item_id", "correct"
    ):
        counts[item_id][0] += int(correct)
        counts[item_id][1] += 1
    items = [ItemStat(i, *counts[i.pk]) for i in assessment.items.all()]
    groups = defaultdict(list)
    for stat in items:
        groups[stat.item.competency or "(no competency)"].append(stat)
    competencies = []
    for name, stats in groups.items():
        right = sum(s.correct for s in stats)
        total = sum(s.answered for s in stats)
        percent = r2(Decimal(right) / total * HUNDRED) if total else Decimal(0)
        competencies.append(CompetencyStat(name, [s.item.number for s in stats], percent))
    competencies.sort(key=lambda c: c.percent)
    return Analysis(
        takers,
        mean,
        mps,
        mps_level(mps) if mps is not None else "",
        max(raws) if raws else None,
        min(raws) if raws else None,
        items,
        competencies,
    )


@dataclass
class LearnerQuarter:
    quarter: int
    row: GradeRow
    assessments: list[Assessment]


def learner_quarters(learner: Learner) -> list[LearnerQuarter]:
    """The learner's grade and scores for every quarter that has assessments."""
    result = []
    for quarter in (1, 2, 3, 4):
        assessments, rows = quarter_grades(learner.section, quarter)
        row = next((r for r in rows if r.learner.pk == learner.pk), None)
        if assessments and row:
            result.append(LearnerQuarter(quarter, row, assessments))
    return result
