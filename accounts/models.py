from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A teacher. Demo teachers are created by "Try the demo" and deleted after a day."""

    is_demo = models.BooleanField(default=False, db_index=True)

    @property
    def display_name(self) -> str:
        return self.first_name or self.username
