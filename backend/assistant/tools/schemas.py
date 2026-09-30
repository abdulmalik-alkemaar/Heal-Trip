"""Pydantic input schemas for the agent's tools.

These models are the contract between the LLM and the database:
- `extra="forbid"`: unknown arguments are rejected, not silently ignored.
- Enums (`SpecialtyCode`, `City`) and bounded ints mean the model can only ask for
  things that exist, in amounts we allow. The same models generate the JSON Schema
  the model sees, so the prompt and the validation can never drift apart.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from providers.choices import City, SpecialtyCode


class _ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class SearchProvidersInput(_ToolInput):
    specialty: SpecialtyCode = Field(description="Required specialty code.")
    city: City | None = Field(
        default=None, description="Patient's city. Omit if unknown to search all cities."
    )
    language: Literal["ar", "en"] | None = Field(
        default=None, description="Only doctors who speak this language."
    )
    second_opinion: bool | None = Field(
        default=None, description="true = only doctors who offer second-opinion consultations."
    )
    telemedicine: bool | None = Field(
        default=None, description="true = only doctors who offer telemedicine (video) visits."
    )
    limit: int = Field(default=3, ge=1, le=5, description="Maximum results (1-5).")


class GetProviderDetailsInput(_ToolInput):
    provider_id: int = Field(ge=1, description="A provider_id returned by search_providers.")


class CheckAvailabilityInput(_ToolInput):
    provider_id: int = Field(ge=1, description="A provider_id returned by search_providers.")
    days_ahead: int = Field(default=7, ge=1, le=14, description="Look-ahead window in days (1-14).")


class GetEmergencyInfoInput(_ToolInput):
    city: City | None = Field(
        default=None, description="Patient's city, to list its emergency departments first."
    )
