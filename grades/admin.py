from django.contrib import admin

from grades.models import Assessment


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ["title", "section", "quarter", "component", "max_score", "date"]
    list_select_related = ["section"]
    list_filter = ["quarter", "component"]
