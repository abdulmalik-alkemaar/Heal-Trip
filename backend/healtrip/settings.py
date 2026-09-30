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
    "django.contrib.postgres",
    # Third party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_q",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Local
    "core",
    "providers",
    "assistant",
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
    # Session auth that enforces CSRF for anonymous users too: chat ownership rides on
    # the session cookie, so unsafe requests must prove they come from our frontend.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "assistant.api.authentication.CsrfEnforcedSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # One error format everywhere: {"error": {"code", "message_en", "message_ar"}}
    "EXCEPTION_HANDLER": "assistant.api.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Views opt in via `throttle_scope`; chat views declare their own throttle classes.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "public": config("PUBLIC_RATE", default="120/min"),
        "chat_minute": f"{config('CHAT_RATE_PER_MINUTE', default=20, cast=int)}/min",
        "chat_day": f"{config('CHAT_RATE_PER_DAY', default=200, cast=int)}/day",
        "chat_session": config("CHAT_SESSION_RATE", default="10/min"),
        "session_create": config("SESSION_CREATE_RATE", default="30/hour"),
    },
    # Client IP from X-Forwarded-For behind exactly N trusted proxies (Railway edge + nginx).
    "NUM_PROXIES": config("NUM_PROXIES", default=None, cast=lambda v: int(v) if v else None),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "HealTrip AI Patient Decision Assistant API",
    "DESCRIPTION": (
        "Chat API for the patient navigation agent plus the read-only provider directory. "
        "All provider data is fictional. Not medical advice."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {"LanguageCodeEnum": "providers.choices.LanguageCode"},
}

# Chat abuse / budget limits
CHAT_MAX_MESSAGES_PER_SESSION = config("CHAT_MAX_MESSAGES_PER_SESSION", default=50, cast=int)
DEMO_DAILY_MESSAGE_CAP = config("DEMO_DAILY_MESSAGE_CAP", default=0, cast=int)  # 0 = no cap
CHAT_RETENTION_DAYS = config("CHAT_RETENTION_DAYS", default=30, cast=int)

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

# ---------------------------------------------------------------------------
# Least privilege for agent tools (optional)
# ---------------------------------------------------------------------------
# If DATABASE_URL_READONLY is set, every tool query runs on a connection whose role
# can only SELECT the provider directory tables (see docs/sql/readonly_role.sql).
# Even a bug in a tool could then neither write data nor read chat history.
DATABASE_URL_READONLY = config("DATABASE_URL_READONLY", default="")
if DATABASE_URL_READONLY:
    DATABASES["tools_readonly"] = {
        **dj_database_url.parse(DATABASE_URL_READONLY, conn_max_age=60),
        "TEST": {"MIRROR": "default"},
    }
TOOLS_DB_ALIAS = "tools_readonly" if DATABASE_URL_READONLY else "default"

# ---------------------------------------------------------------------------
# Logging: PII-redacted; JSON lines in production (LOG_FORMAT=json)
# ---------------------------------------------------------------------------
LOG_FORMAT = config("LOG_FORMAT", default="console")
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact_pii": {"()": "healtrip.logging.PiiRedactingFilter"}},
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {"asctime": "ts", "levelname": "level", "name": "logger"},
        },
        "console": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "console",
            "filters": ["redact_pii"],
        }
    },
    "root": {"handlers": ["default"], "level": LOG_LEVEL},
    "loggers": {
        # The SDK can log request bodies at DEBUG; keep it at WARNING so patient text
        # and headers never reach the logs.
        "anthropic": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
        "httpx2": {"level": "WARNING"},
    },
}
AGENT_MAX_CLARIFICATION_ROUNDS = config("AGENT_MAX_CLARIFICATION_ROUNDS", default=3, cast=int)
