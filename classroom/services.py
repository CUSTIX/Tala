"""Classes, learners and the seat plan."""

import random
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from classroom.models import Learner, Section, Sex


def parse_names(text: str) -> list[tuple[str, str]]:
    """One learner per line, "Last, First" or "First Last". Blank lines are skipped."""
    names = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip(" ,\t")
        if not line:
            continue
        if "," in line:
            last, first = (part.strip() for part in line.split(",", 1))
        elif " " in line:
            first, last = line.rsplit(" ", 1)
        else:
            raise ValidationError(f'"{line}": write the name as "Last, First".')
        if not first or not last:
            raise ValidationError(f'"{line}": write the name as "Last, First".')
        names.append((last[:60], first[:60]))
    return names


@transaction.atomic
def add_learners(section: Section, boys: str, girls: str) -> list[Learner]:
    learners = [
        Learner(section=section, last_name=last, first_name=first, sex=sex)
        for text, sex in ((boys, Sex.MALE), (girls, Sex.FEMALE))
        for last, first in parse_names(text)
    ]
    if not learners:
        raise ValidationError("Add at least one name.")
    created = Learner.objects.bulk_create(learners)
    fill_empty_seats(section)
    return created


# ---- Seat plan ----------------------------------------------------------------------------------


def _seats(section: Section) -> list[tuple[int, int]]:
    """Front row first, left to right."""
    return [(r, c) for r in range(section.seat_rows) for c in range(section.seat_cols)]


@transaction.atomic
def move_learner(section: Section, learner: Learner, row: int | None, col: int | None) -> None:
    """Put a learner on a seat (swapping with whoever sits there) or, with None, off the plan."""
    if learner.section_id != section.pk:
        raise ValidationError("That learner is not in this class.")
    if row is None or col is None:
        Learner.objects.filter(pk=learner.pk).update(seat_row=None, seat_col=None)
        return
    if not (0 <= row < section.seat_rows and 0 <= col < section.seat_cols):
        raise ValidationError("That seat is outside the seat plan.")
    occupant = (
        Learner.objects.select_for_update()
        .filter(section=section, seat_row=row, seat_col=col)
        .exclude(pk=learner.pk)
        .first()
    )
    old = (learner.seat_row, learner.seat_col)
    # Free the target seat first so the unique constraint holds at every step.
    if occupant:
        Learner.objects.filter(pk=occupant.pk).update(seat_row=None, seat_col=None)
    Learner.objects.filter(pk=learner.pk).update(seat_row=row, seat_col=col)
    if occupant and old[0] is not None:
        Learner.objects.filter(pk=occupant.pk).update(seat_row=old[0], seat_col=old[1])


def _place(section: Section, ordered: list[Learner]) -> None:
    Learner.objects.filter(section=section).update(seat_row=None, seat_col=None)
    seats = _seats(section)
    for learner, (row, col) in zip(ordered, seats, strict=False):
        learner.seat_row, learner.seat_col = row, col
    Learner.objects.bulk_update(ordered[: len(seats)], ["seat_row", "seat_col"])


ARRANGEMENTS = {
    "alphabetical": "Alphabetical",
    "random": "Random",
    "alternate": "Boy, girl, alternating",
}


@transaction.atomic
def arrange(section: Section, how: str, rng: random.Random | None = None) -> None:
    """Re-seat the whole class. Learners beyond the number of seats stay unseated."""
    rng = rng or random.Random()  # noqa: S311 - seating, not security
    learners = list(section.learners.order_by("last_name", "first_name"))
    if how == "random":
        rng.shuffle(learners)
    elif how == "alternate":
        boys = [x for x in learners if x.sex == Sex.MALE]
        girls = [x for x in learners if x.sex == Sex.FEMALE]
        rng.shuffle(boys)
        rng.shuffle(girls)
        learners = []
        while boys or girls:
            for group in (boys, girls):
                if group:
                    learners.append(group.pop())
    elif how != "alphabetical":
        raise ValidationError("Unknown arrangement.")
    _place(section, learners)


@transaction.atomic
def fill_empty_seats(section: Section) -> None:
    """Seat unseated learners in the first free seats (front to back)."""
    taken = set(section.learners.filter(seat_row__isnull=False).values_list("seat_row", "seat_col"))
    free = [s for s in _seats(section) if s not in taken]
    unseated = list(section.learners.filter(seat_row__isnull=True))
    for learner, (row, col) in zip(unseated, free, strict=False):
        learner.seat_row, learner.seat_col = row, col
    Learner.objects.bulk_update(unseated[: len(free)], ["seat_row", "seat_col"])


@transaction.atomic
def clear_seats(section: Section) -> None:
    section.learners.update(seat_row=None, seat_col=None)


@transaction.atomic
def resize_seat_plan(section: Section, rows: int, cols: int) -> None:
    """Change the room size. Learners whose seat no longer exists are unseated."""
    if not (1 <= rows <= 12 and 1 <= cols <= 10):
        raise ValidationError("A seat plan has 1-12 rows and 1-10 columns.")
    section.seat_rows, section.seat_cols = rows, cols
    section.save(update_fields=["seat_rows", "seat_cols", "updated_at"])
    section.learners.filter(seat_row__gte=rows).update(seat_row=None, seat_col=None)
    section.learners.filter(seat_col__gte=cols).update(seat_row=None, seat_col=None)


def seat_grid(section: Section, learners) -> list[list[Learner | None]]:
    """Rows of seats (front row first) with the learner on each, or None."""
    grid: list[list[Learner | None]] = [
        [None] * section.seat_cols for _ in range(section.seat_rows)
    ]
    for learner in learners:
        if learner.is_seated and learner.seat_row < section.seat_rows:
            if learner.seat_col < section.seat_cols:
                grid[learner.seat_row][learner.seat_col] = learner
    return grid
