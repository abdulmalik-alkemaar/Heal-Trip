"""Tool tests: validation, empty results, errors, logging, read-only guarantees."""

from unittest.mock import patch

import pytest
from django.db import DatabaseError

from assistant.models import ChatSession, ToolCallLog
from assistant.tools import registry
from assistant.tools.registry import execute, tool_definitions
from providers.models import Doctor, Hospital


@pytest.fixture
def session(db):
    return ChatSession.objects.create(language="en")


@pytest.mark.django_db
class TestSearchProviders:
    def test_finds_cardiologists_in_riyadh(self, seeded_db):
        result = execute("search_providers", {"specialty": "CARDIOLOGY", "city": "RIYADH"})
        assert result.success
        rows = result.output["results"]
        assert rows and all(r["city"] == "RIYADH" for r in rows)
        assert all("CARDIOLOGY" in r["specialty_codes"] for r in rows)
        assert result.output["reason"] == "ok"
        assert result.result_ids == sorted(r["provider_id"] for r in rows)

    def test_results_expose_ids_not_names(self, seeded_db):
        """The LLM gets IDs and facts. Display names are rendered from the DB by the API."""
        row = execute("search_providers", {"specialty": "CARDIOLOGY"}).output["results"][0]
        assert "provider_id" in row and "name_en" not in row and "name_ar" not in row

    def test_never_returns_inactive_doctor(self, seeded_db):
        inactive_ids = set(Doctor.objects.filter(is_active=False).values_list("pk", flat=True))
        result = execute("search_providers", {"specialty": "CARDIOLOGY", "limit": 5})
        assert inactive_ids and not inactive_ids & set(result.result_ids)

    def test_language_filter(self, seeded_db):
        result = execute(
            "search_providers", {"specialty": "CARDIOLOGY", "language": "ar", "limit": 5}
        )
        assert all("ar" in r["languages"] for r in result.output["results"])

    def test_second_opinion_filter(self, seeded_db):
        result = execute(
            "search_providers", {"specialty": "CARDIOLOGY", "second_opinion": True, "limit": 5}
        )
        rows = result.output["results"]
        assert rows and all(r["offers_second_opinion"] for r in rows)

    def test_no_match_returns_reason_and_alternatives(self, seeded_db):
        """Abha has no neurologist: honest no_match + same specialty in other cities."""
        result = execute("search_providers", {"specialty": "NEUROLOGY", "city": "ABHA"})
        assert result.success
        assert result.output["results"] == []
        assert result.output["reason"] == "no_match"
        alternatives = result.output["nearby_alternatives"]
        assert alternatives and all(a["city"] != "ABHA" for a in alternatives)
        assert all("NEUROLOGY" in a["specialty_codes"] for a in alternatives)
        # Alternatives are real tool results, so they are recommendable (grounding whitelist).
        assert set(result.result_ids) == {a["provider_id"] for a in alternatives}

    def test_limit_is_respected(self, seeded_db):
        assert (
            len(execute("search_providers", {"specialty": "CARDIOLOGY", "limit": 1}).result_ids)
            == 1
        )

    def test_next_available_is_future_free_slot(self, seeded_db):
        row = execute("search_providers", {"specialty": "CARDIOLOGY"}).output["results"][0]
        assert row["next_available"] is not None


@pytest.mark.django_db
class TestValidation:
    @pytest.mark.parametrize(
        "args",
        [
            {"specialty": "DERMATOLOGY"},  # not in the enum: the model cannot invent specialties
            {"specialty": "CARDIOLOGY", "city": "LONDON"},  # nor cities
            {"specialty": "CARDIOLOGY", "limit": 50},  # bounded
            {"specialty": "CARDIOLOGY", "limit": 0},
            {"specialty": "CARDIOLOGY", "sql": "DROP TABLE providers_doctor"},  # extra=forbid
            {"city": "RIYADH"},  # missing required
            {"specialty": "CARDIOLOGY", "language": "fr"},
        ],
    )
    def test_invalid_arguments_return_structured_error(self, seeded_db, args):
        result = execute("search_providers", args)
        assert not result.success
        assert result.output["error"]["code"] == "invalid_arguments"
        assert result.output["error"]["details"]
        assert result.result_ids == []

    def test_non_object_arguments(self, seeded_db):
        assert (
            execute("search_providers", "CARDIOLOGY").output["error"]["code"] == "invalid_arguments"
        )

    def test_unknown_tool_is_rejected(self, seeded_db):
        result = execute("delete_all_patients", {})
        assert not result.success
        assert result.output["error"]["code"] == "unknown_tool"
        assert "search_providers" in result.output["error"]["available"]

    def test_db_error_becomes_structured_tool_error(self, seeded_db, session):
        def failing_search(args):
            raise DatabaseError("connection lost")

        original = registry.TOOLS["search_providers"]
        broken = registry.ToolSpec(
            name=original.name,
            description=original.description,
            input_model=original.input_model,
            func=failing_search,
        )
        with patch.dict(registry.TOOLS, {"search_providers": broken}):
            result = execute("search_providers", {"specialty": "CARDIOLOGY"}, session=session)
        assert not result.success
        assert result.output["error"]["code"] == "db_error"
        log = ToolCallLog.objects.get(session=session)
        assert not log.success and "db_error" in log.error


