"""Taking attendance: by list, by tapping the seat plan, or by scanning QR cards."""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import transaction

from attendance.models import Mark, Meeting, Status, Via
from classroom.models import Learner, Section


def meeting_for(section: Section, date: dt.date) -> Meeting:
    meeting, _ = Meeting.objects.get_or_create(section=section, date=date)
    return meeting


@transaction.atomic
def save_marks(section: Section, date: dt.date, statuses: dict[int, str], via: str) -> int:
    """Set each learner's status for the day. An empty status clears the mark.
    Returns how many learners have a mark afterwards."""
    if via not in Via.values:
        raise ValidationError("Unknown attendance method.")
    learner_ids = set(section.learners.values_list("pk", flat=True))
    unknown = set(statuses) - learner_ids
    if unknown:
        raise ValidationError("Some learners are not in this class.")
    bad = {s for s in statuses.values() if s and s not in Status.values}
    if bad:
        raise ValidationError("Unknown attendance status.")
    meeting = meeting_for(section, date)
    existing = {m.learner_id: m for m in meeting.marks.all()}
    to_create, to_update, to_delete = [], [], []
    for learner_id, status in statuses.items():
        mark = existing.get(learner_id)
        if not status:
            if mark:
                to_delete.append(mark.pk)
        elif mark is None:
            to_create.append(Mark(meeting=meeting, learner_id=learner_id, status=status, via=via))
        elif mark.status != status:
            mark.status, mark.via = status, via
            to_update.append(mark)
    Mark.objects.bulk_create(to_create)
    Mark.objects.bulk_update(to_update, ["status", "via", "updated_at"])
    Mark.objects.filter(pk__in=to_delete).delete()
    return meeting.marks.count()


@transaction.atomic
def mark_by_qr(section: Section, date: dt.date, code: str, late: bool = False) -> Learner:
    """A scanned QR card: mark that learner present (or late).
    Cards of other classes are refused."""
    code = code.strip().removeprefix("TALA:")
    learner = Learner.objects.filter(section=section, qr_code=code).first()
    if learner is None:
        raise ValidationError("This QR card is not for a learner in this class.")
    meeting = meeting_for(section, date)
    Mark.objects.update_or_create(
        meeting=meeting,
        learner=learner,
        defaults={"status": Status.LATE if late else Status.PRESENT, "via": Via.QR},
    )
    return learner


@transaction.atomic
def mark_rest_absent(section: Section, date: dt.date) -> int:
    """Everyone without a mark today is absent. Returns how many were marked."""
    meeting = meeting_for(section, date)
    marked = meeting.marks.values_list("learner_id", flat=True)
    missing = section.learners.exclude(pk__in=marked).values_list("pk", flat=True)
    Mark.objects.bulk_create(
        [Mark(meeting=meeting, learner_id=pk, status=Status.ABSENT) for pk in missing]
    )
    return len(missing)
