import pytest
from django.test import Client


@pytest.mark.django_db
class TestCSRFTokenView:
    def test_csrf_token_returns_200(self):
        client = Client()
        response = client.get("/api/csrf-token/")
        assert response.status_code == 200

    def test_csrf_token_sets_cookie(self):
        client = Client()
        response = client.get("/api/csrf-token/")
        assert "csrftoken" in response.cookies


@pytest.mark.django_db
class TestProfileView:
    def test_profile_requires_auth(self):
        client = Client()
        response = client.get("/api/profile/")
        assert response.status_code == 403

    def test_profile_returns_user_data(self, authenticated_client, user):
        response = authenticated_client.get("/api/profile/")
        assert response.status_code == 200
        assert response.json()["email"] == user.email


@pytest.mark.django_db
class TestHealthCheckView:
    def test_health_returns_200(self):
        client = Client()
        response = client.get("/api/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
