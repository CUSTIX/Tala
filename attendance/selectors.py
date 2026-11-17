import calendar
import datetime as dt
from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Count, Q

from attendance.models import Mark, Meeting, Status
from classroom.models import Learner, Section


def statuses_on(section: Section, date: dt.date) -> dict[int, str]:
    """learner id -> status for one day (learners without a mark are missing)."""
    return dict(
        Mark.objects.filter(meeting__section=section, meeting__date=date).values_list(
            "learner_id", "status"
        )
    )


def day_counts(section: Section, date: dt.date) -> dict[str, int]:
    """Status code -> count, in P, L, E, A order, only statuses that occur. A plain dict, not a
    Counter: templates look up keys before attributes, and a Counter answers 0 to "items"."""
    tally = Counter(statuses_on(section, date).values())
    return {s: tally[s] for s in Status.values if tally[s]}


@dataclass
class MonthRow:
    learner: Learner
    cells: list[str]  # status per class day, "" when not marked
    totals: Counter = field(default_factory=Counter)


@dataclass
class MonthReport:
    month: dt.date
    days: list[dt.date]
    rows: list[MonthRow]
    previous: dt.date
    next: dt.date


def month_report(section: Section, month: dt.date) -> MonthReport:
    """A class-days by learners grid for one month (like a school form 2)."""
    first = month.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    meetings = list(
        Meeting.objects.filter(section=section, date__range=(first, last)).order_by("date")
    )
    marks = {
        (m.learner_id, m.meeting_id): m.status
        for m in Mark.objects.filter(meeting__in=meetings).only(
            "learner_id", "meeting_id", "status"
        )
    }
    rows = []
    for learner in section.learners.all():
        cells = [marks.get((learner.pk, m.pk), "") for m in meetings]
        rows.append(MonthRow(learner, cells, Counter(c for c in cells if c)))
    previous = (first - dt.timedelta(days=1)).replace(day=1)
    return MonthReport(first, [m.date for m in meetings], rows, previous, last + dt.timedelta(1))


def learner_totals(learner: Learner) -> dict[str, int]:
    agg = learner.marks.aggregate(
        **{s.label.lower(): Count("pk", filter=Q(status=s.value)) for s in Status}
    )
    agg["days"] = sum(agg.values())
    return agg


def section_rates(section: Section) -> dict[int, int]:
    """learner id -> attendance rate in percent (present or late over marked days)."""
    rows = (
        Mark.objects.filter(meeting__section=section)
        .values("learner_id")
        .annotate(
            attended=Count("pk", filter=Q(status__in=[Status.PRESENT, Status.LATE])),
            total=Count("pk", filter=~Q(status=Status.EXCUSED)),
        )
    )
    return {r["learner_id"]: round(100 * r["attended"] / r["total"]) for r in rows if r["total"]}
