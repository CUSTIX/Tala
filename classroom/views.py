from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from attendance import selectors as attendance
from classroom import selectors, services
from classroom.forms import LearnerForm, LearnersForm, SeatPlanSizeForm, SectionForm
from classroom.models import new_share_token
from core.qr import card_payload, qr_svg
from grades import services as grades


@login_required
def dashboard(request):
    today = timezone.localdate()
    sections = list(
        selectors.sections_for(request.user).annotate(size=Count("learners", distinct=True))
    )
    for section in sections:
        section.today = attendance.day_counts(section, today)
        section.marked = sum(section.today.values())
    return render(request, "classroom/dashboard.html", {"sections": sections, "today": today})


@login_required
def section_create(request):
    form = SectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        section = form.save(commit=False)
        section.teacher = request.user
        section.save()
        messages.success(request, "Class created. Now add your learners.")
        return redirect("classroom:learners_add", section.pk)
    return render(request, "classroom/section_form.html", {"form": form})


@login_required
def section_edit(request, pk):
    section = selectors.section_for(request.user, pk)
    form = SectionForm(request.POST or None, instance=section)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Class saved.")
        return redirect("classroom:section", section.pk)
    return render(request, "classroom/section_form.html", {"form": form, "section": section})


@login_required
@require_POST
def section_delete(request, pk):
    section = selectors.section_for(request.user, pk)
    section.delete()
    messages.success(request, f"Deleted {section}.")
    return redirect("classroom:dashboard")


@login_required
def section_detail(request, pk):
    section = selectors.section_for(request.user, pk)
    today = timezone.localdate()
    learners = list(section.learners.all())
    rates = attendance.section_rates(section)
    for learner in learners:
        learner.rate = rates.get(learner.pk)
    return render(
        request,
        "classroom/section_detail.html",
        {
            "section": section,
            "learners": learners,
            "today": today,
            "counts": attendance.day_counts(section, today),
            "tab": "learners",
        },
    )


@login_required
def learners_add(request, pk):
    section = selectors.section_for(request.user, pk)
    form = LearnersForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        added = services.add_learners(
            section, form.cleaned_data["boys"], form.cleaned_data["girls"]
        )
        messages.success(request, f"Added {len(added)} learner(s) and gave them seats.")
        return redirect("classroom:section", section.pk)
    return render(
        request,
        "classroom/learners_add.html",
        {"form": form, "section": section, "tab": "learners"},
    )


@login_required
def learner_detail(request, pk, learner_pk):
    section = selectors.section_for(request.user, pk)
    learner = selectors.learner_for(section, learner_pk)
    share_url = request.build_absolute_uri(reverse("share", args=[learner.share_token]))
    return render(
        request,
        "classroom/learner_detail.html",
        {
            "section": section,
            "learner": learner,
            "totals": attendance.learner_totals(learner),
            "recent": learner.marks.select_related("meeting").order_by("-meeting__date")[:10],
            "quarters": grades.learner_quarters(learner),
            "qr": qr_svg(card_payload(learner.qr_code)),
            "share_url": share_url,
            "tab": "learners",
        },
    )


@login_required
def learner_edit(request, pk, learner_pk):
    section = selectors.section_for(request.user, pk)
    learner = selectors.learner_for(section, learner_pk)
    form = LearnerForm(request.POST or None, instance=learner)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect("classroom:learner", section.pk, learner.pk)
    return render(
        request,
        "classroom/learner_form.html",
        {"form": form, "section": section, "learner": learner, "tab": "learners"},
    )


@login_required
@require_POST
def learner_delete(request, pk, learner_pk):
    section = selectors.section_for(request.user, pk)
    learner = selectors.learner_for(section, learner_pk)
    learner.delete()
    messages.success(request, f"Removed {learner.name} and their records from this class.")
    return redirect("classroom:section", section.pk)


@login_required
@require_POST
def learner_new_link(request, pk, learner_pk):
    """Replace the share link: the old one stops working (e.g. it was sent to the wrong person)."""
    section = selectors.section_for(request.user, pk)
    learner = selectors.learner_for(section, learner_pk)
    learner.share_token = new_share_token()
    learner.save(update_fields=["share_token", "updated_at"])
    messages.success(request, "New link made. The old link no longer works.")
    return redirect("classroom:learner", section.pk, learner.pk)


@login_required
def qr_cards(request, pk):
    section = selectors.section_for(request.user, pk)
    cards = [(x, qr_svg(card_payload(x.qr_code))) for x in section.learners.all()]
    return render(request, "classroom/qr_cards.html", {"section": section, "cards": cards})


# ---- Seat plan ----------------------------------------------------------------------------------


def _int_or_none(value):
    if value in (None, "", "off"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Bad seat.") from exc


@login_required
def seat_plan(request, pk):
    section = selectors.section_for(request.user, pk)
    if request.method == "POST":
        wants_json = request.headers.get("Accept") == "application/json"
        action = request.POST.get("action")
        try:
            if action == "move":
                learner = selectors.learner_for(section, _int_or_none(request.POST.get("learner")))
                services.move_learner(
                    section,
                    learner,
                    _int_or_none(request.POST.get("row")),
                    _int_or_none(request.POST.get("col")),
                )
            elif action == "arrange":
                services.arrange(section, request.POST.get("how", ""))
                messages.success(request, "Seats rearranged.")
            elif action == "fill":
                services.fill_empty_seats(section)
            elif action == "clear":
                services.clear_seats(section)
                messages.success(request, "Everyone is off the seat plan.")
            elif action == "resize":
                form = SeatPlanSizeForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("A seat plan has 1-12 rows and 1-10 columns.")
                services.resize_seat_plan(
                    section, form.cleaned_data["rows"], form.cleaned_data["cols"]
                )
                messages.success(request, "Room size saved.")
            else:
                return HttpResponseBadRequest("Unknown action.")
        except ValidationError as exc:
            if wants_json:
                return JsonResponse({"error": exc.messages[0]}, status=400)
            messages.error(request, exc.messages[0])
        if wants_json:
            return JsonResponse({"ok": True})
        return redirect("classroom:seats", section.pk)
    learners = list(section.learners.all())
    return render(
        request,
        "classroom/seat_plan.html",
        {
            "section": section,
            "grid": services.seat_grid(section, learners),
            "unseated": [x for x in learners if not x.is_seated],
            "size_form": SeatPlanSizeForm(
                initial={"rows": section.seat_rows, "cols": section.seat_cols}
            ),
            "arrangements": services.ARRANGEMENTS,
            "tab": "seats",
        },
    )


@login_required
def picker(request, pk):
    """Random recitation picker. Prefers learners who are present today."""
    section = selectors.section_for(request.user, pk)
    today_marks = attendance.statuses_on(section, timezone.localdate())
    names = [
        {"id": x.pk, "name": f"{x.first_name} {x.last_name}", "here": today_marks.get(x.pk, "P")}
        for x in section.learners.all()
    ]
    return render(
        request,
        "classroom/picker.html",
        {"section": section, "names": names, "tab": "picker"},
    )


@never_cache
def share(request, token):
    """Read-only report for a learner or parent, opened from the secret link."""
    learner = selectors.learner_by_token(token)
    response = render(
        request,
        "classroom/share.html",
        {
            "learner": learner,
            "section": learner.section,
            "totals": attendance.learner_totals(learner),
            "quarters": grades.learner_quarters(learner),
        },
    )
    response["X-Robots-Tag"] = "noindex"
    return response
