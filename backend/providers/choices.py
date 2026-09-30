"""Closed vocabularies shared by the database, the seed data and the LLM tool schemas.

Keeping these as enums (not free text) is the first anti-hallucination layer:
the tool JSON schemas list the allowed values, Pydantic rejects anything else, and
the model therefore cannot search for a specialty or city that does not exist.
"""

from django.db import models


class City(models.TextChoices):
    RIYADH = "RIYADH", "Riyadh"
    JEDDAH = "JEDDAH", "Jeddah"
    DAMMAM = "DAMMAM", "Dammam"
    ABHA = "ABHA", "Abha"


CITY_NAMES_AR: dict[str, str] = {
    City.RIYADH: "الرياض",
    City.JEDDAH: "جدة",
    City.DAMMAM: "الدمام",
    City.ABHA: "أبها",
}


class SpecialtyCode(models.TextChoices):
    CARDIOLOGY = "CARDIOLOGY", "Cardiology"
    EMERGENCY_MEDICINE = "EMERGENCY_MEDICINE", "Emergency Medicine"
    INTERNAL_MEDICINE = "INTERNAL_MEDICINE", "Internal Medicine"
    NEUROLOGY = "NEUROLOGY", "Neurology"
    ORTHOPEDICS = "ORTHOPEDICS", "Orthopedics"
    GASTROENTEROLOGY = "GASTROENTEROLOGY", "Gastroenterology"
    PULMONOLOGY = "PULMONOLOGY", "Pulmonology"


class LanguageCode(models.TextChoices):
    ARABIC = "ar", "Arabic"
    ENGLISH = "en", "English"
