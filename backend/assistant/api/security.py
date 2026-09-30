"""Request-level protections for the chat API.

- CSRF: enforced for anonymous users too (see authentication.py).
- Throttles: per IP (burst + daily) and per chat session. These protect the
  demo's LLM budget, and a global daily cap bounds the worst case.
- Ownership: a chat session is accessible only from the browser session that
  created it (or its logged-in owner). Guessing a UUID gets you a 404.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from assistant.models import AgentRunLog, ChatSession

from .errors import DailyCapReached

OWNED_SESSIONS_KEY = "chat_session_ids"
MAX_OWNED_SESSIONS = 50


# --- Ownership --------------------------------------------------------------
def remember_session(request: Request, chat: ChatSession) -> None:
    owned = request.session.get(OWNED_SESSIONS_KEY, [])
    owned = [*owned, str(chat.id)][-MAX_OWNED_SESSIONS:]
    request.session[OWNED_SESSIONS_KEY] = owned


def owns(request: Request, chat: ChatSession) -> bool:
    if str(chat.id) in request.session.get(OWNED_SESSIONS_KEY, []):
        return True
    user = request.user
    return bool(user and user.is_authenticated and chat.user_id == user.pk)


def get_owned_session(request: Request, session_id: UUID) -> ChatSession | None:
    chat = ChatSession.objects.filter(pk=session_id).first()
    return chat if chat and owns(request, chat) else None


# --- Throttles --------------------------------------------------------------
class ChatIPBurstThrottle(SimpleRateThrottle):
    """N messages per minute per client IP."""

    scope = "chat_minute"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class ChatIPDailyThrottle(ChatIPBurstThrottle):
    scope = "chat_day"


class ChatSessionThrottle(SimpleRateThrottle):
    """N messages per minute per chat session (independent of IP)."""

    scope = "chat_session"

    def get_cache_key(self, request, view):
        session_id = view.kwargs.get("session_id")
        return (
            self.cache_format % {"scope": self.scope, "ident": str(session_id)}
            if session_id
            else None
        )


class SessionCreateThrottle(ChatIPBurstThrottle):
    scope = "session_create"


class GlobalDailyCapThrottle(BaseThrottle):
    """Hard cap on assistant turns per 24h across ALL users (DEMO_DAILY_MESSAGE_CAP; 0 = off).

    Counted from AgentRunLog in the DB, so it holds across processes and restarts.
    """

    def allow_request(self, request, view) -> bool:
        cap = settings.DEMO_DAILY_MESSAGE_CAP
        if cap <= 0:
            return True
        since = timezone.now() - timedelta(days=1)
        if AgentRunLog.objects.filter(created_at__gte=since).count() >= cap:
            raise DailyCapReached()
        return True
