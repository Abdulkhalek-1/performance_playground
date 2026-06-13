import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "ecommerce",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

# django-silk is opt-in: it instruments every request and would pollute load-test
# numbers, so it is only enabled when DJANGO_SILK=1.
SILK_ENABLED = os.environ.get("DJANGO_SILK", "0") == "1"
if SILK_ENABLED:
    INSTALLED_APPS.append("silk")
    MIDDLEWARE.insert(0, "silk.middleware.SilkyMiddleware")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "playground"),
        "USER": os.environ.get("POSTGRES_USER", "playground"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "playground"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
