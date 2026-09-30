"""API tests: endpoints, ownership, CSRF, validation, error format, throttling, limits."""

import uuid
from unittest.mock import patch

import pytest
from django.test import Client
from rest_framework.throttling import SimpleRateThrottle

from assistant.models import ChatSession, Message

pytestmark = pytest.mark.django_db

TASK_EXAMPLE = (
    "I have chest pain and I'm not sure whether I should see a cardiologist, "
    "go to the ER, or seek a second opinion."
)


def csrf_client() -> Client:
    """A browser-like client: CSRF enforced, token fetched the way the SPA does."""
    client = Client(enforce_csrf_checks=True)
    client.get("/api/csrf-token/")
    client.defaults["HTTP_X_CSRFTOKEN"] = client.cookies["csrftoken"].value
    return client


def new_session(client: Client, language: str = "en") -> str:
    response = client.post(
        "/api/chat/sessions/", {"language": language}, content_type="application/json"
    )
    assert response.status_code == 201, response.content
    return response.json()["session_id"]


def send(client: Client, session_id: str, content: str):
    return client.post(
        f"/api/chat/sessions/{session_id}/messages/",
        {"content": content},
        content_type="application/json",
    )


def assert_error(response, status: int, code: str):
    assert response.status_code == status, response.content
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message_en"] and error["message_ar"]
    return error


