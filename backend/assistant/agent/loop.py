"""The agent loop: LLM <-> tools until the model submits a valid, grounded answer.

One call to `AgentLoop.run()` handles ONE patient message (the orchestrator does
the rules pre-check, persistence and the final safety overrides around it).

    for each iteration (hard cap AGENT_MAX_ITERATIONS):
        call the LLM with the tools + submit_response
        tool calls        -> validate + execute via the registry, feed results back
        submit_response   -> schema-validate -> policy check -> grounding check
                             (each failure gets ONE corrective retry, then fallback)
    cap reached           -> fallback

Why a hand-written loop (not LangChain / the SDK tool runner)? Every decision
point here is a safety control we need to see, test and log, and the loop fits
on one screen (docs/DECISIONS.md ADR-008).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from assistant.enums import Urgency
from assistant.llm.client import LLMClient
from assistant.models import AgentRunLog, ChatSession
from assistant.tools import registry
from assistant.tools.registry import ToolExecution, inline_refs

from . import grounding, stages
from .prompts import (
    CORRECTION_ALL_IDS_INVALID,
    CORRECTION_NO_FINAL_ANSWER,
    CORRECTION_SUBMIT_NOT_ALONE,
    SUBMIT_TOOL,
    SYSTEM_PROMPT,
)
from .schemas import AgentResponse

SUBMIT_TOOL_DEFINITION = {
    "name": SUBMIT_TOOL,
    "description": "Submit your final answer for this turn. Call exactly once, alone, last.",
    "input_schema": inline_refs(AgentResponse.model_json_schema()),
}


@dataclass
class TurnContext:
    session: ChatSession
    run: AgentRunLog
    messages: list[dict[str, Any]]  # history + the new wrapped user turn
    language: str
    rules_urgency: Urgency
    rounds_used: int
    max_rounds: int


@dataclass
class LoopResult:
    answer: AgentResponse | None = None
    grounding: grounding.GroundingResult | None = None
    iterations: int = 0
    executions: list[ToolExecution] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    fallback_reason: str = ""


def _tool_result(call_id: str, content: dict[str, Any] | str, is_error: bool = False) -> dict:
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return {"type": "tool_result", "tool_use_id": call_id, "content": text, "is_error": is_error}


class AgentLoop:
    def __init__(self, client: LLMClient, max_iterations: int) -> None:
        self.client = client
        self.max_iterations = max_iterations
        self.tools = [*registry.tool_definitions(), SUBMIT_TOOL_DEFINITION]

    def run(self, ctx: TurnContext) -> LoopResult:
        result = LoopResult()
        messages = list(ctx.messages)
        corrections_left = {"format": 1, "policy": 1, "grounding": 1}

        def correct(kind: str, call_id: str | None, message: str) -> bool:
            """Send one corrective message per failure kind. False = budget spent."""
            if corrections_left[kind] <= 0:
                return False
            corrections_left[kind] -= 1
            content = [_tool_result(call_id, message, is_error=True)] if call_id else message
            messages.append({"role": "user", "content": content})
            return True

        for iteration in range(1, self.max_iterations + 1):
            result.iterations = iteration
            response = self.client.create(system=SYSTEM_PROMPT, messages=messages, tools=self.tools)
            messages.append({"role": "assistant", "content": response.raw_content})
            if response.stop_reason == "refusal":
                result.fallback_reason = "llm_refusal"
                return result

            submit = next((c for c in response.tool_calls if c.name == SUBMIT_TOOL), None)
            others = [c for c in response.tool_calls if c.name != SUBMIT_TOOL]
            if not response.tool_calls:  # prose instead of submit_response
                if correct("format", None, CORRECTION_NO_FINAL_ANSWER):
                    continue
                result.fallback_reason = "no_final_answer"
                return result

            # Execute data tools (read-only, validated, logged). Errors go back to the model.
            tool_results = []
            for call in others:
                execution = registry.execute(
                    call.name, call.input, session=ctx.session, run=ctx.run
                )
                result.executions.append(execution)
                tool_results.append(_tool_result(call.id, execution.output, not execution.success))
            if submit is None:
                messages.append({"role": "user", "content": tool_results})
                continue
            if others:  # answered before seeing the tool results
                tool_results.append(_tool_result(submit.id, CORRECTION_SUBMIT_NOT_ALONE, True))
                messages.append({"role": "user", "content": tool_results})
                continue

            # Final answer: schema -> policy -> grounding.
            try:
                answer = AgentResponse.model_validate(submit.input)
            except ValidationError as exc:
                errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
                if correct("format", submit.id, "Invalid submit_response: " + "; ".join(errors)):
                    continue
                result.fallback_reason = "invalid_final_answer"
                return result

            problem = stages.answer_problems(
                answer,
                language=ctx.language,
                rounds_used=ctx.rounds_used,
                max_rounds=ctx.max_rounds,
            )
            if problem and correct("policy", submit.id, problem):
                continue  # if the budget is spent, stages.enforce() corrects it deterministically

            checked = grounding.validate(
                session=ctx.session,
                recommended_provider_ids=answer.recommended_provider_ids,
                reply_text=answer.reply_text,
                language=ctx.language,
            )
            result.violations += checked.violations
            if checked.all_recommendations_dropped and correct(
                "grounding", submit.id, CORRECTION_ALL_IDS_INVALID
            ):
                continue

            result.answer, result.grounding = answer, checked
            return result

        result.fallback_reason = "max_iterations"
        return result
