"""Authentication class kept in its own dependency-free module: DRF imports
DEFAULT_AUTHENTICATION_CLASSES while `rest_framework.views` is still loading."""

from rest_framework.authentication import SessionAuthentication


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """Session auth that enforces CSRF for anonymous requests too.

    DRF's SessionAuthentication only checks CSRF for logged-in users. Our anonymous
    chat ownership rides on the session cookie, so an unsafe request from another
    site must be rejected even when nobody is logged in.
    """

    def authenticate(self, request):
        self.enforce_csrf(request)  # no-op for safe methods (GET/HEAD/OPTIONS)
        user = getattr(request._request, "user", None)
        if not user or not user.is_active or not user.is_authenticated:
            return None
        return (user, None)
