from django.contrib import admin

from attendance.models import Meeting


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ["section", "date"]
    list_select_related = ["section"]
    date_hierarchy = "date"
