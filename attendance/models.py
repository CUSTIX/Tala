from django.db import models

from classroom.models import Learner, Section
from core.models import TimeStamped


class Status(models.TextChoices):
    PRESENT = "P", "Present"
    LATE = "L", "Late"
    EXCUSED = "E", "Excused"
    ABSENT = "A", "Absent"


class Via(models.TextChoices):
    LIST = "list", "List"
    SEATS = "seats", "Seat plan"
    QR = "qr", "QR scan"


class Meeting(TimeStamped):
    """One class day for a section."""

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="meetings")
    date = models.DateField()

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["section", "date"], name="one_meeting_per_day")
        ]

    def __str__(self):
        return f"{self.section} on {self.date}"


class Mark(TimeStamped):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="marks")
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="marks")
    status = models.CharField(max_length=1, choices=Status.choices)
    via = models.CharField(max_length=5, choices=Via.choices, default=Via.LIST)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["meeting", "learner"], name="one_mark_per_learner")
        ]
        indexes = [models.Index(fields=["learner", "status"])]
