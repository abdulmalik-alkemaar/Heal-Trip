"""AnthropicClient retry/timeout policy (SDK calls are faked; no network) + mock demo policy."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx2
import pytest
from tenacity import wait_none

from assistant.agent.orchestrator import handle_message
from assistant.llm.client import AnthropicClient, LLMUnavailableError, MockLLMClient, _replayable
from assistant.models import ChatSession

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(cls, code):
    return cls("boom", response=httpx2.Response(code, request=REQUEST), body=None)


def _ok_message():
    block = SimpleNamespace(type="tool_use", id="t1", name="submit_response", input={"x": 1})
    return SimpleNamespace(content=[block], stop_reason="tool_use", model="claude-sonnet-5-5")


@pytest.fixture
def client(settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "test-key-not-real"
    settings.LLM_MAX_RETRIES = 2
    settings.LLM_REFUSAL_FALLBACK = False
    monkeypatch.setattr(AnthropicClient, "retry_wait", wait_none())
    c = AnthropicClient()
    c._client = MagicMock()
    return c


def _call(c):
    return c.create(system="s", messages=[{"role": "user", "content": "hi"}], tools=[])


def test_retries_transient_errors_then_succeeds(client):
    client._client.messages.create.side_effect = [
        anthropic.APITimeoutError(request=REQUEST),
        _status_error(anthropic.InternalServerError, 500),
        _ok_message(),
    ]
    response = _call(client)
    assert response.tool_calls[0].name == "submit_response"
    assert client._client.messages.create.call_count == 3


def test_rate_limit_is_retried(client):
    client._client.messages.create.side_effect = [
        _status_error(anthropic.RateLimitError, 429),
        _ok_message(),
    ]
    assert _call(client).stop_reason == "tool_use"


def test_retries_exhausted_raises_unavailable(client):
    client._client.messages.create.side_effect = anthropic.APITimeoutError(request=REQUEST)
    with pytest.raises(LLMUnavailableError) as exc:
        _call(client)
    assert exc.value.reason == "llm_unavailable"
    assert client._client.messages.create.call_count == 3  # 1 try + 2 retries


def test_bad_request_is_not_retried(client):
    client._client.messages.create.side_effect = _status_error(anthropic.BadRequestError, 400)
    with pytest.raises(LLMUnavailableError) as exc:
        _call(client)
    assert exc.value.reason == "llm_http_400"
    assert client._client.messages.create.call_count == 1


def test_request_shape(client):
    client._client.messages.create.return_value = _ok_message()
    _call(client)
    kwargs = client._client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "auto"}
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["output_config"]["effort"]


def test_refusal_fallback_uses_beta_endpoint(client, settings):
    settings.LLM_REFUSAL_FALLBACK = True
    client._client.beta.messages.create.return_value = _ok_message()
    _call(client)
    kwargs = client._client.beta.messages.create.call_args.kwargs
    assert kwargs["fallbacks"] == "default" and kwargs["betas"] == [
        "server-side-fallback-2026-07-01"
    ]


def test_missing_key_is_unavailable(settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(LLMUnavailableError):
        AnthropicClient()


def test_replayable_drops_declined_attempt_blocks():
    blocks = [
        SimpleNamespace(type="thinking"),
        SimpleNamespace(type="tool_use"),
        SimpleNamespace(type="text"),
        SimpleNamespace(type="fallback"),
        SimpleNamespace(type="tool_use"),
    ]
    assert [b.type for b in _replayable(blocks)] == ["text", "tool_use"]


@pytest.mark.django_db
class TestMockDemoPolicy:
    def test_task_example_asks_clarifying_questions_first(self, seeded_db):
        session = ChatSession.objects.create(language="en")
        text = (
            "I have chest pain and I'm not sure whether I should see a cardiologist, "
            "go to the ER, or seek a second opinion."
        )
        payload = handle_message(session, text, MockLLMClient()).payload
        assert payload["next_step"] == "NEED_MORE_INFO"
        assert 1 <= len(payload["clarifying_questions"]) <= 3
        assert payload["urgency"] == "URGENT"

    def test_second_opinion_request_recommends_second_opinion_doctors(self, seeded_db):
        session = ChatSession.objects.create(language="en")
        payload = handle_message(
            session,
            "I was diagnosed with a heart condition and want a second opinion in Jeddah",
            MockLLMClient(),
        ).payload
        assert payload["next_step"] == "SECOND_OPINION" and payload["provider_ids"]
