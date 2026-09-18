"""
Django settings for the Zoomart Expense & Request Approval Platform.
"""

from pathlib import Path
from decouple import config as env

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-key-change-in-production")

DEBUG = env("DJANGO_DEBUG", default=True, cast=bool)

ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", default="*").split(",")
CSRF_TRUSTED_ORIGINS = env(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="https://*.onrender.com",
).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "auditlog",
    "accounts",
    "core",
    "requests_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.nav_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---------------------------------------------------------
# Development/demo: SQLite (zero setup). Production: switch to PostgreSQL
# by setting DATABASE_URL / the DJANGO_DB_* env vars below.
DATABASES = {
    "default": {
        "ENGINE": env("DJANGO_DB_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": env("DJANGO_DB_NAME", default=str(BASE_DIR / "db.sqlite3")),
        "USER": env("DJANGO_DB_USER", default=""),
        "PASSWORD": env("DJANGO_DB_PASSWORD", default=""),
        "HOST": env("DJANGO_DB_HOST", default=""),
        "PORT": env("DJANGO_DB_PORT", default=""),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ka"
TIME_ZONE = "Asia/Tbilisi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.StaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# --- Secure file upload rules (spec section 6 / 13) --------------------
ALLOWED_ATTACHMENT_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".docx"]
MAX_ATTACHMENT_SIZE_MB = 10
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024 + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024 + 1024 * 1024

# --- Approval amount tiers (defaults; editable later from Admin) -------
# Kept here as a documented fallback only; the real, editable rules live
# in the ApprovalWorkflowRule / ApprovalStepRule tables (core app).

MESSAGE_TAGS = {}

# --- Email (approval-step notifications) --------------------------------
# Off by default (console backend = nothing actually sent, just logged) so
# the app keeps working with zero configuration. To turn on real email,
# set EMAIL_HOST_USER / EMAIL_HOST_PASSWORD as environment variables
# (e.g. a Gmail address + an "App Password" for it) and the SMTP backend
# activates automatically — no code changes needed.
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = env("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "noreply@zoomart.ge")

# Used to build absolute links (e.g. "ნახეთ მოთხოვნა") inside notification emails.
SITE_URL = env("SITE_URL", default="http://localhost:8000")
