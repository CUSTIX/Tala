import random

import pytest
from django.core.exceptions import ValidationError

from classroom import services
from classroom.models import Learner


def test_parse_names_accepts_both_orders_and_skips_blank_lines():
    assert services.parse_names("Dela Cruz, Juan\n\n  Maria  Santos \n") == [
        ("Dela Cruz", "Juan"),
        ("Santos", "Maria"),
    ]


def test_parse_names_rejects_a_single_word():
    with pytest.raises(ValidationError):
        services.parse_names("Juan")


@pytest.mark.django_db
def test_add_learners_seats_them_front_first(section):
    services.add_learners(section, "Cruz, Juan\nReyes, Paolo", "Santos, Maria")
    seats = sorted(section.learners.values_list("seat_row", "seat_col"))
    assert seats == [(0, 0), (0, 1), (0, 2)]


@pytest.mark.django_db
def test_add_learners_needs_a_name(section):
    with pytest.raises(ValidationError):
        services.add_learners(section, "", "  ")


@pytest.mark.django_db
def test_learners_beyond_the_seats_stay_unseated(section):
    names = "\n".join(f"Last{i}, First{i}" for i in range(8))  # 2x3 room = 6 seats
    services.add_learners(section, names, "")
    assert section.learners.filter(seat_row__isnull=True).count() == 2


@pytest.mark.django_db
def test_move_to_a_taken_seat_swaps(section, learners):
    services.arrange(section, "alphabetical")
    a, b = (Learner.objects.get(pk=x.pk) for x in learners[:2])
    a_seat, b_seat = (a.seat_row, a.seat_col), (b.seat_row, b.seat_col)
    services.move_learner(section, a, *b_seat)
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.seat_row, a.seat_col) == b_seat
    assert (b.seat_row, b.seat_col) == a_seat


@pytest.mark.django_db
def test_move_unseated_learner_to_taken_seat_unseats_the_occupant(section, learners):
    services.arrange(section, "alphabetical")
    a = Learner.objects.get(pk=learners[0].pk)
    services.move_learner(section, a, None, None)
    occupant = section.learners.exclude(pk=a.pk).filter(seat_row__isnull=False).first()
    services.move_learner(
        section, Learner.objects.get(pk=a.pk), occupant.seat_row, occupant.seat_col
    )
    occupant.refresh_from_db()
    assert not occupant.is_seated


@pytest.mark.django_db
def test_move_refuses_seats_outside_the_room_and_other_classes(section, learners, other_teacher):
    with pytest.raises(ValidationError):
        services.move_learner(section, learners[0], 5, 0)
    from classroom.models import Section

    other = Section.objects.create(teacher=other_teacher, name="X", subject="Y")
    with pytest.raises(ValidationError):
        services.move_learner(other, learners[0], 0, 0)


@pytest.mark.django_db
def test_alternate_arrangement_mixes_boys_and_girls(section, learners):
    services.arrange(section, "alternate", random.Random(1))
    front = section.learners.filter(seat_row=0).order_by("seat_col")
    assert [x.sex for x in front] == ["M", "F", "M"]


@pytest.mark.django_db
def test_random_arrangement_uses_every_learner_once(section, learners):
    services.arrange(section, "random", random.Random(3))
    seats = list(section.learners.values_list("seat_row", "seat_col"))
    assert len(set(seats)) == len(learners) and (None, None) not in seats


@pytest.mark.django_db
def test_unknown_arrangement_is_refused(section, learners):
    with pytest.raises(ValidationError):
        services.arrange(section, "by-height")


@pytest.mark.django_db
def test_shrinking_the_room_unseats_learners_outside_it(section, learners):
    services.arrange(section, "alphabetical")  # fills row 0 (3 seats) and row 1 (1 seat)
    services.resize_seat_plan(section, 1, 2)
    assert section.learners.filter(seat_row__isnull=False).count() == 2
    with pytest.raises(ValidationError):
        services.resize_seat_plan(section, 0, 2)


@pytest.mark.django_db
def test_seat_grid_places_learners(section, learners):
    services.arrange(section, "alphabetical")
    grid = services.seat_grid(section, section.learners.all())
    assert len(grid) == 2 and len(grid[0]) == 3
    assert grid[0][0].last_name == "Bautista"
