from django.urls import path

from attendance import views

app_name = "attendance"
urlpatterns = [
    path("classes/<int:pk>/attendance/", views.take, name="take"),
    path("classes/<int:pk>/attendance/scan/", views.scan, name="scan"),
    path("classes/<int:pk>/attendance/scan/mark/", views.scan_mark, name="scan_mark"),
    path("classes/<int:pk>/attendance/report/", views.report, name="report"),
]
