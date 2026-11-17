from django.contrib import admin

from classroom.models import Learner, Section


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "teacher", "school_year"]
    list_select_related = ["teacher"]
    search_fields = ["name", "subject"]


@admin.register(Learner)
class LearnerAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "sex", "section"]
    list_select_related = ["section"]
    search_fields = ["last_name", "first_name"]
    exclude = ["share_token"]
