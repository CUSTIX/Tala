from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from grades.models import Assessment


class AssessmentForm(forms.ModelForm):
    items = forms.IntegerField(
        label="Number of items (optional)",
        min_value=1,
        max_value=100,
        required=False,
        help_text="For item analysis: one point per item, so this becomes the highest possible "
        "score. Leave blank to enter total scores only.",
    )

    class Meta:
        model = Assessment
        fields = ["quarter", "component", "title", "max_score", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "quarter": forms.Select(choices=[(q, f"Quarter {q}") for q in (1, 2, 3, 4)]),
        }
        labels = {"component": "Type", "max_score": "Highest possible score"}

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].initial = timezone.localdate()
        self.fields["max_score"].required = False
        if editing:
            del self.fields["items"]

    def clean(self):
        data = super().clean()
        if data.get("items"):
            data["max_score"] = data["items"]
        elif not data.get("max_score"):
            raise ValidationError("Give the highest possible score or the number of items.")
        return data


class CompetenciesForm(forms.Form):
    competencies = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="One line per item, in order: the competency that item tests. "
        "Lines can repeat, and a blank line is an item without a competency.",
    )

    def clean_competencies(self):
        lines = self.cleaned_data["competencies"].replace("\r", "").split("\n")
        while lines and not lines[-1].strip():
            lines.pop()
        if not 1 <= len(lines) <= 100:
            raise ValidationError("A quiz has 1 to 100 items.")
        return lines
