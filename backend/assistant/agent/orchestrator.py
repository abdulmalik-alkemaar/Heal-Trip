"""Orchestrator: one patient message in, one validated & persisted answer out.

    1. sanitize + persist the user message (control chars stripped, PII redacted)
    2. Red-Flag Engine on all user text + state  -> EMERGENCY? answer now, no LLM
    3. Agent loop (LLM + tools + grounding)      -> LLM failure? safe fallback
    4. merge state_updates, re-run the rules on the new structured state
    5. deterministic enforcement: urgency = max(rules, llm), round limit, stage
    6. persist assistant message, session, AgentRunLog; return the payload

"The LLM decides what to do. Deterministic code decides what is safe.
 The database decides what is true."
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction

from assistant.enums import NextStep, RunOutcome, Stage, Urgency, UrgencySource
from assistant.llm.client import LLMClient, LLMUnavailableError, get_llm_client
from assistant.models import AgentRunLog, ChatSession, Message, ToolCallLog
from assistant.safety import red_flags
from assistant.safety.pii import redact
from assistant.tools import registry
from assistant.tools.provider_tools import EMERGENCY_NUMBERS

from . import stages, texts
from .loop import AgentLoop, LoopResult, TurnContext
from .prompts import session_context_block, wrap_patient_text
from .schemas import AgentResponse, PatientState

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 12  # recent turns sent to the model (older context lives in `state`)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")


@dataclass
class TurnResult:
    message: Message  # the persisted assistant message
    payload: dict[str, Any]  # structured payload (IDs only; the API renders cards from the DB)


def sanitize(text: str) -> str:
    """Strip control / bidi-override characters (prompt-smuggling vectors) and redact PII."""
    return redact(_CONTROL_CHARS.sub("", text)).strip()


def load_state(session: ChatSession) -> PatientState:
    try:
        return PatientState.model_validate(session.state or {})
    except ValueError:
        logger.warning("invalid_stored_state", extra={"session_id": str(session.id)})
        return PatientState()


def handle_message(
    session: ChatSession, raw_text: str, client: LLMClient | None = None
) -> TurnResult:
    started = time.monotonic()
    language = session.language
    text = sanitize(raw_text)
    Message.objects.create(session=session, role=Message.Role.USER, content=text)
    user_texts = list(
        session.messages.filter(role=Message.Role.USER).values_list("content", flat=True)
    )
    state = load_state(session)
    run = AgentRunLog.objects.create(
        session=session,
        llm_provider=settings.LLM_PROVIDER,
        final_urgency=Urgency.UNKNOWN,
        urgency_source=UrgencySource.FALLBACK,
        next_step=NextStep.NEED_MORE_INFO,
        stage=session.current_stage,
        outcome=RunOutcome.FALLBACK,
    )

    # 2. Deterministic safety first: no LLM involved, works when the LLM is down.
    rules = red_flags.evaluate(user_texts, state.model_dump())
    if rules.is_emergency:
        run.llm_provider = "none"  # the LLM is never called on this path
        return _finish_emergency(
            session, run, rules, state, started, outcome=RunOutcome.EMERGENCY_SHORT_CIRCUIT
        )

    # 3. Agent loop.
    try:
        client = client or get_llm_client()
        run.llm_provider, run.llm_model = client.provider, client.model
        loop_result = AgentLoop(client, settings.AGENT_MAX_ITERATIONS).run(
            TurnContext(
                session=session,
                run=run,
                messages=build_messages(session, text, state, rules.level),
                language=language,
                rules_urgency=rules.level,
                rounds_used=session.clarification_rounds,
                max_rounds=settings.AGENT_MAX_CLARIFICATION_ROUNDS,
            )
        )
    except LLMUnavailableError as exc:
        logger.warning(
            "llm_unavailable", extra={"session_id": str(session.id), "reason": exc.reason}
        )
        loop_result = LoopResult(fallback_reason=exc.reason)

    if loop_result.answer is None:
        return _finish_fallback(session, run, rules, state, loop_result, started)

    # 4. New facts may reveal an emergency the text alone did not (e.g. a "yes" slot).
    answer = loop_result.answer
    new_state = state.merged(answer.state_updates)
    rules = red_flags.evaluate(user_texts, new_state.model_dump())
    if rules.is_emergency:
        return _finish_emergency(
            session, run, rules, new_state, started, outcome=RunOutcome.OK, loop=loop_result
        )

    # 5. Deterministic enforcement.
    return _finish_agent(session, run, rules, new_state, answer, loop_result, started)


def build_messages(
    session: ChatSession, text: str, state: PatientState, rules_urgency: Urgency
) -> list[dict]:
    """Recent history (user text fenced as data) + the new turn with session context."""
    prior = list(session.messages.order_by("-created_at", "-id")[1 : HISTORY_MESSAGES + 1])[::-1]
    messages: list[dict[str, Any]] = []
    for message in prior:
        if message.role == Message.Role.USER:
            role, content = "user", wrap_patient_text(message.content)
        else:
            summary = {
                k: (message.structured_payload or {}).get(k) for k in ("next_step", "provider_ids")
            }
            role, content = "assistant", f"{message.content}\n[{json.dumps(summary)}]"
        if messages and messages[-1]["role"] == role:  # keep strict user/assistant alternation
            messages[-1]["content"] += "\n\n" + content
        else:
            messages.append({"role": role, "content": content})
    if messages and messages[0]["role"] == "assistant":
        messages.pop(0)
    context = session_context_block(
        language=session.language,
        state=state.model_dump(mode="json"),
        stage=session.current_stage,
        rounds_used=session.clarification_rounds,
        max_rounds=settings.AGENT_MAX_CLARIFICATION_ROUNDS,
        rules_urgency=str(rules_urgency),
    )
    new_turn = f"{context}\n{wrap_patient_text(text)}"
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n" + new_turn
    else:
        messages.append({"role": "user", "content": new_turn})
    return messages


# ---------------------------------------------------------------------------
# Finishers: each builds the payload and persists everything in one transaction.
# ---------------------------------------------------------------------------
def _emergency_block(session: ChatSession, run: AgentRunLog, state: PatientState) -> dict[str, Any]:
    """Emergency numbers + ER hospitals, fetched by CODE (not the LLM) via the same tool."""
    execution = registry.execute(
        "get_emergency_info", {"city": state.city}, session=session, run=run
    )
    output = execution.output if execution.success else {}
    return {
        "numbers": output.get("numbers", EMERGENCY_NUMBERS),
        "hospital_ids": [h["hospital_id"] for h in output.get("hospitals", [])],
    }


def _finish_emergency(
    session, run, rules, state, started, *, outcome, loop: LoopResult | None = None
):
    lang = session.language
    payload = {
        "reply_text": texts.EMERGENCY_REPLY[lang],
        "urgency": Urgency.EMERGENCY,
        "urgency_source": UrgencySource.RULES,
        "next_step": NextStep.CALL_EMERGENCY,
        "clarifying_questions": [],
        "provider_ids": [],
        "emergency": _emergency_block(session, run, state),
        "reasoning_summary": "Deterministic red-flag rules matched: "
        + ", ".join(rules.matched_flags),
    }
    return _persist(
        session, run, state, payload, Stage.EMERGENCY, rules, loop, started, outcome=outcome
    )


def _finish_fallback(session, run, rules, state, loop: LoopResult, started):
    lang = session.language
    urgency = rules.level  # without the LLM, only the rules have an opinion (may be UNKNOWN)
    payload = {
        "reply_text": texts.FALLBACK_REPLY[lang],
        "urgency": urgency,
        "urgency_source": UrgencySource.FALLBACK,
        "next_step": NextStep.SEE_SPECIALIST
        if urgency == Urgency.URGENT
        else NextStep.NEED_MORE_INFO,
        "clarifying_questions": [],
        "provider_ids": [],
        # Emergency numbers are always shown on a fallback: the one thing that must work.
        "emergency": _emergency_block(session, run, state),
        "reasoning_summary": f"Safe fallback ({loop.fallback_reason}).",
    }
    run.fallback_reason = loop.fallback_reason[:60]
    return _persist(
        session,
        run,
        state,
        payload,
        session.current_stage,
        rules,
        loop,
        started,
        outcome=RunOutcome.FALLBACK,
    )


def _finish_agent(session, run, rules, state, answer: AgentResponse, loop: LoopResult, started):
    lang = session.language
    max_rounds = settings.AGENT_MAX_CLARIFICATION_ROUNDS
    decision = stages.enforce(
        answer,
        rules_urgency=rules.level,
        rounds_used=session.clarification_rounds,
        max_rounds=max_rounds,
    )
    checked = loop.grounding
    reply_text = checked.reply_text
    provider_ids = checked.kept_provider_ids
    if checked.all_recommendations_dropped:
        reply_text = texts.NO_VERIFIED_MATCH[lang]
    if answer.next_step == NextStep.NEED_MORE_INFO and not decision.ask_questions:
        reply_text = f"{reply_text}\n\n{texts.BEST_GUIDANCE_NOTE[lang]}"  # round limit reached
    if decision.ask_questions:
        session.clarification_rounds += 1

    needs_er = decision.urgency == Urgency.EMERGENCY or decision.next_step in (
        NextStep.CALL_EMERGENCY,
        NextStep.GO_TO_ER,
    )
    payload = {
        "reply_text": reply_text,
        "urgency": decision.urgency,
        "urgency_source": decision.urgency_source,
        "next_step": decision.next_step,
        "clarifying_questions": [q.model_dump() for q in answer.clarifying_questions]
        if decision.ask_questions
        else [],
        "provider_ids": provider_ids,
        "emergency": _emergency_block(session, run, state) if needs_er else None,
        "reasoning_summary": answer.reasoning_summary,
        "llm_urgency": answer.urgency,
    }
    searched = any(e.name == registry.SEARCH_TOOL and e.success for e in loop.executions)
    stage = stages.next_stage(
        decision, has_grounded_providers=bool(provider_ids), searched_this_turn=searched
    )
    return _persist(
        session, run, state, payload, stage, rules, loop, started, outcome=RunOutcome.OK
    )


@transaction.atomic
def _persist(session, run, state, payload, stage, rules, loop, started, *, outcome) -> TurnResult:
    violations = loop.violations if loop else []
    tool_calls = [
        {
            "name": log.tool_name,
            "args": log.arguments,
            "result_ids": log.result_ids,
            "latency_ms": log.latency_ms,
            "success": log.success,
            "error": log.error,
        }
        for log in ToolCallLog.objects.filter(run=run).order_by("id")
    ]
    latency_ms = int((time.monotonic() - started) * 1000)
    payload["trace"] = {
        "state": state.model_dump(mode="json", exclude_defaults=True),
        "stage": stage,
        "tool_calls": tool_calls,
        "iterations": loop.iterations if loop else 0,
        "grounding_violations": violations,
        "rules": rules.as_dict(),
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "outcome": outcome,
        "fallback_reason": run.fallback_reason,
        "latency_ms": latency_ms,
        "clarification_rounds": session.clarification_rounds,
    }
    payload = json.loads(json.dumps(payload, default=str))  # enums -> plain strings

    session.state = state.model_dump(mode="json")
    session.urgency_level = payload["urgency"]
    session.current_stage = stage
    session.save()
    message = Message.objects.create(
        session=session,
        role=Message.Role.ASSISTANT,
        content=payload["reply_text"],
        structured_payload=payload,
    )
    run.iterations = payload["trace"]["iterations"]
    run.latency_ms = latency_ms
    run.rules_urgency = rules.level
    run.llm_urgency = payload.get("llm_urgency", "")
    run.final_urgency = payload["urgency"]
    run.urgency_source = payload["urgency_source"]
    run.next_step = payload["next_step"]
    run.stage = stage
    run.outcome = outcome
    run.matched_red_flags = list(rules.matched_flags)
    run.grounding_violations = violations
    run.grounding_violations_count = len(violations)
    run.save()
    logger.info(
        "agent_turn",
        extra={
            "session_id": str(session.id),
            "outcome": outcome,
            "urgency": payload["urgency"],
            "urgency_source": payload["urgency_source"],
            "next_step": payload["next_step"],
            "iterations": run.iterations,
            "grounding_violations": len(violations),
            "latency_ms": latency_ms,
        },
    )
    return TurnResult(message=message, payload=payload)
