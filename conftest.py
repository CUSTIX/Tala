import datetime as dt

import pytest
from django.contrib.auth import get_user_model

from classroom.models import Learner, Section, Sex, SubjectGroup


@pytest.fixture(autouse=True)
def fresh_cache(settings):
    """In-memory cache per test (rate-limit counters start at zero; no database needed)."""
    from django.core.cache import cache

    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    yield


@pytest.fixture
def teacher(db):
    return get_user_model().objects.create_user("ana", password="pw-not-used-1", first_name="Ana")


@pytest.fixture
def other_teacher(db):
    return get_user_model().objects.create_user("ben", password="pw-not-used-2", first_name="Ben")


@pytest.fixture
def section(teacher):
    return Section.objects.create(
        teacher=teacher,
        name="Grade 7 - Rizal",
        subject="Science 7",
        subject_group=SubjectGroup.MATH_SCIENCE,
        seat_rows=2,
        seat_cols=3,
    )


@pytest.fixture
def learners(section):
    rows = [
        ("Cruz", "Juan", Sex.MALE),
        ("Reyes", "Paolo", Sex.MALE),
        ("Bautista", "Andrea", Sex.FEMALE),
        ("Santos", "Maria", Sex.FEMALE),
    ]
    return [
        Learner.objects.create(section=section, last_name=last, first_name=first, sex=sex)
        for last, first, sex in rows
    ]


@pytest.fixture
def signed_in(client, teacher):
    client.force_login(teacher)
    return client


@pytest.fixture
def other_client(client, other_teacher):
    client.force_login(other_teacher)
    return client


@pytest.fixture
def monday():
    return dt.date(2026, 11, 16)
