"""Production-only security and environment settings."""

import os

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

from .settings_base import *  # noqa: F403


DEBUG = False


def _required_environment(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required production environment variable is missing: {name}")
    return value


SECRET_KEY = _required_environment("SECRET_KEY")
FIELD_ENCRYPTION_KEY = _required_environment("FIELD_ENCRYPTION_KEY")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Production SECRET_KEY must contain at least 50 characters")
try:
    Fernet(FIELD_ENCRYPTION_KEY.encode())
except Exception as exc:
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not a valid Fernet key") from exc

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "multilang.uz,.multilang.uz,77.42.31.194",
    ).split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "https://multilang.uz,https://*.multilang.uz",
    ).split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "300"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

TRUSTED_PROXY_IPS = [
    network.strip()
    for network in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1/32,::1/128").split(",")
    if network.strip()
]

DATABASES["default"]["CONN_MAX_AGE"] = int(os.getenv("DB_CONN_MAX_AGE", "60"))  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405
if "postgresql" not in DATABASES["default"]["ENGINE"]:  # noqa: F405
    raise ImproperlyConfigured("Production requires PostgreSQL; set USE_POSTGRES=true")

# HSTS is intentionally staged at a short max-age without subdomains/preload.
# Those two deployment checks are silenced until the documented rollout has
# confirmed HTTPS on every tenant hostname; all other deploy checks still run.
SILENCED_SYSTEM_CHECKS = [
    *globals().get("SILENCED_SYSTEM_CHECKS", []),
    "security.W005",
    "security.W021",
]