class TestChatFlow:
    def test_create_session(self, seeded_db):
        client = csrf_client()
        response = client.post(
            "/api/chat/sessions/", {"language": "ar"}, content_type="application/json"
        )
        body = response.json()
        assert response.status_code == 201
        assert ChatSession.objects.get(pk=body["session_id"]).language == "ar"
        assert body["disclaimer"]["en"] and body["disclaimer"]["ar"]

    def test_send_message_response_contract(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        body = send(client, session_id, TASK_EXAMPLE).json()
        expected = {
            "message_id", "reply_text", "urgency", "urgency_source", "next_step",
            "clarifying_questions", "providers", "emergency", "reasoning_summary", "trace", "disclaimer",
        }  # fmt: skip
        assert expected <= set(body)
        assert body["next_step"] == "NEED_MORE_INFO" and body["clarifying_questions"]
        assert {"state", "stage", "tool_calls", "iterations", "grounding_violations"} <= set(
            body["trace"]
        )

    def test_provider_cards_come_from_the_database(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        body = send(
            client, session_id, "I want a second opinion about my heart diagnosis in Riyadh"
        ).json()
        assert body["providers"], body
        card = body["providers"][0]
        assert {"name_en", "name_ar", "hospital", "consultation_fee_sar", "next_available"} <= set(
            card
        )
        assert card["hospital"]["name_ar"] and card["offers_second_opinion"] is True

    def test_emergency_response_includes_numbers_and_hospitals(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        body = send(
            client, session_id, "crushing chest pain spreading to my left arm and sweating"
        ).json()
        assert body["urgency"] == "EMERGENCY" and body["next_step"] == "CALL_EMERGENCY"
        assert body["emergency"]["numbers"][0]["number"] == "997"
        assert all(h["has_emergency"] for h in body["emergency"]["hospitals"])

    def test_history(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        send(client, session_id, TASK_EXAMPLE)
        body = client.get(f"/api/chat/sessions/{session_id}/").json()
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert body["messages"][1]["turn"]["next_step"] == "NEED_MORE_INFO"
        assert body["stage"] == "CLARIFY" and body["messages_remaining"] == 49

    def test_stored_message_is_sanitized(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        send(client, session_id, "knee pain\x07‮, call me on 0551234567 or a@b.com")
        stored = Message.objects.get(session_id=session_id, role="user").content
        assert "\x07" not in stored and "‮" not in stored
        assert "0551234567" not in stored and "a@b.com" not in stored


class TestOwnershipAndCsrf:
    def test_other_browser_cannot_read_or_write(self, seeded_db):
        owner, stranger = csrf_client(), csrf_client()
        session_id = new_session(owner)
        assert_error(stranger.get(f"/api/chat/sessions/{session_id}/"), 404, "not_found")
        assert_error(send(stranger, session_id, "hello"), 404, "not_found")

    def test_unknown_session_is_404(self, seeded_db):
        assert_error(csrf_client().get(f"/api/chat/sessions/{uuid.uuid4()}/"), 404, "not_found")

    def test_post_without_csrf_token_is_rejected(self, seeded_db):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            "/api/chat/sessions/", {"language": "en"}, content_type="application/json"
        )
        assert_error(response, 403, "csrf_failed")

    def test_logged_in_user_sees_own_session_from_another_browser(self, seeded_db, user):
        first = csrf_client()
        first.force_login(user)
        session_id = new_session(first)
        second = Client()
        second.force_login(user)
        assert second.get(f"/api/chat/sessions/{session_id}/").status_code == 200


class TestValidationAndLimits:
    def test_message_too_long(self, seeded_db):
        client = csrf_client()
        error = assert_error(send(client, new_session(client), "x" * 1001), 400, "validation_error")
        assert "content" in error["details"]

    @pytest.mark.parametrize("payload", [{}, {"content": ""}, {"content": "   "}])
    def test_empty_message(self, seeded_db, payload):
        client = csrf_client()
        session_id = new_session(client)
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages/", payload, content_type="application/json"
        )
        assert_error(response, 400, "validation_error")

    def test_null_bytes_are_rejected(self, seeded_db):
        client = csrf_client()
        assert_error(send(client, new_session(client), "hi\x00there"), 400, "validation_error")

    def test_invalid_language(self, seeded_db):
        response = csrf_client().post(
            "/api/chat/sessions/", {"language": "fr"}, content_type="application/json"
        )
        assert_error(response, 400, "validation_error")

    def test_malformed_json(self, seeded_db):
        response = csrf_client().post(
            "/api/chat/sessions/", "{not json", content_type="application/json"
        )
        assert_error(response, 400, "parse_error")

    def test_session_message_limit(self, seeded_db, settings):
        settings.CHAT_MAX_MESSAGES_PER_SESSION = 1
        client = csrf_client()
        session_id = new_session(client)
        assert send(client, session_id, "knee pain").status_code == 200
        assert_error(send(client, session_id, "more knee pain"), 409, "session_limit_reached")

    def test_ip_rate_limit(self, seeded_db, monkeypatch):
        monkeypatch.setattr(
            SimpleRateThrottle,
            "THROTTLE_RATES",
            {
                "chat_minute": "2/min",
                "chat_day": "100/day",
                "chat_session": "100/min",
                "session_create": "100/hour",
            },
        )
        client = csrf_client()
        session_id = new_session(client)
        assert send(client, session_id, "knee pain").status_code == 200
        assert send(client, session_id, "knee pain again").status_code == 200
        error = assert_error(send(client, session_id, "knee pain 3"), 429, "rate_limited")
        assert error["details"]["retry_after_seconds"] > 0

    def test_per_session_rate_limit(self, seeded_db, monkeypatch):
        monkeypatch.setattr(
            SimpleRateThrottle,
            "THROTTLE_RATES",
            {
                "chat_minute": "100/min",
                "chat_day": "100/day",
                "chat_session": "1/min",
                "session_create": "100/hour",
            },
        )
        client = csrf_client()
        session_id = new_session(client)
        assert send(client, session_id, "knee pain").status_code == 200
        assert_error(send(client, session_id, "again"), 429, "rate_limited")
        assert send(client, new_session(client), "a new conversation is fine").status_code == 200

    def test_global_daily_cap(self, seeded_db, settings):
        settings.DEMO_DAILY_MESSAGE_CAP = 1
        client = csrf_client()
        session_id = new_session(client)
        assert send(client, session_id, "knee pain").status_code == 200
        assert_error(send(client, session_id, "again"), 429, "daily_cap_reached")


class TestErrorsAndPublicEndpoints:
    def test_unhandled_exception_returns_generic_500(self, seeded_db):
        client = csrf_client()
        session_id = new_session(client)
        with patch(
            "assistant.api.views.handle_message", side_effect=RuntimeError("secret internals")
        ):
            response = send(client, session_id, "hello")
        assert_error(response, 500, "internal_error")
        assert b"secret internals" not in response.content

    def test_unknown_api_route_is_json_404(self, db):
        assert_error(Client().get("/api/does-not-exist/"), 404, "not_found")

    def test_health_reports_status_without_secrets(self, db, settings):
        settings.ANTHROPIC_API_KEY = "sk-ant-super-secret"
        response = Client().get("/api/health/")
        body = response.json()
        assert response.status_code == 200 and body["database"] == "ok"
        assert body["llm"]["api_key_configured"] is True
        assert b"sk-ant-super-secret" not in response.content

    def test_providers_filters(self, seeded_db):
        body = Client().get("/api/providers/?specialty=CARDIOLOGY&city=JEDDAH&language=ar").json()
        assert body["count"] >= 1
        for doctor in body["results"]:
            assert doctor["hospital"]["city"] == "JEDDAH" and "ar" in doctor["languages"]
            assert "CARDIOLOGY" in [s["code"] for s in doctor["specialties"]]

    def test_providers_rejects_unknown_filter_value(self, seeded_db):
        assert_error(Client().get("/api/providers/?city=LONDON"), 400, "validation_error")

    def test_specialties(self, seeded_db):
        codes = [s["code"] for s in Client().get("/api/specialties/").json()]
        assert "CARDIOLOGY" in codes and len(codes) == 7

    def test_openapi_docs(self, db):
        assert Client().get("/api/docs/").status_code == 200
        assert Client().get("/api/schema/").status_code == 200
