"""Seed the FICTIONAL provider directory. Idempotent: safe to run on every container start.

- Specialties / hospitals / doctors are upserted on natural keys (code, name, name+hospital).
- Slots are created with get_or_create on (doctor, start_time), so re-running never
  duplicates slots and never resets a slot that was marked booked.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from providers.models import AvailabilitySlot, Doctor, Hospital, Specialty
from providers.seed_data import HOSPITALS, SPECIALTIES, doctor_rows

RIYADH_TZ = ZoneInfo("Asia/Riyadh")
SLOT_DAYS = 14
# Clinic hours (local time). Each doctor gets a deterministic subset (see _slot_times).
CLINIC_TIMES = [time(9, 0), time(10, 30), time(13, 0), time(16, 0), time(18, 30)]
FRIDAY = 4  # datetime.weekday(): Monday=0 ... Friday=4 (weekend in KSA)


class Command(BaseCommand):
    help = "Create/update the fictional doctors, hospitals and 14 days of availability slots."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        specialties = self._seed_specialties()
        hospitals = self._seed_hospitals()
        doctors = self._seed_doctors(specialties, hospitals)
        slots_created = self._seed_slots(doctors)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(specialties)} specialties, {len(hospitals)} hospitals, "
                f"{len(doctors)} doctors, {slots_created} new slots (all data is FICTIONAL)."
            )
        )

    def _seed_specialties(self) -> dict[str, Specialty]:
        result = {}
        for code, name_en, name_ar in SPECIALTIES:
            obj, _ = Specialty.objects.update_or_create(
                code=code, defaults={"name_en": name_en, "name_ar": name_ar}
            )
            result[str(code)] = obj
        return result

    def _seed_hospitals(self) -> dict[str, Hospital]:
        result = {}
        for key, fields in HOSPITALS.items():
            data = dict(fields)
            obj, _ = Hospital.objects.update_or_create(
                name_en=data.pop("name_en"), defaults={**data, "is_active": True}
            )
            result[key] = obj
        return result

    def _seed_doctors(
        self, specialties: dict[str, Specialty], hospitals: dict[str, Hospital]
    ) -> list[Doctor]:
        doctors = []
        for row in doctor_rows():
            codes = row.pop("specialties")
            hospital = hospitals[row.pop("hospital_key")]
            doctor, _ = Doctor.objects.update_or_create(
                name_en=row.pop("name_en"), hospital=hospital, defaults=row
            )
            doctor.specialties.set([specialties[c] for c in codes])
            doctors.append(doctor)
        return doctors

    def _seed_slots(self, doctors: list[Doctor]) -> int:
        today = timezone.localdate(timezone=RIYADH_TZ)
        created = 0
        for doctor in doctors:
            if not doctor.is_active:
                continue
            for day_offset in range(1, SLOT_DAYS + 1):
                day = today + timedelta(days=day_offset)
                if day.weekday() == FRIDAY:
                    continue
                for slot_index, slot_time in enumerate(self._slot_times(doctor.pk, day_offset)):
                    start = datetime.combine(day, slot_time, tzinfo=RIYADH_TZ)
                    # Deterministically pre-book some slots so availability looks realistic.
                    booked = (doctor.pk + day_offset + slot_index) % 4 == 0
                    _, was_created = AvailabilitySlot.objects.get_or_create(
                        doctor=doctor,
                        start_time=start,
                        defaults={"duration_minutes": 30, "is_booked": booked},
                    )
                    created += int(was_created)
        return created

    @staticmethod
    def _slot_times(doctor_pk: int, day_offset: int) -> list[time]:
        """Pick 2 clinic times per day, varying by doctor and day (deterministic)."""
        start = (doctor_pk + day_offset) % len(CLINIC_TIMES)
        return [CLINIC_TIMES[start], CLINIC_TIMES[(start + 2) % len(CLINIC_TIMES)]]
