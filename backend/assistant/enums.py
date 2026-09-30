"""Enumerations shared by the models, the agent and the API.

`Urgency` is *ordered*: `max_urgency()` is how we enforce the rule
"final urgency = max(rules, llm)" - the LLM may escalate, never downgrade.
"""

from django.db import models


class Urgency(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    ROUTINE = "ROUTINE", "Routine"
    URGENT = "URGENT", "Urgent"
    EMERGENCY = "EMERGENCY", "Emergency"


# Explicit rank table (rather than relying on declaration order) so the ordering is
# obvious when reading the code and cannot change by accidentally reordering members.
URGENCY_RANK: dict[str, int] = {
    Urgency.UNKNOWN: 0,
    Urgency.ROUTINE: 1,
    Urgency.URGENT: 2,
    Urgency.EMERGENCY: 3,
}


def max_urgency(*levels: str | None) -> Urgency:
    """Return the most severe of the given urgency levels (None/unknown values are ignored)."""
    valid = [Urgency(level) for level in levels if level in URGENCY_RANK]
    if not valid:
        return Urgency.UNKNOWN
    return max(valid, key=lambda level: URGENCY_RANK[level])


class Stage(models.TextChoices):
    INTAKE = "INTAKE", "Intake"
    CLARIFY = "CLARIFY", "Clarify"
    ASSESS = "ASSESS", "Assess"
    SEARCH = "SEARCH", "Search"
    RECOMMEND = "RECOMMEND", "Recommend"
    EMERGENCY = "EMERGENCY", "Emergency"


class NextStep(models.TextChoices):
    CALL_EMERGENCY = "CALL_EMERGENCY", "Call emergency services"
    GO_TO_ER = "GO_TO_ER", "Go to the ER"
    SEE_SPECIALIST = "SEE_SPECIALIST", "See a specialist"
    SECOND_OPINION = "SECOND_OPINION", "Get a second opinion"
    NEED_MORE_INFO = "NEED_MORE_INFO", "Need more information"


class UrgencySource(models.TextChoices):
    RULES = "rules", "Deterministic rules"
    LLM = "llm", "LLM"
    FALLBACK = "fallback", "Safe fallback"


class RunOutcome(models.TextChoices):
    OK = "ok", "Agent answered"
    EMERGENCY_SHORT_CIRCUIT = "emergency_short_circuit", "Rules short-circuit (no LLM)"
    FALLBACK = "fallback", "Safe fallback response"
