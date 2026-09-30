"""READ-ONLY tool implementations. ORM only, never raw SQL, never writes.

Each function takes an already-validated Pydantic input and returns a plain,
JSON-serializable dict. What goes back to the LLM is deliberately *thin*: IDs and
structured facts, not display names. The model refers to providers by
`provider_id`. The UI renders names, fees and phones straight from the DB
(assistant/api/serializers.py), so the model has nothing to paraphrase wrongly.
"""

from datetime import timedelta
from typing import Any

from django.db.models import OuterRef, Prefetch, QuerySet, Subquery
from django.utils import timezone

from providers.models import AvailabilitySlot, Doctor, Hospital, Specialty

from .schemas import (
    CheckAvailabilityInput,
    GetEmergencyInfoInput,
    GetProviderDetailsInput,
    SearchProvidersInput,
)

# Saudi national emergency numbers (public, stable). 997 is the Saudi Red Crescent
# ambulance service; 911 is the unified emergency number and also works in KSA.
EMERGENCY_NUMBERS: list[dict[str, str]] = [
    {"number": "997", "label_en": "Ambulance (Saudi Red Crescent)", "label_ar": "الإسعاف (الهلال الأحمر السعودي)"},
    {"number": "911", "label_en": "Unified emergency number", "label_ar": "رقم الطوارئ الموحد"},
    {"number": "937", "label_en": "Ministry of Health advice line (non-emergency)", "label_ar": "مركز اتصال وزارة الصحة (لغير الطوارئ)"},
]  # fmt: skip

MAX_SLOTS = 5
MAX_ER_HOSPITALS = 5


def _next_free_slot_subquery() -> Subquery:
    return Subquery(
        AvailabilitySlot.objects.filter(
            doctor=OuterRef("pk"), is_booked=False, start_time__gt=timezone.now()
        )
        .order_by("start_time")
        .values("start_time")[:1]
    )


def _active_doctors() -> QuerySet[Doctor]:
    """Base queryset for everything the agent can see: active doctors at active hospitals."""
    return (
        Doctor.objects.filter(is_active=True, hospital__is_active=True)
        .select_related("hospital")
        .prefetch_related(Prefetch("specialties", queryset=Specialty.objects.only("code")))
        .annotate(next_available=_next_free_slot_subquery())
    )


def _summary(doctor: Doctor) -> dict[str, Any]:
    """The thin, ID-based view of a doctor that the LLM sees in search results."""
    return {
        "provider_id": doctor.pk,
        "hospital_id": doctor.hospital_id,
        "specialty_codes": sorted(s.code for s in doctor.specialties.all()),
        "city": doctor.hospital.city,
        "languages": list(doctor.languages),
        "offers_second_opinion": doctor.offers_second_opinion,
        "offers_telemedicine": doctor.offers_telemedicine,
        "years_experience": doctor.years_experience,
        "next_available": doctor.next_available.isoformat() if doctor.next_available else None,
    }


def _ranked(qs: QuerySet[Doctor]) -> QuerySet[Doctor]:
    # Deterministic ordering (stable for tests and evals): best-rated, most experienced first.
    return qs.order_by("-rating", "-years_experience", "pk")


def search_providers(args: SearchProvidersInput) -> dict[str, Any]:
    qs = _active_doctors().filter(specialties__code=args.specialty)
    if args.language:
        qs = qs.filter(languages__contains=[args.language])
    if args.second_opinion:
        qs = qs.filter(offers_second_opinion=True)
    if args.telemedicine:
        qs = qs.filter(offers_telemedicine=True)

    in_city = qs.filter(hospital__city=args.city) if args.city else qs
    results = [_summary(d) for d in _ranked(in_city.distinct())[: args.limit]]

    response: dict[str, Any] = {
        "filters_applied": args.model_dump(exclude_none=True),
        "results": results,
        "reason": "ok" if results else "no_match",
        "nearby_alternatives": [],
    }
    if not results and args.city:
        # Honest alternative: same specialty and filters, other cities. We never
        # substitute a different specialty, which could mislead the patient.
        others = qs.exclude(hospital__city=args.city).distinct()
        response["nearby_alternatives"] = [_summary(d) for d in _ranked(others)[: args.limit]]
    return response


def get_provider_details(args: GetProviderDetailsInput) -> dict[str, Any]:
    doctor = _active_doctors().filter(pk=args.provider_id).first()
    if doctor is None:
        return {
            "error": {"code": "not_found", "message": f"No active provider {args.provider_id}."}
        }
    hospital = doctor.hospital
    return {
        **_summary(doctor),
        "name_en": doctor.name_en,
        "name_ar": doctor.name_ar,
        "consultation_fee_sar": str(doctor.consultation_fee_sar),
        "rating": str(doctor.rating) if doctor.rating is not None else None,
        "hospital": {
            "hospital_id": hospital.pk,
            "name_en": hospital.name_en,
            "name_ar": hospital.name_ar,
            "city": hospital.city,
            "has_emergency": hospital.has_emergency,
            "accreditation": hospital.accreditation,
        },
    }


def check_availability(args: CheckAvailabilityInput) -> dict[str, Any]:
    if not Doctor.objects.filter(pk=args.provider_id, is_active=True).exists():
        return {
            "error": {"code": "not_found", "message": f"No active provider {args.provider_id}."}
        }
    now = timezone.now()
    slots = AvailabilitySlot.objects.filter(
        doctor_id=args.provider_id,
        is_booked=False,
        start_time__gt=now,
        start_time__lte=now + timedelta(days=args.days_ahead),
    ).order_by("start_time")[:MAX_SLOTS]
    return {
        "provider_id": args.provider_id,
        "days_ahead": args.days_ahead,
        "slots": [
            {
                "slot_id": s.pk,
                "start_time": s.start_time.isoformat(),
                "duration_minutes": s.duration_minutes,
            }
            for s in slots
        ],
    }


def get_emergency_info(args: GetEmergencyInfoInput) -> dict[str, Any]:
    er = Hospital.objects.filter(is_active=True, has_emergency=True)
    hospitals = list(er.filter(city=args.city)) if args.city else []
    if not hospitals:
        # Unknown city, or no ER there: list ERs everywhere rather than nothing.
        hospitals = list(er.order_by("city", "name_en")[:MAX_ER_HOSPITALS])
    return {
        "numbers": EMERGENCY_NUMBERS,
        "city": args.city,
        "hospitals": [
            {"hospital_id": h.pk, "city": h.city, "has_emergency": True} for h in hospitals
        ],
    }
