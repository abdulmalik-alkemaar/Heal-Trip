"""
Production settings for healtrip project.
Extends base settings with production-specific overrides.
"""

import dj_database_url
from decouple import Csv, config

from .settings import *  # noqa: F401, F403
from .settings import DATABASES, REST_FRAMEWORK

DEBUG = False

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

# Database - PostgreSQL. DATABASE_URL is REQUIRED here (no local default): fail fast.
# Only "default" is replaced so the optional least-privilege "tools_readonly" alias survives.
DATABASES["default"] = dj_database_url.parse(config("DATABASE_URL"), conn_max_age=60)

# Cache - Redis when available (shared throttle counters across gunicorn workers).
# Without REDIS_URL, fall back to per-process memory: per-IP limits get weaker (x workers),
# but the global DEMO_DAILY_MESSAGE_CAP is DB-backed and still holds.
REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }

# Security
# SECURE_SSL_REDIRECT not needed — Railway enforces HTTPS at the edge (and a redirect here
# would break the internal http health checks), so the matching deploy check is silenced.
SILENCED_SYSTEM_CHECKS = ["security.W008"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Demo safety: stricter defaults than development (all overridable via env).
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],
        "chat_minute": f"{config('CHAT_RATE_PER_MINUTE', default=10, cast=int)}/min",
        "chat_day": f"{config('CHAT_RATE_PER_DAY', default=60, cast=int)}/day",
        "session_create": config("SESSION_CREATE_RATE", default="10/hour"),
    },
    # Railway edge -> frontend nginx -> Django: the client IP is 2 hops back in X-Forwarded-For.
    "NUM_PROXIES": config("NUM_PROXIES", default=2, cast=int),
}
DEMO_DAILY_MESSAGE_CAP = config("DEMO_DAILY_MESSAGE_CAP", default=500, cast=int)

# Structured JSON logs in production.
LOGGING["handlers"]["default"]["formatter"] = config("LOG_FORMAT", default="json")  # noqa: F405

# Django-Q2 (Redis broker for production)
Q_CLUSTER = {
    "name": "healtrip_production",
    "workers": config("DJANGO_Q_WORKERS", default=8, cast=int),
    "timeout": config("DJANGO_Q_TIMEOUT", default=900, cast=int),
    "retry": config("DJANGO_Q_RETRY", default=960, cast=int),
    "django_redis": "default",
    "max_attempts": 2,
    "ack_failures": True,
    "save_limit": 1000,
}
