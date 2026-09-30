from django.apps import AppConfig


class AssistantConfig(AppConfig):
    name = "assistant"

    def ready(self) -> None:
        from .api import schema  # noqa: F401  (registers the OpenAPI auth extension)
