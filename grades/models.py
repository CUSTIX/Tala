from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from classroom.models import Learner, Section
from core.models import TimeStamped


class Component(models.TextChoices):
    WRITTEN = "WW", "Written Work"
    PERFORMANCE = "PT", "Performance Tasks"
    QUARTERLY = "QA", "Quarterly Assessment"


class Assessment(TimeStamped):
    """A quiz, task or exam. Its highest possible score (HPS) is max_score."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="assessments")
    quarter = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    component = models.CharField(max_length=2, choices=Component.choices)
    title = models.CharField(max_length=80)
    max_score = models.DecimalField(
        "highest possible score",
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
    )
    date = models.DateField()

    class Meta:
        ordering = ["quarter", "component", "date", "id"]
        indexes = [models.Index(fields=["section", "quarter"])]

    def __str__(self):
        return self.title

    @property
    def has_items(self) -> bool:
        return self.items.exists()


class Score(TimeStamped):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="scores")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="scores")
    raw = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["assessment", "learner"], name="one_score_each"),
            models.CheckConstraint(condition=models.Q(raw__gte=0), name="score_not_negative"),
        ]


class Item(TimeStamped):
    """One question of a quiz, tagged with the competency it tests (for item analysis)."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    number = models.PositiveSmallIntegerField()
    competency = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "number"], name="one_item_number")
        ]


class Response(TimeStamped):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="responses")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="responses")
    correct = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "learner"], name="one_response_each")
        ]
