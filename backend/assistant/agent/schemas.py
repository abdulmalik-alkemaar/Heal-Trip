"""Pydantic schemas for the agent's state and its final answer.

`AgentResponse` is the input schema of the `submit_response` tool. Making the final
answer a tool call (rather than free text) means the model's output is constrained
by a JSON Schema and then validated here. Anything that fails validation triggers
one repair attempt, then a safe fallback.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from assistant.enums import NextStep
from providers.choices import City

MAX_QUESTIONS_PER_TURN = 3
MAX_RECOMMENDATIONS = 5

PatientGoal = Literal["SPECIALIST", "ER", "SECOND_OPINION", "UNSURE"]
AgeRange = Literal["UNDER_18", "18_39", "40_64", "65_PLUS"]
ShortText = Field(default=None, max_length=200)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class PatientState(_Strict):
    """Slots the agent fills during the conversation (persisted in ChatSession.state).

    No identity fields (name, national ID, phone) on purpose: we never collect them.
    """

    chief_complaint: str | None = ShortText
    symptoms: list[str] = Field(default_factory=list, max_length=15)
    onset: str | None = ShortText
    duration: str | None = ShortText
    severity_1_10: int | None = Field(default=None, ge=1, le=10)
    radiating_pain: bool | None = None
    shortness_of_breath: bool | None = None
    sweating_or_nausea: bool | None = None
    age_range: AgeRange | None = None
    known_conditions: list[str] = Field(default_factory=list, max_length=10)
    has_existing_diagnosis: bool | None = None
    patient_goal: PatientGoal | None = None
    city: City | None = None
    preferred_language: Literal["ar", "en"] | None = None

    def merged(self, updates: PatientStateUpdate | None) -> PatientState:
        """Apply partial updates. Lists are unioned (order kept); scalars are replaced."""
        if updates is None:
            return self
        data = self.model_dump()
        for key, value in updates.model_dump(exclude_unset=True).items():
            if value is None:
                continue
            if isinstance(value, list):
                data[key] = list(dict.fromkeys([*data.get(key, []), *value]))[:15]
            else:
                data[key] = value
        return PatientState.model_validate(data)


class PatientStateUpdate(PatientState):
    """Same fields as PatientState; only the ones the model sets are applied."""


class ClarifyingQuestion(_Strict):
    question: str = Field(min_length=3, max_length=300)
    # Chips the user can tap. They must be self-contained answers
    # ("Yes, the pain spreads to my arm", not just "Yes") so the red-flag rules
    # can read them without the question's context.
    quick_replies: list[str] = Field(default_factory=list, max_length=5)


class AgentResponse(_Strict):
    """The final answer for one turn (input schema of the `submit_response` tool)."""

    reply_text: str = Field(
        min_length=1,
        max_length=2500,
        description="Message to the patient in the session language. Never include provider "
        "names, phone numbers, fees or addresses; provider cards are shown separately.",
    )
    urgency: Literal["EMERGENCY", "URGENT", "ROUTINE"]
    next_step: NextStep
    clarifying_questions: list[ClarifyingQuestion] = Field(
        default_factory=list, max_length=MAX_QUESTIONS_PER_TURN
    )
    recommended_provider_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_RECOMMENDATIONS,
        description="provider_id values returned by search_providers in this conversation.",
    )
    state_updates: PatientStateUpdate = Field(default_factory=PatientStateUpdate)
    reasoning_summary: str = Field(
        default="",
        max_length=400,
        description="One or two sentences on why this next step (shown in the trace panel).",
    )

    @model_validator(mode="after")
    def _consistent(self) -> AgentResponse:
        if self.next_step == NextStep.NEED_MORE_INFO and not self.clarifying_questions:
            raise ValueError("next_step NEED_MORE_INFO requires at least one clarifying question")
        if self.urgency == "EMERGENCY" and self.next_step not in (
            NextStep.CALL_EMERGENCY,
            NextStep.GO_TO_ER,
        ):
            raise ValueError("urgency EMERGENCY requires next_step CALL_EMERGENCY or GO_TO_ER")
        self.recommended_provider_ids = list(dict.fromkeys(self.recommended_provider_ids))
        return self
