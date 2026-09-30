"""
Django settings for healtrip project - Development configuration.
"""

from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="django-insecure-dev-key-change-in-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

AUTH_USER_MODEL = "core.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third party
    "rest_framework",
    "corsheaders",
    "django_q",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Local
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "healtrip.urls"

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

WSGI_APPLICATION = "healtrip.wsgi.application"

# Database - PostgreSQL everywhere (dev, test, CI, prod). We deliberately do NOT
# fall back to SQLite: provider search relies on Postgres features (ArrayField
# for doctor languages) and dev/prod parity avoids "works on my machine" bugs.
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default="postgresql://healtrip:healtrip@localhost:5432/healtrip"),
        conn_max_age=60,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# CORS (development only)
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())
CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="http://localhost:3000,http://localhost:8000", cast=Csv()
)
CSRF_COOKIE_HTTPONLY = False  # Allow JS to read CSRF token
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Login redirects
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/app/login"
LOGOUT_REDIRECT_URL = f"{FRONTEND_URL}/app"

# Django-Q2 (ORM broker for development)
Q_CLUSTER = {
    "name": "healtrip_dev",
    "workers": 4,
    "timeout": 600,
    "retry": 660,
    "orm": "default",
}

# django-allauth
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": config("GOOGLE_CLIENT_ID", default=""),
            "secret": config("GOOGLE_CLIENT_SECRET", default=""),
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}

# Site URL
SITE_URL = config("SITE_URL", default="http://localhost:8000")

# ---------------------------------------------------------------------------
# LLM / Agent configuration
# ---------------------------------------------------------------------------
# The API key is read ONLY here, from the environment. It is never serialized
# into any API response, never logged, and never sent to the frontend.
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")
# "anthropic" = real Claude API; "mock" = deterministic scripted client (tests/CI/offline demo).
LLM_PROVIDER = config("LLM_PROVIDER", default="mock")
LLM_MODEL = config("LLM_MODEL", default="claude-sonnet-5-5")
# Effort controls thinking depth / token spend. Patient navigation is a chat-style
# task, so "medium" is a sensible default; tune via env without code changes.
LLM_EFFORT = config("LLM_EFFORT", default="medium")
LLM_MAX_TOKENS = config("LLM_MAX_TOKENS", default=4096, cast=int)
LLM_TIMEOUT_SECONDS = config("LLM_TIMEOUT_SECONDS", default=30, cast=float)
LLM_MAX_RETRIES = config("LLM_MAX_RETRIES", default=3, cast=int)
# Server-side refusal fallback (Claude API only). If the primary model declines a
# request on safety grounds, the API re-runs it on a fallback model in the same call.
LLM_REFUSAL_FALLBACK = config("LLM_REFUSAL_FALLBACK", default=True, cast=bool)
AGENT_MAX_ITERATIONS = config("AGENT_MAX_ITERATIONS", default=5, cast=int)
AGENT_MAX_CLARIFICATION_ROUNDS = config("AGENT_MAX_CLARIFICATION_ROUNDS", default=3, cast=int)
