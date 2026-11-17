from django.contrib import admin
from django.urls import include, path

from classroom.views import share
from config import views
from core import views as core

urlpatterns = [
    path("", core.home, name="home"),
    path("accounts/", include("accounts.urls")),
    path("app/", include("classroom.urls")),
    path("app/", include("attendance.urls")),
    path("app/", include("grades.urls")),
    path("s/<str:token>/", share, name="share"),
    path("admin/", admin.site.urls),
    path("livez/", views.livez, name="livez"),
    path("healthz/", views.healthz, name="healthz"),
]

handler403 = "core.views.forbidden"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
