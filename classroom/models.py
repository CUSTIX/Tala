import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStamped


class SubjectGroup(models.TextChoices):
    """DepEd Order No. 8, s. 2015: component weights depend on the subject."""

    LANGUAGES = "LANG", "Languages, AP, EsP (Grades 1-10)"
    MATH_SCIENCE = "MATHSCI", "Math, Science (Grades 1-10)"
    MAPEH_TLE = "MAPEH", "MAPEH, EPP/TLE (Grades 1-10)"
    SHS_CORE = "SHSCORE", "SHS core subjects"
    SHS_ACADEMIC = "SHSACAD", "SHS academic track subjects"
    SHS_TVL = "SHSTVL", "SHS TVL, sports and arts subjects"


# (written work, performance tasks, quarterly assessment), as fractions of the grade.
WEIGHTS = {
    SubjectGroup.LANGUAGES: ("0.30", "0.50", "0.20"),
    SubjectGroup.MATH_SCIENCE: ("0.40", "0.40", "0.20"),
    SubjectGroup.MAPEH_TLE: ("0.20", "0.60", "0.20"),
    SubjectGroup.SHS_CORE: ("0.25", "0.50", "0.25"),
    SubjectGroup.SHS_ACADEMIC: ("0.25", "0.45", "0.30"),
    SubjectGroup.SHS_TVL: ("0.20", "0.60", "0.20"),
}


class Section(TimeStamped):
    """One class a teacher handles: a section and the subject taught to it."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(max_length=80, help_text='e.g. "Grade 7 - Sampaguita"')
    subject = models.CharField(max_length=80)
    subject_group = models.CharField(
        max_length=8, choices=SubjectGroup.choices, default=SubjectGroup.LANGUAGES
    )
    school_year = models.CharField(max_length=9, default="2026-2027")
    seat_rows = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    seat_cols = models.PositiveSmallIntegerField(
        default=6, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    class Meta:
        ordering = ["name", "subject"]

    def __str__(self):
        return f"{self.name} · {self.subject}"

    @property
    def weights(self) -> dict[str, Decimal]:
        ww, pt, qa = WEIGHTS[SubjectGroup(self.subject_group)]
        return {"WW": Decimal(ww), "PT": Decimal(pt), "QA": Decimal(qa)}


def new_qr_code() -> str:
    return secrets.token_urlsafe(8)


def new_share_token() -> str:
    return secrets.token_urlsafe(24)


class Sex(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"


class Learner(TimeStamped):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="learners")
    last_name = models.CharField(max_length=60)
    first_name = models.CharField(max_length=60)
    sex = models.CharField(max_length=1, choices=Sex.choices)
    # Printed on the learner's QR card; identifies the learner when scanned (not a secret).
    qr_code = models.CharField(max_length=16, unique=True, default=new_qr_code)
    # Secret link for the learner or parent to see attendance and grades (read-only).
    share_token = models.CharField(max_length=40, unique=True, default=new_share_token)
    seat_row = models.PositiveSmallIntegerField(null=True, blank=True)
    seat_col = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        # Class records list boys first, then girls, each alphabetically.
        ordering = ["-sex", "last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "seat_row", "seat_col"],
                condition=models.Q(seat_row__isnull=False),
                name="one_learner_per_seat",
            ),
            models.CheckConstraint(
                condition=models.Q(seat_row__isnull=True, seat_col__isnull=True)
                | models.Q(seat_row__isnull=False, seat_col__isnull=False),
                name="seat_row_and_col_together",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def name(self) -> str:
        return f"{self.last_name}, {self.first_name}"

    @property
    def short_name(self) -> str:
        return f"{self.first_name} {self.last_name[:1]}."

    @property
    def initials(self) -> str:
        return (self.first_name[:1] + self.last_name[:1]).upper()

    @property
    def is_seated(self) -> bool:
        return self.seat_row is not None
