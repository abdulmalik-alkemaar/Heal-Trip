from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from core.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _offline_llm(settings):
    """Tests never call the real LLM, even if a developer's .env has a key."""
    settings.LLM_PROVIDER = "mock"
    settings.ANTHROPIC_API_KEY = ""


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; isolate them per test."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def authenticated_client(user):
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def seeded_db(db):
    """The full fictional provider directory (the same data the demo uses)."""
    call_command("seed_providers", stdout=StringIO())
