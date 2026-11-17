import pytest
from django.urls import reverse

from classroom.models import Learner, Section
from classroom.services import arrange


@pytest.mark.django_db
def test_create_class_then_add_learners(signed_in, teacher):
    response = signed_in.post(
        reverse("classroom:section_create"),
        {
            "name": "Grade 9 - Luna",
            "subject": "Math 9",
            "subject_group": "MATHSCI",
            "school_year": "2026-2027",
        },
    )
    section = Section.objects.get(teacher=teacher, name="Grade 9 - Luna")
    assert response["Location"] == reverse("classroom:learners_add", args=[section.pk])
    response = signed_in.post(
        reverse("classroom:learners_add", args=[section.pk]),
        {"boys": "Cruz, Juan\nReyes, Paolo", "girls": "Santos, Maria"},
    )
    assert response.status_code == 302
    assert section.learners.count() == 3


@pytest.mark.django_db
def test_add_learners_shows_errors(signed_in, section):
    response = signed_in.post(
        reverse("classroom:learners_add", args=[section.pk]), {"boys": "Juan"}
    )
    assert response.status_code == 200
    assert b"Last, First" in response.content
    assert not section.learners.exists()


@pytest.mark.django_db
def test_class_page_lists_learners_boys_first(signed_in, section, learners):
    content = signed_in.get(reverse("classroom:section", args=[section.pk])).content.decode()
    assert content.index("Cruz, Juan") < content.index("Bautista, Andrea")


@pytest.mark.django_db
def test_edit_and_delete_learner(signed_in, section, learners):
    juan = learners[0]
    signed_in.post(
        reverse("classroom:learner_edit", args=[section.pk, juan.pk]),
        {"last_name": "Dela Cruz", "first_name": "Juan", "sex": "M"},
    )
    juan.refresh_from_db()
    assert juan.last_name == "Dela Cruz"
    signed_in.post(reverse("classroom:learner_delete", args=[section.pk, juan.pk]))
    assert not Learner.objects.filter(pk=juan.pk).exists()


@pytest.mark.django_db
def test_delete_class(signed_in, section, learners):
    signed_in.post(reverse("classroom:section_delete", args=[section.pk]))
    assert not Section.objects.filter(pk=section.pk).exists()


@pytest.mark.django_db
def test_learner_page_shows_qr_and_share_link(signed_in, section, learners):
    juan = learners[0]
    content = signed_in.get(reverse("classroom:learner", args=[section.pk, juan.pk])).content
    assert b"<svg" in content
    assert juan.share_token.encode() in content


@pytest.mark.django_db
def test_new_link_replaces_the_old_one(signed_in, client, section, learners):
    juan = learners[0]
    old = juan.share_token
    signed_in.post(reverse("classroom:learner_new_link", args=[section.pk, juan.pk]))
    juan.refresh_from_db()
    assert juan.share_token != old
    assert client.get(reverse("share", args=[old])).status_code == 404


@pytest.mark.django_db
def test_share_page_is_public_read_only_and_not_indexed(client, section, learners):
    juan = learners[0]
    response = client.get(reverse("share", args=[juan.share_token]))
    assert response.status_code == 200
    assert b"Juan Cruz" in response.content
    assert b"Paolo" not in response.content, "only this learner's record"
    assert response["X-Robots-Tag"] == "noindex"
    assert client.get(reverse("share", args=["guess"])).status_code == 404


@pytest.mark.django_db
def test_qr_cards_page(signed_in, section, learners):
    content = signed_in.get(reverse("classroom:qr_cards", args=[section.pk])).content
    assert content.count(b'class="segno"') == len(learners)


@pytest.mark.django_db
def test_seat_move_by_fetch_and_errors(signed_in, section, learners):
    arrange(section, "alphabetical")
    url = reverse("classroom:seats", args=[section.pk])
    juan = learners[0]
    response = signed_in.post(
        url,
        {"action": "move", "learner": juan.pk, "row": 1, "col": 2},
        HTTP_ACCEPT="application/json",
    )
    assert response.json() == {"ok": True}
    juan.refresh_from_db()
    assert (juan.seat_row, juan.seat_col) == (1, 2)
    response = signed_in.post(
        url,
        {"action": "move", "learner": juan.pk, "row": 9, "col": 0},
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 400
    response = signed_in.post(url, {"action": "move", "learner": juan.pk, "row": "off"})
    juan.refresh_from_db()
    assert not juan.is_seated and response.status_code == 302
    assert signed_in.post(url, {"action": "dance"}).status_code == 400


@pytest.mark.django_db
def test_seat_plan_actions(signed_in, section, learners):
    url = reverse("classroom:seats", args=[section.pk])
    signed_in.post(url, {"action": "clear"})
    assert not section.learners.filter(seat_row__isnull=False).exists()
    signed_in.post(url, {"action": "fill"})
    assert section.learners.filter(seat_row__isnull=False).count() == 4
    signed_in.post(url, {"action": "arrange", "how": "random"})
    signed_in.post(url, {"action": "resize", "rows": 3, "cols": 4})
    section.refresh_from_db()
    assert (section.seat_rows, section.seat_cols) == (3, 4)
    signed_in.post(url, {"action": "resize", "rows": 0, "cols": 4})
    section.refresh_from_db()
    assert section.seat_rows == 3
    page = signed_in.get(url)
    assert b"cols-4" in page.content


@pytest.mark.django_db
def test_cannot_move_another_classes_learner(signed_in, section, other_teacher):
    other = Section.objects.create(teacher=other_teacher, name="X", subject="Y")
    stranger = Learner.objects.create(section=other, last_name="A", first_name="B", sex="M")
    response = signed_in.post(
        reverse("classroom:seats", args=[section.pk]),
        {"action": "move", "learner": stranger.pk, "row": 0, "col": 0},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_picker_lists_names_as_data(signed_in, section, learners):
    content = signed_in.get(reverse("classroom:picker", args=[section.pk])).content
    assert b'id="picker-names"' in content and b"Juan Cruz" in content
