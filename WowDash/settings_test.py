"""Hermetic settings for local and CI test execution."""

import os

os.environ["SENTRY_DSN"] = ""
os.environ.setdefault("USE_REDIS", "False")

from .settings_base import *  # noqa: E402,F403


DEBUG = False
TESTING = True
DISABLE_SUBSCRIPTION_ENFORCEMENT = True
SECRET_KEY = "test-only-secret-key"
FIELD_ENCRYPTION_KEY = ""
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
TEST_RUNNER = "WowDash.test_runner.HermeticDiscoverRunner"

if os.getenv("TEST_USE_POSTGRES", "False").lower() != "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "wowdash-tests",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
