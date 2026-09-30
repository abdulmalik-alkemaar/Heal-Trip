"""Privacy + security helpers: PII redaction, log filter, retention purge, key hygiene."""

import logging
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from assistant.agent.orchestrator import sanitize
from assistant.models import ChatSession, Message
from assistant.safety.pii import redact
from healtrip.logging import PiiRedactingFilter


@pytest.mark.parametrize(
    "text, leaked",
    [
        ("call me on 0551234567", "0551234567"),
        ("my number is +966 55 123 4567", "123 4567"),
        ("email: patient@example.com", "patient@example.com"),
        ("national id 1012345678", "1012345678"),
        ("iqama 2123456789", "2123456789"),
        ("card 4111111111111111", "4111111111111111"),
    ],
)
def test_pii_is_redacted(text, leaked):
    assert leaked not in redact(text)


def test_redaction_keeps_clinical_numbers():
    text = "pain 7 out of 10 for 2 weeks, I am 45"
    assert redact(text) == text


def test_sanitize_strips_bidi_and_control_characters():
    assert sanitize("chest‮ pain\x07​") == "chest pain"


def test_log_filter_redacts_message_args_and_extras():
    record = logging.LogRecord("x", logging.INFO, "", 0, "user said %s", ("0551234567",), None)
    record.note = "mail a@b.com"
    PiiRedactingFilter().filter(record)
    assert "0551234567" not in record.getMessage()
    assert "a@b.com" not in record.note


@pytest.mark.django_db
def test_purge_old_sessions():
    old = ChatSession.objects.create(language="en")
    Message.objects.create(session=old, role="user", content="old")
    fresh = ChatSession.objects.create(language="en")
    ChatSession.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=31))

    out = StringIO()
    call_command("purge_old_sessions", "--dry-run", stdout=out)
    assert "Would delete 1" in out.getvalue() and ChatSession.objects.count() == 2

    call_command("purge_old_sessions", stdout=StringIO())
    assert list(ChatSession.objects.values_list("pk", flat=True)) == [fresh.pk]
    assert not Message.objects.filter(session_id=old.pk).exists()  # cascade


@pytest.mark.django_db
def test_api_key_never_reaches_a_response(settings, seeded_db):
    settings.ANTHROPIC_API_KEY = "sk-ant-api03-never-leak-this"
    client = Client()
    for url in ["/api/health/", "/api/providers/", "/api/specialties/", "/api/schema/"]:
        assert b"never-leak-this" not in client.get(url).content
