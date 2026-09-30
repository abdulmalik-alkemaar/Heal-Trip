import pytest

from .factories import UserFactory


@pytest.mark.django_db
class TestUser:
    def test_create_user(self):
        user = UserFactory()
        assert user.pk is not None
        assert user.is_active

    def test_str_returns_email(self):
        user = UserFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_str_returns_username_when_no_email(self):
        user = UserFactory(email="", username="testuser")
        assert str(user) == "testuser"
