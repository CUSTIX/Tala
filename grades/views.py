import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from classroom import selectors as classroom
from core.numbers import plain
from grades import services
from grades.forms import AssessmentForm, CompetenciesForm
from grades.models import Assessment, Component


def _assessment(section, pk) -> Assessment:
    return get_object_or_404(Assessment, pk=pk, section=section)


def _quarter(request, section) -> int:
    try:
        quarter = int(request.GET.get("q", ""))
    except ValueError:
        quarter = 0
    if quarter in (1, 2, 3, 4):
        return quarter
    latest = section.assessments.order_by("-quarter").values_list("quarter", flat=True).first()
    return latest or 1


@login_required
def gradebook(request, pk):
    section = classroom.section_for(request.user, pk)
    quarter = _quarter(request, section)
    assessments, rows = services.quarter_grades(section, quarter)
    if request.GET.get("format") == "csv":
        return _csv(section, quarter, assessments, rows)
    groups = [
        (c, [a for a in assessments if a.component == c.value], section.weights[c.value])
        for c in Component
    ]
    return render(
        request,
        "grades/gradebook.html",
        {
            "section": section,
            "quarter": quarter,
            "groups": groups,
            "assessments": assessments,
            "rows": rows,
            "tab": "grades",
        },
    )


def _csv(section, quarter, assessments, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="class-record-{section.pk}-q{quarter}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(
        ["Learner", "Sex"]
        + [f"{a.component} {a.title} ({plain(a.max_score)})" for a in assessments]
        + ["WW PS", "WW WS", "PT PS", "PT WS", "QA PS", "QA WS", "Initial grade", "Quarterly grade"]
    )
    for row in rows:
        cells = [row.learner.name, row.learner.sex]
        cells += ["" if row.scores[a.pk] is None else row.scores[a.pk] for a in assessments]
        for c in ("WW", "PT", "QA"):
            comp = row.components[c]
            cells += ["" if comp.ps is None else comp.ps, "" if comp.ws is None else comp.ws]
        cells += [row.initial or "", row.quarterly or ""]
        writer.writerow(cells)
    return response


@login_required
def final(request, pk):
    section = classroom.section_for(request.user, pk)
    return render(
        request,
        "grades/final.html",
        {"section": section, "rows": services.final_grades(section), "tab": "grades"},
    )


@login_required
def assessment_create(request, pk):
    section = classroom.section_for(request.user, pk)
    initial = {"quarter": _quarter(request, section), "component": request.GET.get("c", "WW")}
    form = AssessmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        assessment = form.save(commit=False)
        assessment.section = section
        assessment.max_score = form.cleaned_data["max_score"]
        assessment.save()
        if form.cleaned_data.get("items"):
            services.set_items(assessment, [""] * form.cleaned_data["items"])
            messages.success(request, "Added. Tag each item with its competency, or skip.")
            return redirect("grades:items", section.pk, assessment.pk)
        messages.success(request, "Added. Now enter the scores.")
        return redirect("grades:scores", section.pk, assessment.pk)
    return render(
        request, "grades/assessment_form.html", {"form": form, "section": section, "tab": "grades"}
    )


@login_required
def assessment_edit(request, pk, assessment_pk):
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    form = AssessmentForm(request.POST or None, instance=assessment, editing=True)
    if assessment.has_items:
        form.fields["max_score"].disabled = True
        form.fields["max_score"].help_text = "Set by the number of items."
    if request.method == "POST" and form.is_valid():
        try:
            if assessment.scores.filter(raw__gt=form.cleaned_data["max_score"]).exists():
                raise ValidationError("Some scores are above that. Lower them first.")
            form.save()
            messages.success(request, "Saved.")
            return redirect("grades:scores", section.pk, assessment.pk)
        except ValidationError as exc:
            form.add_error("max_score", exc)
    return render(
        request,
        "grades/assessment_form.html",
        {"form": form, "section": section, "assessment": assessment, "tab": "grades"},
    )


@login_required
@require_POST
def assessment_delete(request, pk, assessment_pk):
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    quarter = assessment.quarter
    assessment.delete()
    messages.success(request, f"Deleted {assessment.title} and its scores.")
    return redirect(f"{reverse('grades:book', args=[section.pk])}?q={quarter}")


def _decimal(value: str) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(f'"{value}" is not a number.') from exc


@login_required
def scores(request, pk, assessment_pk):
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    learners = list(section.learners.all())
    if request.method == "POST" and not assessment.has_items:
        try:
            values = {
                x.pk: _decimal(request.POST.get(f"r-{x.pk}", ""))
                for x in learners
                if f"r-{x.pk}" in request.POST
            }
            services.save_scores(assessment, values)
            messages.success(request, "Scores saved.")
            return redirect(f"{reverse('grades:book', args=[section.pk])}?q={assessment.quarter}")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    current = dict(assessment.scores.values_list("learner_id", "raw"))
    for learner in learners:
        value = current.get(learner.pk)
        learner.raw = "" if value is None else plain(value)
        if request.method == "POST":
            learner.raw = request.POST.get(f"r-{learner.pk}", learner.raw)
    return render(
        request,
        "grades/scores.html",
        {"section": section, "assessment": assessment, "learners": learners, "tab": "grades"},
    )


@login_required
def items(request, pk, assessment_pk):
    """Tag each quiz item with a competency."""
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    current = "\n".join(i.competency for i in assessment.items.all())
    form = CompetenciesForm(request.POST or None, initial={"competencies": current})
    if request.method == "POST" and form.is_valid():
        if assessment.scores.exists() and not assessment.has_items:
            messages.error(request, "This quiz already has total scores. Clear them first.")
        else:
            services.set_items(assessment, form.cleaned_data["competencies"])
            messages.success(request, "Items saved. Now check each learner's answers.")
            return redirect("grades:responses", section.pk, assessment.pk)
    return render(
        request,
        "grades/items.html",
        {"section": section, "assessment": assessment, "form": form, "tab": "grades"},
    )


@login_required
def responses(request, pk, assessment_pk):
    """Item-by-item checking: one row per learner, one checkbox per item answered right."""
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    quiz_items = list(assessment.items.all())
    if not quiz_items:
        return redirect("grades:items", section.pk, assessment.pk)
    learners = list(section.learners.all())
    if request.method == "POST":
        took = {x.pk for x in learners if request.POST.get(f"t-{x.pk}")}
        correct = {
            (x.pk, i.pk)
            for x in learners
            for i in quiz_items
            if x.pk in took and request.POST.get(f"c-{x.pk}-{i.pk}")
        }
        try:
            services.save_responses(assessment, correct, took)
            messages.success(request, "Answers saved and scores updated.")
            return redirect("grades:analysis", section.pk, assessment.pk)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
    right = set(
        assessment.items.filter(responses__correct=True).values_list("responses__learner_id", "pk")
    )
    answered = set(assessment.scores.values_list("learner_id", flat=True))
    rows = [
        (x, x.pk in answered or not answered, [(i, (x.pk, i.pk) in right) for i in quiz_items])
        for x in learners
    ]
    return render(
        request,
        "grades/responses.html",
        {
            "section": section,
            "assessment": assessment,
            "items": quiz_items,
            "rows": rows,
            "tab": "grades",
        },
    )


@login_required
def analysis(request, pk, assessment_pk):
    section = classroom.section_for(request.user, pk)
    assessment = _assessment(section, assessment_pk)
    return render(
        request,
        "grades/analysis.html",
        {
            "section": section,
            "assessment": assessment,
            "a": services.item_analysis(assessment),
            "tab": "grades",
        },
    )
