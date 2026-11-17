from django.urls import path

from classroom import views

app_name = "classroom"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("classes/new/", views.section_create, name="section_create"),
    path("classes/<int:pk>/", views.section_detail, name="section"),
    path("classes/<int:pk>/edit/", views.section_edit, name="section_edit"),
    path("classes/<int:pk>/delete/", views.section_delete, name="section_delete"),
    path("classes/<int:pk>/learners/add/", views.learners_add, name="learners_add"),
    path("classes/<int:pk>/learners/<int:learner_pk>/", views.learner_detail, name="learner"),
    path(
        "classes/<int:pk>/learners/<int:learner_pk>/edit/", views.learner_edit, name="learner_edit"
    ),
    path(
        "classes/<int:pk>/learners/<int:learner_pk>/delete/",
        views.learner_delete,
        name="learner_delete",
    ),
    path(
        "classes/<int:pk>/learners/<int:learner_pk>/new-link/",
        views.learner_new_link,
        name="learner_new_link",
    ),
    path("classes/<int:pk>/qr-cards/", views.qr_cards, name="qr_cards"),
    path("classes/<int:pk>/seats/", views.seat_plan, name="seats"),
    path("classes/<int:pk>/picker/", views.picker, name="picker"),
]
