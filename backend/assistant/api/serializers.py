"""Request validation + response rendering for the chat API.

Rendering rule: stored payloads hold only IDs. `render_turn()` expands them into
provider / hospital cards from the DB at response time, so what the patient sees
is always current, verified directory data.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from rest_framework import serializers

from assistant.agent.texts import DISCLAIMER
from assistant.models import ChatSession, Message
from providers.serializers import (
    DoctorCardSerializer,
    HospitalCardSerializer,
    doctor_cards,
    hospital_cards,
)

MAX_MESSAGE_CHARS = 1000


# --- Requests ---------------------------------------------------------------
class CreateSessionSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=ChatSession.Language.choices, default="en")


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=MAX_MESSAGE_CHARS, trim_whitespace=True, allow_blank=False
    )


# --- Response documentation (drf-spectacular) --------------------------------
class ClarifyingQuestionSerializer(serializers.Serializer):
    question = serializers.CharField()
    quick_replies = serializers.ListField(child=serializers.CharField())


class EmergencyNumberSerializer(serializers.Serializer):
    number = serializers.CharField()
    label_en = serializers.CharField()
    label_ar = serializers.CharField()


class EmergencySerializer(serializers.Serializer):
    numbers = EmergencyNumberSerializer(many=True)
    hospitals = HospitalCardSerializer(many=True)


class ToolCallTraceSerializer(serializers.Serializer):
    name = serializers.CharField()
    args = serializers.DictField()
    result_ids = serializers.ListField(child=serializers.IntegerField())
    latency_ms = serializers.IntegerField()
    success = serializers.BooleanField()
    error = serializers.CharField()


class TraceSerializer(serializers.Serializer):
    state = serializers.DictField()
    stage = serializers.CharField()
    tool_calls = ToolCallTraceSerializer(many=True)
    iterations = serializers.IntegerField()
    grounding_violations = serializers.ListField(child=serializers.DictField())
    rules = serializers.DictField()
    llm_provider = serializers.CharField()
    llm_model = serializers.CharField()
    outcome = serializers.CharField()
    fallback_reason = serializers.CharField()
    latency_ms = serializers.IntegerField()
    clarification_rounds = serializers.IntegerField()


class TurnResponseSerializer(serializers.Serializer):
    message_id = serializers.IntegerField()
    reply_text = serializers.CharField()
    urgency = serializers.ChoiceField(choices=["EMERGENCY", "URGENT", "ROUTINE", "UNKNOWN"])
    urgency_source = serializers.ChoiceField(choices=["rules", "llm", "fallback"])
    next_step = serializers.CharField()
    clarifying_questions = ClarifyingQuestionSerializer(many=True)
    providers = DoctorCardSerializer(many=True)
    emergency = EmergencySerializer(allow_null=True)
    reasoning_summary = serializers.CharField()
    trace = TraceSerializer()
    disclaimer = serializers.DictField(child=serializers.CharField())


class SessionCreatedSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    language = serializers.CharField()
    created_at = serializers.DateTimeField()
    disclaimer = serializers.DictField(child=serializers.CharField())


class HistoryMessageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    role = serializers.CharField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()
    turn = TurnResponseSerializer(allow_null=True)


class SessionDetailSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    language = serializers.CharField()
    state = serializers.DictField()
    stage = serializers.CharField()
    urgency_level = serializers.CharField()
    clarification_rounds = serializers.IntegerField()
    messages_remaining = serializers.IntegerField()
    messages = HistoryMessageSerializer(many=True)


# --- Rendering ----------------------------------------------------------------
def render_turn(message: Message) -> dict[str, Any]:
    """Expand a stored assistant payload (IDs) into the API response (DB cards)."""
    payload = dict(message.structured_payload or {})
    emergency = payload.get("emergency")
    return {
        "message_id": message.pk,
        "reply_text": payload.get("reply_text", message.content),
        "urgency": payload.get("urgency", "UNKNOWN"),
        "urgency_source": payload.get("urgency_source", "fallback"),
        "next_step": payload.get("next_step", "NEED_MORE_INFO"),
        "clarifying_questions": payload.get("clarifying_questions", []),
        "providers": doctor_cards(payload.get("provider_ids", [])),
        "emergency": (
            {
                "numbers": emergency["numbers"],
                "hospitals": hospital_cards(emergency["hospital_ids"]),
            }
            if emergency
            else None
        ),
        "reasoning_summary": payload.get("reasoning_summary", ""),
        "trace": payload.get("trace", {}),
        "disclaimer": DISCLAIMER,
    }


def render_session(chat: ChatSession) -> dict[str, Any]:
    messages = list(chat.messages.exclude(role=Message.Role.TOOL).order_by("created_at", "id"))
    user_count = sum(1 for m in messages if m.role == Message.Role.USER)
    return {
        "session_id": chat.id,
        "language": chat.language,
        "state": chat.state,
        "stage": chat.current_stage,
        "urgency_level": chat.urgency_level,
        "clarification_rounds": chat.clarification_rounds,
        "messages_remaining": max(0, settings.CHAT_MAX_MESSAGES_PER_SESSION - user_count),
        "messages": [
            {
                "id": m.pk,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at,
                "turn": render_turn(m) if m.role == Message.Role.ASSISTANT else None,
            }
            for m in messages
        ],
    }
