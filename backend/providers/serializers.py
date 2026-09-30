"""Provider cards: the ONLY way provider facts reach the UI.

Every name, phone, fee and address the patient sees is serialized from these DB
rows, never from LLM text. Both languages are included; the client picks one.
"""

from django.utils import timezone
from rest_framework import serializers

from .choices import CITY_NAMES_AR
from .models import Doctor, Hospital, Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["code", "name_en", "name_ar"]


class HospitalCardSerializer(serializers.ModelSerializer):
    hospital_id = serializers.IntegerField(source="pk")
    city_name_en = serializers.CharField(source="get_city_display")
    city_name_ar = serializers.SerializerMethodField()

    class Meta:
        model = Hospital
        fields = [
            "hospital_id",
            "name_en",
            "name_ar",
            "city",
            "city_name_en",
            "city_name_ar",
            "address_en",
            "address_ar",
            "has_emergency",
            "emergency_phone",
            "accreditation",
        ]

    def get_city_name_ar(self, obj: Hospital) -> str:
        return CITY_NAMES_AR.get(obj.city, obj.city)


class DoctorCardSerializer(serializers.ModelSerializer):
    provider_id = serializers.IntegerField(source="pk")
    specialties = SpecialtySerializer(many=True, read_only=True)
    hospital = HospitalCardSerializer(read_only=True)
    next_available = serializers.SerializerMethodField()

    class Meta:
        model = Doctor
        fields = [
            "provider_id",
            "name_en",
            "name_ar",
            "specialties",
            "hospital",
            "languages",
            "years_experience",
            "offers_second_opinion",
            "offers_telemedicine",
            "consultation_fee_sar",
            "rating",
            "next_available",
        ]

    def get_next_available(self, obj: Doctor) -> str | None:
        slot = (
            obj.slots.filter(is_booked=False, start_time__gt=timezone.now())
            .order_by("start_time")
            .values_list("start_time", flat=True)
            .first()
        )
        return slot.isoformat() if slot else None


def doctor_cards(provider_ids: list[int]) -> list[dict]:
    """Serialize active doctors in the given order (unknown/inactive ids are skipped)."""
    doctors = (
        Doctor.objects.filter(pk__in=provider_ids, is_active=True, hospital__is_active=True)
        .select_related("hospital")
        .prefetch_related("specialties")
    )
    by_id = {d.pk: d for d in doctors}
    ordered = [by_id[i] for i in provider_ids if i in by_id]
    return DoctorCardSerializer(ordered, many=True).data


def hospital_cards(hospital_ids: list[int]) -> list[dict]:
    hospitals = {h.pk: h for h in Hospital.objects.filter(pk__in=hospital_ids, is_active=True)}
    return HospitalCardSerializer(
        [hospitals[i] for i in hospital_ids if i in hospitals], many=True
    ).data
