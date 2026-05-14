"""Django settings for the OMR OCR validator app."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-secret-key-change-me-in-production",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "validator",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "omr_validator.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "omr_validator.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

# Image data lives outside the Django project so users can drop files in
# without touching the app source. Override with OMR_DATA_DIR if needed.
DATA_DIR = Path(os.environ.get("OMR_DATA_DIR", BASE_DIR / "data"))
OMR_IMAGES_DIR = DATA_DIR / "omr_images"
EXTRACTED_SECTIONS_DIR = DATA_DIR / "extracted_sections"

MEDIA_URL = "/media/"
MEDIA_ROOT = DATA_DIR

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OCR configuration
# Set OMR_MOCK_OCR=1 to skip loading heavy ML models and use deterministic
# stub outputs (useful for UI development).
MOCK_OCR = os.environ.get("OMR_MOCK_OCR", "0") == "1"

GLM_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4v-flash")

TROCR_MODEL = os.environ.get("TROCR_MODEL", "microsoft/trocr-base-printed")
DOTS_OCR_MODEL = os.environ.get("DOTS_OCR_MODEL", "rednote-hilab/dots.ocr")
