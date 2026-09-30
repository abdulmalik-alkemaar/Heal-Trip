"""Conversation state + audit trail for the patient decision assistant.

- ChatSession: one conversation; holds the extracted PatientState slots and stage.
- Message: user/assistant turns (tool traffic lives in ToolCallLog, not here).
- ToolCallLog: every tool execution. Its `result_ids` are the ground truth the
  grounding validator uses to decide which provider IDs the model may recommend.
- AgentRunLog: one row per assistant turn (iterations, latency, urgency provenance,
  grounding violations). Kept separate from ToolCallLog because it is per *turn*,
  and a turn can have zero or many tool calls (see docs/DECISIONS.md ADR-004).
"""

import uuid

from django.conf import settings
from django.db import models

from .enums import NextStep, RunOutcome, Stage, Urgency, UrgencySource


class ChatSession(models.Model):
    class Language(models.TextChoices):
        ARABIC = "ar", "Arabic"
        ENGLISH = "en", "English"

    # UUID so session ids are not enumerable. Ownership is still enforced separately
    # (the browser's Django session must list this id) - see assistant/api/permissions.py.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)
    # Extracted PatientState slots (validated by assistant.agent.schemas.PatientState).
    state = models.JSONField(default=dict, blank=True)
    urgency_level = models.CharField(
        max_length=10, choices=Urgency.choices, default=Urgency.UNKNOWN
    )
    current_stage = models.CharField(max_length=10, choices=Stage.choices, default=Stage.INTAKE)
    clarification_rounds = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        # Retention purge filters on updated_at.
        indexes = [models.Index(fields=["updated_at"], name="chatsession_updated_idx")]

    def __str__(self) -> str:
        return f"{self.id} ({self.language}, {self.current_stage})"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # For assistant turns: the full API payload (urgency, next_step, provider ids, ...).
    structured_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["session", "created_at"], name="message_session_idx")]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:40]}"


class AgentRunLog(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="runs")
    llm_provider = models.CharField(max_length=20)
    llm_model = models.CharField(max_length=60, blank=True, default="")
    iterations = models.PositiveSmallIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    rules_urgency = models.CharField(
        max_length=10, choices=Urgency.choices, default=Urgency.UNKNOWN
    )
    llm_urgency = models.CharField(max_length=10, choices=Urgency.choices, blank=True, default="")
    final_urgency = models.CharField(max_length=10, choices=Urgency.choices)
    urgency_source = models.CharField(max_length=10, choices=UrgencySource.choices)
    next_step = models.CharField(max_length=20, choices=NextStep.choices)
    stage = models.CharField(max_length=10, choices=Stage.choices)
    outcome = models.CharField(max_length=30, choices=RunOutcome.choices)
    matched_red_flags = models.JSONField(default=list, blank=True)
    grounding_violations = models.JSONField(default=list, blank=True)
    grounding_violations_count = models.PositiveSmallIntegerField(default=0)
    # Short machine-readable reason when outcome == fallback (e.g. "llm_unavailable").
    fallback_reason = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"run {self.pk} ({self.outcome}, {self.final_urgency})"


class ToolCallLog(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="tool_calls")
    run = models.ForeignKey(
        AgentRunLog, on_delete=models.CASCADE, null=True, blank=True, related_name="tool_calls"
    )
    tool_name = models.CharField(max_length=60)
    # Arguments are validated enums/ints/bools (no free text), so they carry no PII.
    arguments = models.JSONField(default=dict)
    # Doctor ids returned to the model - the whitelist for grounding validation.
    result_ids = models.JSONField(default=list)
    # Hospital ids returned (emergency info / provider details) - for name grounding.
    result_hospital_ids = models.JSONField(default=list)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True, default="")
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["session", "tool_name"], name="toolcall_session_tool_idx")]

    def __str__(self) -> str:
        return f"{self.tool_name} ({'ok' if self.success else 'error'})"
