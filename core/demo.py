"""Fake classes for "Try the demo". Every visitor gets their own demo teacher, so nobody sees or
changes anyone else's data. Names are common Filipino first names and surnames combined at random:
made up, never real learners."""

import datetime as dt
import random
import secrets
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from attendance.models import Mark, Meeting, Status
from classroom import services as classroom
from classroom.models import Learner, Section, Sex, SubjectGroup
from grades.models import Assessment, Item, Response, Score

SURNAMES = """Dela Cruz, Santos, Reyes, Garcia, Mendoza, Bautista, Ramos, Aquino, Castillo,
Villanueva, Fernandez, Navarro, Torres, Flores, Gonzales, Domingo, Mercado, Pascual, Salazar,
Valdez, Soriano, Manalo, Aguilar, Lopez, Rivera, Morales, Cruz, Tolentino, Panganiban, Ocampo,
Gutierrez,
Javier, De Leon, Santiago, Marquez, Dizon, Mangubat, Lacson, Magbanua, Villareal, Abad, Belmonte,
Cabrera, Dimaano, Esguerra, Lualhati, Macaraeg, Nepomuceno, Quiambao, Sarmiento"""
BOYS = """Juan, Jose, Mark, John Paul, Carlo, Miguel, Paolo, Rafael, Gabriel, Angelo, Christian,
Joshua, Kenneth, Jericho, Nathaniel, Ian, Lance, Kyle, Jerome, Adrian, Vincent, Bryan, Elijah,
Francis, Dominic, Renz, Aldrin, Jayson, Prince, Emmanuel"""
GIRLS = """Maria, Andrea, Angel, Princess, Kristine, Nicole, Jasmine, Erica, Bea, Camille, Patricia,
Trisha, Joanna, Mikaela, Alyssa, Sofia, Ella, Janelle, Kathleen, Shaina, Hannah, Clarisse,
Rose Ann, Aira, Lovely, Precious, Mary Joy, Sheena, Danica, Ysabel"""


def _names(text: str) -> list[str]:
    return [n.strip() for n in text.split(",")]


CLASSES = [
    ("Grade 7 - Sampaguita", "Science 7", SubjectGroup.MATH_SCIENCE, 26),
    ("Grade 8 - Narra", "English 8", SubjectGroup.LANGUAGES, 24),
    ("Grade 10 - Mabini", "MAPEH 10", SubjectGroup.MAPEH_TLE, 22),
]

QUIZ_COMPETENCIES = {
    "Science 7": [
        "Identify the parts of the microscope",
        "Describe the levels of biological organization",
        "Differentiate plant and animal cells",
        "Explain how a microscope magnifies",
    ],
    "English 8": [
        "Determine the meaning of words from context",
        "Identify the main idea of a text",
        "Use transitional devices",
        "Distinguish fact from opinion",
    ],
    "MAPEH 10": [
        "Identify elements of 20th-century music",
        "Describe modern art movements",
        "Explain components of fitness",
        "Identify health trends and issues",
    ],
}

# (component, title, highest possible score) for the first quarter.
Q1 = [
    ("WW", "Quiz 1", 20),
    ("WW", "Quiz 2", 15),
    ("WW", "Long quiz", 40),
    ("WW", "Quiz 4", 20),  # has items: item analysis
    ("PT", "Group output", 50),
    ("PT", "Performance task 2", 50),
    ("QA", "First quarterly exam", 50),
]
Q2 = [("WW", "Quiz 1", 20), ("PT", "Project proposal", 30)]

FAKE_COUNT = 20  # items in the analysed quiz


def school_days(end: dt.date, count: int) -> list[dt.date]:
    days, day = [], end
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= dt.timedelta(days=1)
    return sorted(days)


def _class_names(rng: random.Random, boys: int, girls: int):
    """Unique made-up names for one class: boys first, then girls."""
    seen, out = set(), []
    for sex, count, pool in ((Sex.MALE, boys, _names(BOYS)), (Sex.FEMALE, girls, _names(GIRLS))):
        while sum(1 for x in out if x[2] == sex) < count:
            name = (rng.choice(_names(SURNAMES)), rng.choice(pool))
            if name not in seen:
                seen.add(name)
                out.append((*name, sex))
    return out


