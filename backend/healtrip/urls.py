"""Root URL configuration for healtrip project."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("core.urls")),
    path("api/", include("providers.urls")),
    path("api/", include("assistant.api.urls")),
    # OpenAPI 3 schema + interactive docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
]

# JSON (not HTML) error pages when DEBUG=False.
handler404 = "assistant.api.errors.json_404"
handler500 = "assistant.api.errors.json_500"
