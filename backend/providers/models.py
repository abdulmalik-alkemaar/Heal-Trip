"""Provider directory: the single source of truth for doctors and hospitals.

The LLM never writes provider facts itself. It can only reference rows here by ID,
and the API renders provider cards from these rows (see assistant/agent/grounding.py).
All user-facing text is stored in both English and Arabic.
"""

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models

from .choices import City, LanguageCode, SpecialtyCode


class Specialty(models.Model):
    code = models.CharField(max_length=40, unique=True, choices=SpecialtyCode.choices)
    name_en = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "specialties"

    def __str__(self) -> str:
        return self.code


class Hospital(models.Model):
    name_en = models.CharField(max_length=200, unique=True)
    name_ar = models.CharField(max_length=200)
    city = models.CharField(max_length=20, choices=City.choices)
    address_en = models.CharField(max_length=300)
    address_ar = models.CharField(max_length=300)
    has_emergency = models.BooleanField(default=False)
    emergency_phone = models.CharField(max_length=30, blank=True, default="")
    # e.g. "JCI", "CBAHI", "JCI, CBAHI" or empty.
    accreditation = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city", "name_en"]
        indexes = [
            # Every tool query filters on is_active + city; ER lookup adds has_emergency.
            models.Index(fields=["is_active", "city"], name="hospital_active_city_idx"),
            models.Index(fields=["has_emergency", "city"], name="hospital_er_city_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name_en} ({self.city})"


class Doctor(models.Model):
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="doctors")
    # The M2M join table gets indexes on both FKs automatically (specialty filter).
    specialties = models.ManyToManyField(Specialty, related_name="doctors")
    languages = ArrayField(
        models.CharField(max_length=2, choices=LanguageCode.choices),
        default=list,
        help_text='Spoken languages, e.g. ["ar", "en"]',
    )
    years_experience = models.PositiveSmallIntegerField()
    offers_second_opinion = models.BooleanField(default=False)
    offers_telemedicine = models.BooleanField(default=False)
    consultation_fee_sar = models.DecimalField(max_digits=8, decimal_places=2)
    rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["name_en", "hospital"], name="doctor_unique_per_hospital"
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"], name="doctor_active_idx"),
            # GIN index makes `languages @> ARRAY['ar']` (the language filter) index-backed.
            GinIndex(fields=["languages"], name="doctor_languages_gin"),
        ]

    def __str__(self) -> str:
        return self.name_en


class AvailabilitySlot(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="slots")
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    is_booked = models.BooleanField(default=False)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(fields=["doctor", "start_time"], name="slot_unique_per_doctor"),
        ]
        indexes = [
            # "Next free slots for doctor X" = filter doctor + is_booked, order by start_time.
            models.Index(fields=["doctor", "is_booked", "start_time"], name="slot_doctor_free_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.doctor_id} @ {self.start_time:%Y-%m-%d %H:%M}"
