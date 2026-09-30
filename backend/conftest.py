from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from core.tests.factories import UserFactory


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
