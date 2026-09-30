"""Tool registry: the ONLY way the agent can touch data.

One table maps tool name -> (description, Pydantic input model, function). `execute()`
is the single choke point for every call, and it:
  1. rejects unknown tool names (the model cannot invent capabilities),
  2. validates arguments with Pydantic; errors are returned to the model as a
     structured tool error so it can self-correct instead of crashing the turn,
  3. runs the read-only function, converting DB failures into structured errors,
  4. logs the call (redacted args, returned IDs, latency, success) to ToolCallLog.
The returned `result_ids` feed the grounding validator.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.db import DatabaseError
from pydantic import BaseModel, ValidationError

from assistant.models import AgentRunLog, ChatSession, ToolCallLog
from assistant.safety.pii import redact_value

from . import provider_tools
from .schemas import (
    CheckAvailabilityInput,
    GetEmergencyInfoInput,
    GetProviderDetailsInput,
    SearchProvidersInput,
)

logger = logging.getLogger(__name__)

SEARCH_TOOL = "search_providers"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    func: Callable[[Any], dict[str, Any]]


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name=SEARCH_TOOL,
            description=(
                "Search the HealTrip provider directory for active doctors by specialty, "
                "optionally filtered by city, spoken language, second-opinion and telemedicine "
                "support. Returns provider_ids (not names). If nothing matches in the city, "
                "'reason' is 'no_match' and 'nearby_alternatives' lists the same specialty in "
                "other cities. This is the ONLY source of providers you may recommend."
            ),
            input_model=SearchProvidersInput,
            func=provider_tools.search_providers,
        ),
        ToolSpec(
            name="get_provider_details",
            description=(
                "Get full directory details for one provider_id previously returned by "
                "search_providers. Returns a not_found error for unknown or inactive ids."
            ),
            input_model=GetProviderDetailsInput,
            func=provider_tools.get_provider_details,
        ),
        ToolSpec(
            name="check_availability",
            description=(
                "List up to 5 upcoming free appointment slots for a provider_id within "
                "days_ahead (1-14) days."
            ),
            input_model=CheckAvailabilityInput,
            func=provider_tools.check_availability,
        ),
        ToolSpec(
            name="get_emergency_info",
            description=(
                "Get Saudi national emergency numbers and hospitals with an emergency "
                "department (optionally in the patient's city). Use whenever the situation "
                "may be an emergency."
            ),
            input_model=GetEmergencyInfoInput,
            func=provider_tools.get_emergency_info,
        ),
    ]
}


@dataclass
class ToolExecution:
    name: str
    output: dict[str, Any]
    success: bool
    latency_ms: int
    arguments: dict[str, Any] = field(default_factory=dict)
    result_ids: list[int] = field(default_factory=list)
    result_hospital_ids: list[int] = field(default_factory=list)


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline Pydantic `$defs` so each tool's input_schema is self-contained."""
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)


def input_schema(spec: ToolSpec) -> dict[str, Any]:
    schema = _inline_refs(spec.input_model.model_json_schema())
    schema.pop("title", None)
    schema["additionalProperties"] = False
    return schema


def tool_definitions() -> list[dict[str, Any]]:
    """Tool list in Anthropic Messages API format, generated from the Pydantic models."""
    return [
        {"name": s.name, "description": s.description, "input_schema": input_schema(s)}
        for s in TOOLS.values()
    ]


def _extract_ids(output: dict[str, Any]) -> tuple[list[int], list[int]]:
    doctor_ids: list[int] = []
    hospital_ids: list[int] = []
    rows = list(output.get("results", [])) + list(output.get("nearby_alternatives", []))
    if "provider_id" in output:
        rows.append(output)
    for row in rows:
        doctor_ids.append(row["provider_id"])
        if row.get("hospital_id"):
            hospital_ids.append(row["hospital_id"])
    for hospital in output.get("hospitals", []):
        hospital_ids.append(hospital["hospital_id"])
    if isinstance(output.get("hospital"), dict):
        hospital_ids.append(output["hospital"]["hospital_id"])
    return sorted(set(doctor_ids)), sorted(set(hospital_ids))


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, **extra}}


def _run(name: str, raw_args: Any) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Validate + execute. Returns (output, logged_arguments, success). Never raises."""
    spec = TOOLS.get(name)
    if spec is None:
        return _error("unknown_tool", f"Unknown tool '{name}'.", available=sorted(TOOLS)), {}, False
    if not isinstance(raw_args, dict):
        return _error("invalid_arguments", "Arguments must be a JSON object."), {}, False
    try:
        args = spec.input_model.model_validate(raw_args)
    except ValidationError as exc:
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]} for e in exc.errors()
        ]
        message = "Invalid arguments; fix them and call the tool again."
        return _error("invalid_arguments", message, details=details), raw_args, False
    logged_args = args.model_dump(exclude_none=True)
    try:
        output = spec.func(args)
    except DatabaseError:
        logger.exception("tool_db_error", extra={"tool": name})
        return _error("db_error", "The directory is temporarily unavailable."), logged_args, False
    return output, logged_args, "error" not in output


def execute(
    name: str,
    raw_args: Any,
    *,
    session: ChatSession | None = None,
    run: AgentRunLog | None = None,
) -> ToolExecution:
    """Execute a tool call from the model (or from code, e.g. the emergency path) and log it."""
    started = time.monotonic()
    output, logged_args, success = _run(name, raw_args)
    latency_ms = int((time.monotonic() - started) * 1000)
    doctor_ids, hospital_ids = _extract_ids(output) if success else ([], [])
    execution = ToolExecution(
        name=name,
        output=output,
        success=success,
        latency_ms=latency_ms,
        arguments=redact_value(logged_args),
        result_ids=doctor_ids,
        result_hospital_ids=hospital_ids,
    )
    if session is not None:
        _log(execution, session, run)
    logger.info(
        "tool_call",
        extra={"tool": name, "success": success, "latency_ms": latency_ms, "ids": doctor_ids},
    )
    return execution


def _log(execution: ToolExecution, session: ChatSession, run: AgentRunLog | None) -> None:
    try:
        ToolCallLog.objects.create(
            session=session,
            run=run,
            tool_name=execution.name[:60],
            arguments=execution.arguments,
            result_ids=execution.result_ids,
            result_hospital_ids=execution.result_hospital_ids,
            success=execution.success,
            error="" if execution.success else str(execution.output.get("error", ""))[:1000],
            latency_ms=execution.latency_ms,
        )
    except DatabaseError:
        # Audit logging must never take down the patient-facing answer.
        logger.exception("tool_log_write_failed", extra={"tool": execution.name})
