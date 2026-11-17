"""Tala settings. Every environment-specific value comes from environment variables."""

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Required: fail loudly at startup instead of running with a guessable key.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG")  # off unless explicitly turned on
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")  # set by Render
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "classroom",
    "attendance",
    "grades",
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "classroom:dashboard"
LOGOUT_REDIRECT_URL = "home"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

# Strict CSP: no inline scripts (a test enforces it), fonts from Google Fonts only.
_FONT_CSS, _FONT_FILES = "https://fonts.googleapis.com", "https://fonts.gstatic.com"
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        f"style-src 'self' {_FONT_CSS}",
        f"font-src 'self' {_FONT_FILES}",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
PERMISSIONS_POLICY = (
    # camera=(self): the attendance scanner reads learners' QR cards with the phone camera.
    "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"
)

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"


def database_from_url(url: str) -> dict:
    """postgres:// URL (what hosted Postgres such as Neon hands out) -> Django settings."""
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must start with postgres:// or postgresql://")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        # Hosted Postgres sits across a TLS handshake and may be suspended: keep connections for a
        # minute, check them before reuse, and give up after 10 s instead of hanging a worker.
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 10, **dict(parse_qsl(parts.query))},
    }


DATABASES = {
    "default": database_from_url(os.environ["DATABASE_URL"])
    if os.environ.get("DATABASE_URL")
    else {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "tala"),
        "USER": os.environ.get("POSTGRES_USER", "tala"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Rate-limit counters live in Postgres (not process memory), so every worker shares them and the
# web container stays stateless. Table created by `createcachetable` (start script / compose).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "tala_cache",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Manila")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if env_bool("DJANGO_STATIC_MANIFEST")
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
WHITENOISE_USE_FINDERS = not env_bool("DJANGO_STATIC_MANIFEST")

if env_bool("DJANGO_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^livez/$", r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SILENCED_SYSTEM_CHECKS = ["security.W021"]  # HSTS preload is opt-in, hard to undo
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_HTTPONLY = True

# Header (request.META key) with the real visitor IP, set by a proxy that overwrites it, e.g.
# HTTP_CF_CONNECTING_IP behind Cloudflare/Render. Empty: use the socket address. Never point it at
# X-Forwarded-For, which clients can forge. Used to rate-limit demo sign-ins.
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")

# ---- Demo ----------------------------------------------------------------------------------------
# "Try the demo" creates a private demo teacher with fake classes (Faker, never real learners), so
# visitors never see or change each other's data. Accounts older than DEMO_TTL_HOURS are deleted on
# start (bin/start.sh runs purge_demo). Per visitor IP per hour:
DEMO_ACCOUNTS_PER_HOUR = int(os.environ.get("DEMO_ACCOUNTS_PER_HOUR", "10"))
DEMO_TTL_HOURS = int(os.environ.get("DEMO_TTL_HOURS", "24"))
# Sign-in attempts per IP per 15 minutes.
LOGINS_PER_WINDOW = int(os.environ.get("LOGINS_PER_WINDOW", "20"))

SESSION_COOKIE_AGE = 12 * 3600

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
