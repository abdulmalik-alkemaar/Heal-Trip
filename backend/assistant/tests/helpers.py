"""Test helpers for scripting the MockLLMClient."""

from __future__ import annotations

import json
from typing import Any

from assistant.llm.client import LLMResponse, ToolCall, text_only, tool_use  # noqa: F401


def submit(**overrides: Any) -> LLMResponse:
    """A valid submit_response call; override any field."""
    payload: dict[str, Any] = {
        "reply_text": "Here is my guidance.",
        "urgency": "ROUTINE",
        "next_step": "SEE_SPECIALIST",
        "clarifying_questions": [],
        "recommended_provider_ids": [],
        "state_updates": {},
        "reasoning_summary": "test",
    }
    payload.update(overrides)
    return tool_use("submit_response", payload)


def last_tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """tool_result blocks of the most recent user message (what the model just received)."""
    content = messages[-1]["content"]
    assert isinstance(content, list), content
    return [b for b in content if b["type"] == "tool_result"]


def search_ids(messages: list[dict[str, Any]]) -> list[int]:
    """provider_ids from the most recent search_providers result in the conversation."""
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(message["content"], list):
            for block in message["content"]:
                data = json.loads(block["content"]) if block["content"].startswith("{") else {}
                if "results" in data:
                    return [r["provider_id"] for r in data["results"] + data["nearby_alternatives"]]
    return []


def multi_tool(*calls: tuple[str, dict[str, Any]]) -> LLMResponse:
    """One assistant turn with several tool calls."""
    responses = [tool_use(name, args, call_id=f"toolu_{i}") for i, (name, args) in enumerate(calls)]
    return LLMResponse(
        stop_reason="tool_use",
        tool_calls=[c for r in responses for c in r.tool_calls],
        raw_content=[b for r in responses for b in r.raw_content],
    )
