"""Grounding Validator unit tests."""

import pytest

from assistant.agent.grounding import REMOVED_MARKER, validate
from assistant.models import ChatSession
from assistant.tools.registry import execute
from providers.models import Doctor, Hospital

pytestmark = pytest.mark.django_db


@pytest.fixture
def session(seeded_db):
    return ChatSession.objects.create(language="en")


def _search(session, **args):
    return execute(
        "search_providers", {"specialty": "CARDIOLOGY", **args}, session=session
    ).result_ids


def test_ids_from_session_search_are_kept(session):
    ids = _search(session, city="RIYADH")
    result = validate(session=session, recommended_provider_ids=ids, reply_text="ok", language="en")
    assert result.kept_provider_ids == ids and result.violations == []


def test_fake_id_is_dropped(session):
    _search(session)
    result = validate(
        session=session, recommended_provider_ids=[999999], reply_text="ok", language="en"
    )
    assert result.kept_provider_ids == []
    assert result.violations == [{"type": "unknown_provider_id", "provider_id": 999999}]
    assert result.all_recommendations_dropped


def test_inactive_id_is_dropped_even_if_it_exists(session):
    inactive = Doctor.objects.get(is_active=False).pk
    result = validate(
        session=session, recommended_provider_ids=[inactive], reply_text="ok", language="en"
    )
    assert result.violations[0]["type"] == "unknown_provider_id"


def test_real_id_not_returned_to_session_is_dropped(session):
    _search(session, city="RIYADH")
    abha_doctor = Doctor.objects.filter(hospital__city="ABHA", is_active=True).first().pk
    result = validate(
        session=session, recommended_provider_ids=[abha_doctor], reply_text="ok", language="en"
    )
    assert result.violations[0]["type"] == "provider_not_from_session_search"


def test_details_lookup_does_not_whitelist_an_id(session):
    """Guessing an id and fetching its details must not make it recommendable (ADR-006)."""
    guessed = Doctor.objects.filter(is_active=True).first().pk
    execute("get_provider_details", {"provider_id": guessed}, session=session)
    result = validate(
        session=session, recommended_provider_ids=[guessed], reply_text="ok", language="en"
    )
    assert result.kept_provider_ids == []


def test_empty_recommendation_is_not_a_violation(session):
    result = validate(
        session=session, recommended_provider_ids=[], reply_text="No match.", language="en"
    )
    assert result.violations == [] and not result.all_recommendations_dropped


def test_made_up_doctor_name_is_stripped(session):
    result = validate(
        session=session,
        recommended_provider_ids=[],
        reply_text="I recommend Dr. Johnathan Makeup for this.",
        language="en",
    )
    assert "Makeup" not in result.reply_text
    assert REMOVED_MARKER["en"] in result.reply_text
    assert result.violations[0]["type"] == "fabricated_doctor_name"


def test_arabic_made_up_doctor_name_is_stripped(seeded_db):
    session = ChatSession.objects.create(language="ar")
    result = validate(
        session=session,
        recommended_provider_ids=[],
        reply_text="أنصحك بزيارة د. سامي المختلق",
        language="ar",
    )
    assert "المختلق" not in result.reply_text and REMOVED_MARKER["ar"] in result.reply_text


def test_real_directory_name_not_in_session_is_stripped(session):
    doctor = Doctor.objects.get(name_en="Dr. Ahmed Bakr")
    result = validate(
        session=session,
        recommended_provider_ids=[],
        reply_text=f"Try {doctor.name_en}.",
        language="en",
    )
    assert "Bakr" not in result.reply_text
    assert result.violations[0] == {"type": "unverified_doctor_name", "provider_id": doctor.pk}


def test_hospital_name_not_in_session_is_stripped(session):
    hospital = Hospital.objects.get(name_en="Red Sea Care Hospital")
    result = validate(
        session=session,
        recommended_provider_ids=[],
        reply_text="Go to Red Sea Care Hospital.",
        language="en",
    )
    assert "Red Sea" not in result.reply_text
    assert result.violations[0] == {"type": "unverified_hospital_name", "hospital_id": hospital.pk}


def test_name_of_returned_provider_is_allowed(session):
    ids = _search(session, city="RIYADH")
    doctor = Doctor.objects.get(pk=ids[0])
    result = validate(
        session=session,
        recommended_provider_ids=ids[:1],
        reply_text=f"{doctor.name_en} is available.",
        language="en",
    )
    assert result.violations == [] and doctor.name_en in result.reply_text


def test_generic_doctor_words_are_not_flagged(session):
    text = "Please see a doctor soon. A cardiologist can examine you."
    result = validate(session=session, recommended_provider_ids=[], reply_text=text, language="en")
    assert result.reply_text == text and result.violations == []