@pytest.mark.django_db
class TestOtherTools:
    def test_get_provider_details(self, seeded_db):
        doctor = Doctor.objects.filter(is_active=True).first()
        result = execute("get_provider_details", {"provider_id": doctor.pk})
        assert result.success
        assert result.output["name_en"] == doctor.name_en
        assert result.output["hospital"]["hospital_id"] == doctor.hospital_id

    def test_get_provider_details_not_found(self, seeded_db):
        result = execute("get_provider_details", {"provider_id": 999999})
        assert not result.success and result.output["error"]["code"] == "not_found"

    def test_get_provider_details_inactive_is_not_found(self, seeded_db):
        inactive = Doctor.objects.filter(is_active=False).first()
        result = execute("get_provider_details", {"provider_id": inactive.pk})
        assert result.output["error"]["code"] == "not_found"

    def test_check_availability(self, seeded_db):
        doctor = Doctor.objects.filter(is_active=True).first()
        result = execute("check_availability", {"provider_id": doctor.pk, "days_ahead": 14})
        slots = result.output["slots"]
        assert result.success and 0 < len(slots) <= 5
        assert slots == sorted(slots, key=lambda s: s["start_time"])

    @pytest.mark.parametrize("days", [0, 15, -1])
    def test_check_availability_bounds(self, seeded_db, days):
        doctor = Doctor.objects.filter(is_active=True).first()
        result = execute("check_availability", {"provider_id": doctor.pk, "days_ahead": days})
        assert result.output["error"]["code"] == "invalid_arguments"

    def test_emergency_info_for_city(self, seeded_db):
        result = execute("get_emergency_info", {"city": "JEDDAH"})
        numbers = [n["number"] for n in result.output["numbers"]]
        assert "997" in numbers and "911" in numbers
        hospitals = result.output["hospitals"]
        assert hospitals and all(h["city"] == "JEDDAH" for h in hospitals)
        assert all(Hospital.objects.get(pk=h["hospital_id"]).has_emergency for h in hospitals)

    def test_emergency_info_without_city_lists_all_er(self, seeded_db):
        result = execute("get_emergency_info", {})
        assert {h["city"] for h in result.output["hospitals"]} >= {"RIYADH", "JEDDAH"}


@pytest.mark.django_db
class TestLoggingAndSchemas:
    def test_every_call_is_logged(self, seeded_db, session):
        execute("search_providers", {"specialty": "CARDIOLOGY"}, session=session)
        execute("search_providers", {"specialty": "NOPE"}, session=session)
        logs = list(ToolCallLog.objects.filter(session=session).order_by("id"))
        assert [log.success for log in logs] == [True, False]
        assert logs[0].result_ids and logs[0].latency_ms >= 0
        assert logs[1].result_ids == [] and "invalid_arguments" in logs[1].error

    def test_logged_arguments_are_redacted(self, seeded_db, session):
        execute(
            "search_providers", {"specialty": "x", "note": "call me 0551234567"}, session=session
        )
        assert "0551234567" not in str(ToolCallLog.objects.get(session=session).arguments)

    def test_tool_definitions_are_self_contained_json_schema(self):
        definitions = {d["name"]: d for d in tool_definitions()}
        assert set(definitions) == set(registry.TOOLS)
        schema = definitions["search_providers"]["input_schema"]
        assert "$defs" not in str(schema) and "$ref" not in str(schema)
        assert schema["additionalProperties"] is False
        assert schema["required"] == ["specialty"]
        assert "CARDIOLOGY" in schema["properties"]["specialty"]["enum"]

    def test_tools_are_read_only(self, seeded_db):
        """No tool changes the directory (counts before == after a burst of calls)."""
        before = (Doctor.objects.count(), Hospital.objects.count())
        for spec in registry.TOOLS.values():
            execute(spec.name, {"specialty": "CARDIOLOGY", "provider_id": 1, "city": "RIYADH"})
        assert before == (Doctor.objects.count(), Hospital.objects.count())


@pytest.mark.django_db
def test_tool_queries_use_the_least_privilege_alias(seeded_db, settings):
    """Tools query via settings.TOOLS_DB_ALIAS (a SELECT-only role in production)."""
    from django.utils.connection import ConnectionDoesNotExist

    settings.TOOLS_DB_ALIAS = "no_such_alias"
    with pytest.raises(ConnectionDoesNotExist):
        execute("search_providers", {"specialty": "CARDIOLOGY"})
