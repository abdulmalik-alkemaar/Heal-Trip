"""LLM client abstraction.

The agent loop depends only on the small `LLMClient` protocol below, so:
- tests and CI run against `MockLLMClient` (deterministic, no network, no key),
- the real `AnthropicClient` can be swapped for another provider without touching
  the loop, and
- every failure mode (timeout, 5xx, rate limit, refusal) is normalized into one
  `LLMUnavailableError` the orchestrator turns into a safe fallback.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic
from django.conf import settings
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailableError(Exception):
    """The LLM could not produce an answer (after retries). `reason` is log-safe."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class ToolCall:
    id: str
    name: str
    input: Any


@dataclass
class LLMResponse:
    stop_reason: str
    tool_calls: list[ToolCall]
    text: str = ""
    # Content exactly as it must be echoed back in the next request (append-only history).
    raw_content: list[Any] = field(default_factory=list)
    model: str = ""


class LLMClient(Protocol):
    provider: str
    model: str

    def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


# ---------------------------------------------------------------------------
# Anthropic (Claude) implementation
# ---------------------------------------------------------------------------
def _is_retryable(exc: BaseException) -> bool:
    """Retry only transient failures: timeouts, connection errors, 429 and 5xx."""
    if isinstance(exc, anthropic.APIConnectionError):  # includes APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def _replayable(content: Iterable[Any]) -> list[Any]:
    """Drop blocks the API must not receive back after a server-side model fallback.

    If a refusal fallback happened, blocks *before* the last `fallback` marker came
    from the declined attempt; thinking/tool_use blocks from it must not be echoed.
    """
    blocks = list(content)
    fallback_positions = [i for i, b in enumerate(blocks) if getattr(b, "type", "") == "fallback"]
    if not fallback_positions:
        return blocks
    boundary = fallback_positions[-1]
    dropped = {"thinking", "redacted_thinking", "tool_use"}
    before = [b for b in blocks[:boundary] if getattr(b, "type", "") not in dropped]
    return before + blocks[boundary + 1 :]


class AnthropicClient:
    provider = "anthropic"
    # Exponential backoff between retries (class attribute so tests can make it instant).
    retry_wait = wait_exponential(multiplier=0.5, max=8)

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise LLMUnavailableError("llm_not_configured")
        # SDK-level retries are disabled; tenacity owns the retry policy so it is
        # explicit, testable and limited to transient errors.
        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.model = settings.LLM_MODEL

    def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        try:
            for attempt in Retrying(
                retry=retry_if_exception(_is_retryable),
                stop=stop_after_attempt(settings.LLM_MAX_RETRIES + 1),
                wait=self.retry_wait,
                reraise=False,
            ):
                with attempt:
                    return self._create_once(system=system, messages=messages, tools=tools)
        except RetryError as exc:
            cause = exc.last_attempt.exception()
            logger.warning("llm_retries_exhausted", extra={"error": type(cause).__name__})
            raise LLMUnavailableError("llm_unavailable") from cause
        except anthropic.APIStatusError as exc:  # non-retryable 4xx (bad request, auth, ...)
            logger.error("llm_request_rejected", extra={"status": exc.status_code})
            raise LLMUnavailableError(f"llm_http_{exc.status_code}") from exc
        except anthropic.AnthropicError as exc:
            logger.error("llm_error", extra={"error": type(exc).__name__})
            raise LLMUnavailableError("llm_error") from exc
        raise LLMUnavailableError(
            "llm_unavailable"
        )  # pragma: no cover - loop always returns/raises

    def _create_once(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": settings.LLM_MAX_TOKENS,
            # The system prompt + tools are identical on every request: cache them.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
            "tools": tools,
            # Forced tool_choice is not supported on current models; the prompt asks the
            # model to finish via submit_response and the loop repairs if it does not.
            "tool_choice": {"type": "auto"},
            "output_config": {"effort": settings.LLM_EFFORT},
        }
        if settings.LLM_REFUSAL_FALLBACK:
            response = self._client.beta.messages.create(
                **kwargs, betas=[REFUSAL_FALLBACK_BETA], fallbacks="default"
            )
        else:
            response = self._client.messages.create(**kwargs)

        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input)
            for b in response.content
            if b.type == "tool_use"
        ]
        text = "".join(b.text for b in response.content if b.type == "text")
        return LLMResponse(
            stop_reason=response.stop_reason or "",
            tool_calls=tool_calls,
            text=text,
            raw_content=_replayable(response.content),
            model=response.model,
        )


# ---------------------------------------------------------------------------
# Mock implementation (tests, CI, offline demo)
# ---------------------------------------------------------------------------
Step = LLMResponse | Exception | Callable[[list[dict[str, Any]]], LLMResponse]


class MockLLMClient:
    """Deterministic client. Plays a script of steps, one per `create()` call.

    A step is an `LLMResponse`, an exception to raise (e.g. to simulate an outage),
    or a callable receiving the messages (for scripted behaviour that inspects
    tool results). When no script is given, the heuristic demo policy is used so
    `LLM_PROVIDER=mock` still produces a usable end-to-end demo.
    """

    provider = "mock"
    model = "mock-scripted"

    def __init__(self, script: Iterable[Step] | None = None) -> None:
        self._script = list(script) if script is not None else None
        self.calls: list[dict[str, Any]] = []

    def create(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        if self._script is None:
            from .mock_policy import demo_policy

            return demo_policy(messages)
        if not self._script:
            raise LLMUnavailableError("mock_script_exhausted")
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        if callable(step):
            return step(messages)
        return step


def tool_use(name: str, input: dict[str, Any], call_id: str | None = None) -> LLMResponse:
    """Helper to build a mock response containing one tool call."""
    call_id = call_id or f"toolu_{name}_{abs(hash(str(input))) % 10**8}"
    block = {"type": "tool_use", "id": call_id, "name": name, "input": input}
    return LLMResponse(
        stop_reason="tool_use",
        tool_calls=[ToolCall(id=call_id, name=name, input=input)],
        raw_content=[block],
        model=MockLLMClient.model,
    )


def text_only(text: str) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        tool_calls=[],
        text=text,
        raw_content=[{"type": "text", "text": text}],
        model=MockLLMClient.model,
    )


def get_llm_client() -> LLMClient:
    """Factory used by the orchestrator: provider chosen by LLM_PROVIDER."""
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicClient()
    return MockLLMClient()
