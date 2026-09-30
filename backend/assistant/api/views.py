"""Chat API. Anonymous by default (reviewers need no login); optional Google login
attaches sessions to the user for cross-device history."""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from assistant.agent.orchestrator import handle_message
from assistant.agent.texts import DISCLAIMER
from assistant.models import ChatSession, Message

from .errors import SessionLimitReached
from .security import (
    ChatIPBurstThrottle,
    ChatIPDailyThrottle,
    ChatSessionThrottle,
    GlobalDailyCapThrottle,
    SessionCreateThrottle,
    get_owned_session,
    remember_session,
)
from .serializers import (
    CreateSessionSerializer,
    SendMessageSerializer,
    SessionCreatedSerializer,
    SessionDetailSerializer,
    TurnResponseSerializer,
    render_session,
    render_turn,
)


class _ChatAPIView(APIView):
    permission_classes = [AllowAny]  # authorization = session ownership (see security.py)

    def owned_session(self, request: Request, session_id: UUID) -> ChatSession:
        chat = get_owned_session(request, session_id)
        if chat is None:
            raise NotFound()  # same answer for "doesn't exist" and "not yours"
        return chat


@extend_schema(tags=["chat"])
class SessionCreateView(_ChatAPIView):
    throttle_classes = [SessionCreateThrottle]

    @extend_schema(request=CreateSessionSerializer, responses={201: SessionCreatedSerializer})
    def post(self, request: Request) -> Response:
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        chat = ChatSession.objects.create(language=serializer.validated_data["language"], user=user)
        remember_session(request, chat)
        body = {
            "session_id": chat.id,
            "language": chat.language,
            "created_at": chat.created_at,
            "disclaimer": DISCLAIMER,
        }
        return Response(body, status=status.HTTP_201_CREATED)


@extend_schema(tags=["chat"])
class SessionDetailView(_ChatAPIView):
    @extend_schema(responses={200: SessionDetailSerializer})
    def get(self, request: Request, session_id: UUID) -> Response:
        return Response(render_session(self.owned_session(request, session_id)))


@extend_schema(tags=["chat"])
class MessageCreateView(_ChatAPIView):
    # Order matters: cheap per-IP/per-session limits first, the DB-backed global cap last.
    throttle_classes = [
        ChatIPBurstThrottle,
        ChatIPDailyThrottle,
        ChatSessionThrottle,
        GlobalDailyCapThrottle,
    ]

    @extend_schema(
        request=SendMessageSerializer,
        responses={200: TurnResponseSerializer},
        examples=[
            OpenApiExample(
                "Task example",
                request_only=True,
                value={
                    "content": "I have chest pain and I'm not sure whether I should see a "
                    "cardiologist, go to the ER, or seek a second opinion."
                },
            )
        ],
    )
    def post(self, request: Request, session_id: UUID) -> Response:
        chat = self.owned_session(request, session_id)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        used = chat.messages.filter(role=Message.Role.USER).count()
        if used >= settings.CHAT_MAX_MESSAGES_PER_SESSION:
            raise SessionLimitReached()
        result = handle_message(chat, serializer.validated_data["content"])
        return Response(render_turn(result.message))
