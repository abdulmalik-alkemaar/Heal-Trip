"""Conversation stages and the rules the BACKEND enforces on the model's answer.

INTAKE -> CLARIFY -> ASSESS -> SEARCH -> RECOMMEND, plus EMERGENCY from anywhere.

The model proposes; this module decides:
- `answer_problems()`: repairable issues sent back to the model once
  (asking questions after the round limit, replying in the wrong language).
- `enforce()`: final deterministic corrections applied no matter what the model
  said (urgency floor from the rules, no NEED_MORE_INFO after the round limit,
  EMERGENCY => CALL_EMERGENCY/GO_TO_ER).
- `next_stage()`: stage transition. RECOMMEND is reachable only with grounded
  provider IDs, and those exist only after a successful search_providers call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from assistant.enums import NextStep, Stage, Urgency, max_urgency

from .prompts import CORRECTION_NO_ROUNDS_LEFT, CORRECTION_WRONG_LANGUAGE
from .schemas import AgentResponse

_ARABIC_CHARS = re.compile(r"[؀-ۿ]")
_LATIN_CHARS = re.compile(r"[A-Za-z]")


def _looks_like(language: str, text: str) -> bool:
    arabic, latin = len(_ARABIC_CHARS.findall(text)), len(_LATIN_CHARS.findall(text))
    return arabic >= latin if language == "ar" else latin >= arabic


def answer_problems(
    answer: AgentResponse, *, language: str, rounds_used: int, max_rounds: int
) -> str | None:
    """Return a correction message for the model, or None if the answer is acceptable."""
    if answer.next_step == NextStep.NEED_MORE_INFO and rounds_used >= max_rounds:
        return CORRECTION_NO_ROUNDS_LEFT
    if not _looks_like(language, answer.reply_text):
        return CORRECTION_WRONG_LANGUAGE.format(
            language="Arabic" if language == "ar" else "English"
        )
    return None


@dataclass
class Decision:
    urgency: Urgency
    urgency_source: str  # "rules" | "llm"
    next_step: NextStep
    ask_questions: bool


def enforce(
    answer: AgentResponse, *, rules_urgency: Urgency, rounds_used: int, max_rounds: int
) -> Decision:
    """Deterministic post-processing of the model's answer (cannot be argued with)."""
    llm_urgency = Urgency(answer.urgency)
    urgency = max_urgency(rules_urgency, llm_urgency)
    # Attribute the level to the rules when they set (or tie) the final level: the rules are
    # the reason it cannot be lower, whatever the model said.
    source = "rules" if urgency == rules_urgency and rules_urgency != Urgency.UNKNOWN else "llm"

    next_step = NextStep(answer.next_step)
    if next_step == NextStep.NEED_MORE_INFO and rounds_used >= max_rounds:
        # Out of rounds: best guidance instead of another question.
        next_step = NextStep.SEE_SPECIALIST
    if urgency == Urgency.EMERGENCY and next_step not in (
        NextStep.CALL_EMERGENCY,
        NextStep.GO_TO_ER,
    ):
        next_step = NextStep.CALL_EMERGENCY
    return Decision(
        urgency=urgency,
        urgency_source=source,
        next_step=next_step,
        ask_questions=next_step == NextStep.NEED_MORE_INFO,
    )


def next_stage(
    decision: Decision, *, has_grounded_providers: bool, searched_this_turn: bool
) -> Stage:
    if decision.urgency == Urgency.EMERGENCY or decision.next_step == NextStep.CALL_EMERGENCY:
        return Stage.EMERGENCY
    if decision.next_step == NextStep.NEED_MORE_INFO:
        return Stage.CLARIFY
    if has_grounded_providers:
        return Stage.RECOMMEND
    if searched_this_turn:
        return Stage.SEARCH  # searched, but nothing verified to recommend
    return Stage.ASSESS