@transaction.atomic
def create_demo_teacher(today: dt.date | None = None, seed: int | None = None):
    today = today or timezone.localdate()
    rng = random.Random(seed)  # noqa: S311 - fake data
    user = get_user_model().objects.create(
        username=f"demo-{secrets.token_hex(5)}",
        first_name="Teacher " + rng.choice(_names(GIRLS)),
        is_demo=True,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])

    for name, subject, group, size in CLASSES:
        section = Section.objects.create(
            teacher=user, name=name, subject=subject, subject_group=group, seat_cols=6, seat_rows=5
        )
        boys = size // 2
        learners = Learner.objects.bulk_create(
            Learner(section=section, last_name=last, first_name=first, sex=sex)
            for last, first, sex in _class_names(rng, boys, size - boys)
        )
        classroom.arrange(section, "alternate", rng)
        ability = {x.pk: rng.uniform(0.66, 0.98) for x in learners}
        _attendance(section, learners, school_days(today - dt.timedelta(days=1), 20), rng)
        _assessments(section, learners, ability, today, rng)
    return user


def _attendance(section, learners, days, rng):
    meetings = Meeting.objects.bulk_create(Meeting(section=section, date=d) for d in days)
    habit = {x.pk: rng.choice([0.0, 0.02, 0.04, 0.08, 0.15]) for x in learners}
    marks = []
    for meeting in meetings:
        for learner in learners:
            roll = rng.random()
            miss = habit[learner.pk]
            if roll < miss:
                status = Status.ABSENT
            elif roll < miss * 2:
                status = Status.LATE
            elif roll < miss * 2 + 0.01:
                status = Status.EXCUSED
            else:
                status = Status.PRESENT
            marks.append(Mark(meeting=meeting, learner=learner, status=status))
    Mark.objects.bulk_create(marks)


def _assessments(section, learners, ability, today, rng):
    start = today - dt.timedelta(days=70)
    plan = [(1, *a) for a in Q1] + [(2, *a) for a in Q2]
    for n, (quarter, component, title, hps) in enumerate(plan):
        day = start + dt.timedelta(days=n * 7) if quarter == 1 else today - dt.timedelta(days=3)
        assessment = Assessment.objects.create(
            section=section,
            quarter=quarter,
            component=component,
            title=title,
            max_score=Decimal(hps),
            date=min(day, today),
        )
        if quarter == 1 and title == "Quiz 4":
            _quiz_items(assessment, learners, ability, rng)
            continue
        Score.objects.bulk_create(
            Score(
                assessment=assessment,
                learner=x,
                raw=Decimal(max(0, min(hps, round(hps * rng.gauss(ability[x.pk], 0.08))))),
            )
            for x in learners
        )


def _quiz_items(assessment, learners, ability, rng):
    competencies = QUIZ_COMPETENCIES[assessment.section.subject]
    difficulty = [rng.uniform(-0.25, 0.12) for _ in competencies]  # some harder than others
    items = Item.objects.bulk_create(
        Item(assessment=assessment, number=i + 1, competency=competencies[i % len(competencies)])
        for i in range(FAKE_COUNT)
    )
    assessment.max_score = Decimal(FAKE_COUNT)
    assessment.save(update_fields=["max_score"])
    responses, totals = [], {}
    for x in learners:
        right = 0
        for item in items:
            p = ability[x.pk] + difficulty[(item.number - 1) % len(competencies)]
            correct = rng.random() < p
            right += correct
            responses.append(Response(item=item, learner=x, correct=correct))
        totals[x.pk] = right
    Response.objects.bulk_create(responses)
    Score.objects.bulk_create(
        Score(assessment=assessment, learner_id=pk, raw=Decimal(v)) for pk, v in totals.items()
    )


def purge_expired(hours: int) -> int:
    cutoff = timezone.now() - dt.timedelta(hours=hours)
    expired = get_user_model().objects.filter(is_demo=True, date_joined__lt=cutoff)
    count = expired.count()
    expired.delete()  # cascades to their classes, learners, attendance and grades
    return count
