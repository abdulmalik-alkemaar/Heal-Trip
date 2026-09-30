from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class CSRFTokenView(APIView):
    """Set CSRF cookie for the React SPA."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["ops"], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        from django.middleware.csrf import get_token

        get_token(request)
        return Response({"detail": "CSRF cookie set"})


class ProfileView(APIView):
    """Get or update current user profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], responses={200: UserSerializer})
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @extend_schema(tags=["auth"], request=UserSerializer, responses={200: UserSerializer})
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


@extend_schema(tags=["ops"])
class HealthCheckView(APIView):
    """Liveness + dependency status. Reports configuration *presence*, never secret values."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: OpenApiTypes.OBJECT, 503: OpenApiTypes.OBJECT})
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database = "ok"
        except DatabaseError:
            database = "error"
        body = {
            "status": "ok" if database == "ok" else "degraded",
            "database": database,
            "llm": {
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL
                if settings.LLM_PROVIDER == "anthropic"
                else "mock-scripted",
                "api_key_configured": bool(settings.ANTHROPIC_API_KEY),
            },
            "agent": {
                "max_iterations": settings.AGENT_MAX_ITERATIONS,
                "max_clarification_rounds": settings.AGENT_MAX_CLARIFICATION_ROUNDS,
            },
        }
        return Response(body, status=200 if database == "ok" else 503)
