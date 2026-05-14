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

# Pipeline outputs from crop_omr.py and extract_sections.py.
# Default layout (Part-D):
#     data screen/part-d/01/<sheet>.jpg              # raw scans (input to crop)
#     output/cropped/part-d/<sheet>.jpg              # cropped sheets
#     output/sections/part-d/<sheet>/<section>.jpg   # section crops
PIPELINE_ROOT = Path(os.environ.get("OMR_PIPELINE_ROOT", BASE_DIR / "output"))
OMR_IMAGES_DIR = PIPELINE_ROOT / "cropped" / "part-d"
EXTRACTED_SECTIONS_DIR = PIPELINE_ROOT / "sections" / "part-d"

# extract_sections.py produces 15 crops per sheet but only these three are
# handwritten text we want to label. ``ingest_data`` skips the rest, so they
# stay on disk but never appear in the labeling queue.
LABEL_SECTION_TYPES = [
    "registration_no",
    "roll_no_written",
    "course_code_written",
]

# MEDIA_ROOT covers both cropped sheets and section crops so the labeling UI
# can serve either through MEDIA_URL.
MEDIA_URL = "/media/"
MEDIA_ROOT = PIPELINE_ROOT

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OCR configuration
# Set OMR_MOCK_OCR=1 to skip loading heavy ML models and use deterministic
# stub outputs (useful for UI development).
MOCK_OCR = os.environ.get("OMR_MOCK_OCR", "0") == "1"

GLM_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4v-flash")

TROCR_MODEL = os.environ.get("TROCR_MODEL", "microsoft/trocr-base-handwritten")
DOTS_OCR_MODEL = os.environ.get("DOTS_OCR_MODEL", "rednote-hilab/dots.ocr")
