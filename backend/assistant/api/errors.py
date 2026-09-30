"""One error format for the whole API:

    {"error": {"code": "...", "message_en": "...", "message_ar": "...", "details": {...}?}}

`code` is stable and machine-readable (the frontend switches on it); the messages
are safe to show to patients. Internal details (stack traces, SQL) never leak.
"""

from __future__ import annotations

import logging
from typing import Any

from django.http import Http404, JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

MESSAGES: dict[str, tuple[str, str]] = {
    "validation_error": ("Some of the information sent is invalid.", "بعض المعلومات المرسلة غير صحيحة."),
    "not_found": ("Not found.", "غير موجود."),
    "rate_limited": ("Too many requests. Please wait a moment and try again.", "طلبات كثيرة. يرجى الانتظار قليلًا ثم المحاولة مجددًا."),
    "daily_cap_reached": ("The demo has reached today's message limit. Please try again tomorrow. In an emergency call 997.", "وصل العرض التجريبي إلى الحد اليومي للرسائل. يرجى المحاولة غدًا. في الحالات الطارئة اتصل على 997."),
    "session_limit_reached": ("This conversation has reached its message limit. Please start a new conversation.", "وصلت هذه المحادثة إلى الحد الأقصى للرسائل. يرجى بدء محادثة جديدة."),
    "csrf_failed": ("Your session expired. Please reload the page.", "انتهت صلاحية الجلسة. يرجى إعادة تحميل الصفحة."),
    "forbidden": ("You don't have permission to do that.", "ليست لديك صلاحية لهذا الإجراء."),
    "not_authenticated": ("Please sign in.", "يرجى تسجيل الدخول."),
    "method_not_allowed": ("Method not allowed.", "الطريقة غير مسموح بها."),
    "parse_error": ("The request body is not valid JSON.", "محتوى الطلب ليس JSON صالحًا."),
    "unsupported_media_type": ("Unsupported content type.", "نوع المحتوى غير مدعوم."),
    "internal_error": ("Something went wrong on our side. If this is an emergency call 997.", "حدث خطأ من جهتنا. إذا كانت حالة طارئة فاتصل على 997."),
}  # fmt: skip


def error_body(code: str, details: Any = None) -> dict[str, Any]:
    message_en, message_ar = MESSAGES.get(code, MESSAGES["internal_error"])
    body: dict[str, Any] = {"code": code, "message_en": message_en, "message_ar": message_ar}
    if details:
        body["details"] = details
    return {"error": body}


class APIError(exceptions.APIException):
    """Base for our own errors: subclasses set `status_code` and `error_code`."""

    error_code = "internal_error"


class SessionLimitReached(APIError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "session_limit_reached"


class DailyCapReached(APIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "daily_cap_reached"


def _code_for(exc: Exception) -> str:
    if isinstance(exc, APIError):
        return exc.error_code
    if isinstance(exc, exceptions.ValidationError):
        return "validation_error"
    if isinstance(exc, (exceptions.NotFound, Http404)):
        return "not_found"
    if isinstance(exc, exceptions.Throttled):
        return "rate_limited"
    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        return "not_authenticated"
    if isinstance(exc, exceptions.PermissionDenied):
        return "csrf_failed" if "CSRF" in str(exc.detail) else "forbidden"
    if isinstance(exc, exceptions.MethodNotAllowed):
        return "method_not_allowed"
    if isinstance(exc, exceptions.ParseError):
        return "parse_error"
    if isinstance(exc, exceptions.UnsupportedMediaType):
        return "unsupported_media_type"
    return "internal_error"


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """DRF EXCEPTION_HANDLER: wrap every error (including unexpected ones) in our format."""
    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception: log it with the stack trace, answer with a generic 500.
        logger.exception("unhandled_api_error", extra={"view": type(context.get("view")).__name__})
        return Response(error_body("internal_error"), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    code = _code_for(exc)
    details = response.data if code == "validation_error" else None
    if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        details = {"retry_after_seconds": int(exc.wait)}
    response.data = error_body(code, details)
    return response


def json_404(request, exception=None) -> JsonResponse:
    """handler404 for non-DRF routes (e.g. unknown /api/ paths)."""
    return JsonResponse(error_body("not_found"), status=404)


def json_500(request) -> JsonResponse:
    return JsonResponse(error_body("internal_error"), status=500)
