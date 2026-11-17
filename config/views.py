from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache


@never_cache
def livez(request):
    """The process is up. No database query, so a suspended free database can stay asleep."""
    return HttpResponse("ok", content_type="text/plain")


@never_cache
def healthz(request):
    """The app can reach its database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
