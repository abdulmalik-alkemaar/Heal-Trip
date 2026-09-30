"""drf-spectacular extension: document our authenticator as the standard cookie scheme.
Imported from AssistantConfig.ready() so it is registered before schema generation."""

from drf_spectacular.authentication import SessionScheme


class CsrfEnforcedSessionScheme(SessionScheme):
    target_class = "assistant.api.authentication.CsrfEnforcedSessionAuthentication"
