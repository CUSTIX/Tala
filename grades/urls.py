from django.urls import path

from grades import views

app_name = "grades"
urlpatterns = [
    path("classes/<int:pk>/grades/", views.gradebook, name="book"),
    path("classes/<int:pk>/grades/final/", views.final, name="final"),
    path("classes/<int:pk>/grades/new/", views.assessment_create, name="create"),
    path("classes/<int:pk>/grades/<int:assessment_pk>/", views.scores, name="scores"),
    path("classes/<int:pk>/grades/<int:assessment_pk>/edit/", views.assessment_edit, name="edit"),
    path(
        "classes/<int:pk>/grades/<int:assessment_pk>/delete/",
        views.assessment_delete,
        name="delete",
    ),
    path("classes/<int:pk>/grades/<int:assessment_pk>/items/", views.items, name="items"),
    path("classes/<int:pk>/grades/<int:assessment_pk>/answers/", views.responses, name="responses"),
    path("classes/<int:pk>/grades/<int:assessment_pk>/analysis/", views.analysis, name="analysis"),
]
