from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from core import throttle
from core.demo import create_demo_teacher


def _too_many(request, message: str):
    return HttpResponse(
        render_to_string("core/error.html", {"title": "Slow down", "message": message}, request),
        status=429,
    )


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = throttle.client_ip(request)
        if not throttle.hit("login", ip, settings.LOGINS_PER_WINDOW, window=900):
            return _too_many(request, "Too many sign-in attempts. Try again in 15 minutes.")
        return super().post(request, *args, **kwargs)


@require_POST
def demo(request):
    """Create a private demo teacher with fake classes and sign in as them."""
    if request.user.is_authenticated and request.user.is_demo:
        return redirect("classroom:dashboard")
    ip = throttle.client_ip(request)
    if not throttle.hit("demo", ip, settings.DEMO_ACCOUNTS_PER_HOUR):
        return _too_many(request, "That's a lot of demo classes. Try again in an hour.")
    user = create_demo_teacher()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(
        request,
        "Welcome! This demo is yours alone: three classes of made-up learners. "
        "It is deleted after a day.",
    )
    return redirect("classroom:dashboard")
