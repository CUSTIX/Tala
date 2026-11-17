from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        return redirect("classroom:dashboard")
    return render(request, "core/home.html")


def _error(request, status, title, message):
    return render(request, "core/error.html", {"title": title, "message": message}, status=status)


def forbidden(request, exception=None):
    return _error(request, 403, "Not allowed", "You can't open this page.")


def not_found(request, exception=None):
    return _error(request, 404, "Not found", "This page doesn't exist, or it isn't yours.")


def server_error(request):
    # Self-contained: no database queries or context that could fail again.
    return render(request, "500.html", status=500)
