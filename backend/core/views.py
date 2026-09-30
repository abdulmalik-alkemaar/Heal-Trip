from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class CSRFTokenView(APIView):
    """Set CSRF cookie for the React SPA."""

    permission_classes = [AllowAny]

    def get(self, request):
        from django.middleware.csrf import get_token

        get_token(request)
        return Response({"detail": "CSRF cookie set"})


class ProfileView(APIView):
    """Get or update current user profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class HealthCheckView(APIView):
    """Simple health check endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})
