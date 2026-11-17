import csv
import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from attendance import selectors, services
from attendance.models import Status, Via
from classroom import selectors as classroom
from classroom.services import seat_grid

MODES = {"seats": "Seat plan", "list": "List", "roll": "One by one"}


def _day(value: str | None) -> dt.date:
    """?date=YYYY-MM-DD, never in the future; today when missing or invalid."""
    today = timezone.localdate()
    try:
        day = dt.date.fromisoformat(value) if value else today
    except ValueError:
        return today
    return min(day, today)


def _take_url(section, day, mode):
    return f"{reverse('attendance:take', args=[section.pk])}?date={day.isoformat()}&mode={mode}"


@login_required
def take(request, pk):
    section = classroom.section_for(request.user, pk)
    day = _day(request.GET.get("date") or request.POST.get("date"))
    mode = request.GET.get("mode") or request.POST.get("mode") or "seats"
    mode = mode if mode in MODES else "seats"
    learners = list(section.learners.all())
    if request.method == "POST":
        try:
            if request.POST.get("action") == "rest_absent":
                n = services.mark_rest_absent(section, day)
                messages.success(request, f"Marked {n} unmarked learner(s) absent.")
            else:
                statuses = {
                    x.pk: request.POST.get(f"s-{x.pk}", "")
                    for x in learners
                    if f"s-{x.pk}" in request.POST
                }
                via = Via.SEATS if mode == "seats" else Via.LIST
                count = services.save_marks(section, day, statuses, via)
                messages.success(request, f"Attendance saved: {count} of {len(learners)} marked.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect(_take_url(section, day, mode))
    statuses = selectors.statuses_on(section, day)
    for learner in learners:
        learner.status = statuses.get(learner.pk, "")
    return render(
        request,
        "attendance/take.html",
        {
            "section": section,
            "day": day,
            "is_today": day == timezone.localdate(),
            "previous": day - dt.timedelta(days=1),
            "next": day + dt.timedelta(days=1),
            "mode": mode,
            "modes": MODES,
            "learners": learners,
            "grid": seat_grid(section, learners),
            "unseated": [x for x in learners if not x.is_seated],
            "statuses": Status.choices,
            "counts": selectors.day_counts(section, day),
            "tab": "attendance",
        },
    )


@login_required
def scan(request, pk):
    section = classroom.section_for(request.user, pk)
    today = timezone.localdate()
    return render(
        request,
        "attendance/scan.html",
        {
            "section": section,
            "today": today,
            "marked": sum(selectors.day_counts(section, today).values()),
            "size": section.learners.count(),
            "tab": "attendance",
        },
    )


@login_required
@require_POST
def scan_mark(request, pk):
    """Called by the scanner page for each QR card it reads. Always today."""
    section = classroom.section_for(request.user, pk)
    today = timezone.localdate()
    late = request.POST.get("late") == "1"
    try:
        learner = services.mark_by_qr(section, today, request.POST.get("code", "")[:64], late)
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages[0]}, status=404)
    counts = selectors.day_counts(section, today)
    return JsonResponse(
        {
            "name": f"{learner.first_name} {learner.last_name}",
            "status": Status.LATE.label if late else Status.PRESENT.label,
            "marked": sum(counts.values()),
        }
    )


def _month(value: str | None) -> dt.date:
    try:
        return dt.date.fromisoformat(f"{value}-01") if value else timezone.localdate()
    except ValueError:
        return timezone.localdate()


@login_required
def report(request, pk):
    section = classroom.section_for(request.user, pk)
    month = _month(request.GET.get("month"))
    data = selectors.month_report(section, month)
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        name = f"attendance-{section.pk}-{data.month:%Y-%m}.csv"
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Learner",
                "Sex",
                *[d.isoformat() for d in data.days],
                "Present",
                "Late",
                "Excused",
                "Absent",
            ]
        )
        for row in data.rows:
            writer.writerow(
                [row.learner.name, row.learner.sex, *row.cells]
                + [row.totals[s] for s in ("P", "L", "E", "A")]
            )
        return response
    return render(
        request,
        "attendance/report.html",
        {
            "section": section,
            "report": data,
            "is_current": data.month == timezone.localdate().replace(day=1),
            "tab": "attendance",
        },
    )
