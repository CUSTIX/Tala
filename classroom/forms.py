from django import forms
from django.core.exceptions import ValidationError

from classroom.models import Learner, Section
from classroom.services import parse_names


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["name", "subject", "subject_group", "school_year"]
        labels = {"name": "Section", "subject_group": "Grading weights"}
        help_texts = {
            "name": 'e.g. "Grade 7 - Sampaguita"',
            "subject_group": "Sets the written work / performance task / exam weights "
            "(DepEd Order No. 8, s. 2015).",
        }


NAMES_HELP = 'One learner per line, "Last, First". You can paste from a spreadsheet.'


class LearnersForm(forms.Form):
    boys = forms.CharField(
        label="Boys", widget=forms.Textarea(attrs={"rows": 8}), required=False, help_text=NAMES_HELP
    )
    girls = forms.CharField(
        label="Girls",
        widget=forms.Textarea(attrs={"rows": 8}),
        required=False,
        help_text=NAMES_HELP,
    )

    def clean(self):
        data = super().clean()
        total = 0
        for key in ("boys", "girls"):
            try:
                total += len(parse_names(data.get(key, "")))
            except ValidationError as exc:
                self.add_error(key, exc)
        if not self.errors and total == 0:
            raise ValidationError("Add at least one name.")
        if total > 80:
            raise ValidationError("Add at most 80 learners at a time.")
        return data


class LearnerForm(forms.ModelForm):
    class Meta:
        model = Learner
        fields = ["last_name", "first_name", "sex"]


class SeatPlanSizeForm(forms.Form):
    rows = forms.IntegerField(min_value=1, max_value=12)
    cols = forms.IntegerField(label="Columns", min_value=1, max_value=10)
