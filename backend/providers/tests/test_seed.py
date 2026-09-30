from io import StringIO

import pytest
from django.core.management import call_command

from providers.choices import City, SpecialtyCode
from providers.models import AvailabilitySlot, Doctor, Hospital, Specialty


@pytest.mark.django_db
class TestSeedProviders:
    def test_seed_creates_directory(self, seeded_db):
        assert Specialty.objects.count() == len(SpecialtyCode)
        assert Hospital.objects.count() == 8
        assert Doctor.objects.count() >= 25
        assert AvailabilitySlot.objects.exists()

    def test_seed_is_idempotent(self, seeded_db):
        counts = (
            Hospital.objects.count(),
            Doctor.objects.count(),
            AvailabilitySlot.objects.count(),
        )
        call_command("seed_providers", stdout=StringIO())
        assert counts == (
            Hospital.objects.count(),
            Doctor.objects.count(),
            AvailabilitySlot.objects.count(),
        )

    def test_every_city_has_an_emergency_department(self, seeded_db):
        for city in City:
            assert Hospital.objects.filter(city=city, has_emergency=True, is_active=True).exists()

    def test_abha_has_no_neurology_on_purpose(self, seeded_db):
        """The deliberate gap that exercises the honest 'not found' path."""
        assert not Doctor.objects.filter(
            hospital__city=City.ABHA, specialties__code=SpecialtyCode.NEUROLOGY
        ).exists()
        assert Doctor.objects.filter(specialties__code=SpecialtyCode.NEUROLOGY).exists()

    def test_inactive_doctor_gets_no_slots(self, seeded_db):
        inactive = Doctor.objects.filter(is_active=False)
        assert inactive.exists()
        assert not AvailabilitySlot.objects.filter(doctor__in=inactive).exists()

    def test_all_user_facing_text_is_bilingual(self, seeded_db):
        for hospital in Hospital.objects.all():
            assert hospital.name_ar and hospital.address_ar
        for doctor in Doctor.objects.all():
            assert doctor.name_ar
        for specialty in Specialty.objects.all():
            assert specialty.name_ar

    def test_languages_array_filter(self, seeded_db):
        arabic_speakers = Doctor.objects.filter(languages__contains=["ar"])
        english_only = Doctor.objects.exclude(languages__contains=["ar"])
        assert arabic_speakers.exists() and english_only.exists()
