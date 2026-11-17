from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class TeacherAdmin(UserAdmin):
    list_display = ["username", "first_name", "is_demo", "is_staff", "date_joined"]
    list_filter = ["is_demo", "is_staff"]
