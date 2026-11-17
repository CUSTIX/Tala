"""A small fixed-window rate limit on the shared cache (Postgres), so all workers agree."""

import time

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    header = settings.CLIENT_IP_HEADER
    ip = request.META.get(header, "") if header else ""
    return (ip or request.META.get("REMOTE_ADDR", "") or "unknown").split(",")[0].strip()


def hit(scope: str, key: str, limit: int, window: int = 3600) -> bool:
    """Count one event. Returns False when the limit for this window is already used up."""
    bucket = f"throttle:{scope}:{key}:{int(time.time() // window)}"
    added = cache.add(bucket, 1, timeout=window)
    if added:
        return True
    try:
        count = cache.incr(bucket)
    except ValueError:  # expired between add and incr
        cache.add(bucket, 1, timeout=window)
        return True
    return count <= limit
