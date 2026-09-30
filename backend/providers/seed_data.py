"""FICTIONAL provider directory used by `manage.py seed_providers`.

Every hospital, doctor, address and phone number below is invented for this
prototype. Phone numbers deliberately use the non-assigned "000" block.

Deliberate coverage gaps (used to test honest "not found" behaviour):
- ABHA has **no NEUROLOGY** (the headline test case).
- DAMMAM has no PULMONOLOGY; JEDDAH and ABHA have no GASTROENTEROLOGY.
- One doctor is inactive (on leave) to prove inactive rows are never recommended.
"""

from decimal import Decimal

from .choices import City, SpecialtyCode

SPECIALTIES: list[tuple[str, str, str]] = [
    (SpecialtyCode.CARDIOLOGY, "Cardiology", "أمراض القلب"),
    (SpecialtyCode.EMERGENCY_MEDICINE, "Emergency Medicine", "طب الطوارئ"),
    (SpecialtyCode.INTERNAL_MEDICINE, "Internal Medicine", "الطب الباطني"),
    (SpecialtyCode.NEUROLOGY, "Neurology", "الأمراض العصبية"),
    (SpecialtyCode.ORTHOPEDICS, "Orthopedics", "جراحة العظام"),
    (SpecialtyCode.GASTROENTEROLOGY, "Gastroenterology", "أمراض الجهاز الهضمي"),
    (SpecialtyCode.PULMONOLOGY, "Pulmonology", "أمراض الرئة"),
]

# key -> hospital fields. `key` is only used to link doctors below.
HOSPITALS: dict[str, dict] = {
    "RUH_A": {
        "name_en": "Al-Wahah Medical City",
        "name_ar": "مدينة الواحة الطبية",
        "city": City.RIYADH,
        "address_en": "King Fahd Road, Al Olaya, Riyadh (fictional)",
        "address_ar": "طريق الملك فهد، العليا، الرياض (عنوان افتراضي)",
        "has_emergency": True,
        "emergency_phone": "+966 11 000 0101",
        "accreditation": "JCI",
    },
    "RUH_B": {
        "name_en": "Riyadh Crescent Specialist Clinics",
        "name_ar": "عيادات الهلال التخصصية بالرياض",
        "city": City.RIYADH,
        "address_en": "Takhassusi Street, Riyadh (fictional)",
        "address_ar": "شارع التخصصي، الرياض (عنوان افتراضي)",
        "has_emergency": False,
        "emergency_phone": "",
        "accreditation": "CBAHI",
    },
    "JED_A": {
        "name_en": "Red Sea Care Hospital",
        "name_ar": "مستشفى رعاية البحر الأحمر",
        "city": City.JEDDAH,
        "address_en": "Prince Sultan Road, Jeddah (fictional)",
        "address_ar": "طريق الأمير سلطان، جدة (عنوان افتراضي)",
        "has_emergency": True,
        "emergency_phone": "+966 12 000 0202",
        "accreditation": "JCI, CBAHI",
    },
    "JED_B": {
        "name_en": "Al-Balad Family Clinics",
        "name_ar": "عيادات البلد العائلية",
        "city": City.JEDDAH,
        "address_en": "Al-Balad District, Jeddah (fictional)",
        "address_ar": "حي البلد، جدة (عنوان افتراضي)",
        "has_emergency": False,
        "emergency_phone": "",
        "accreditation": "",
    },
    "DMM_A": {
        "name_en": "Eastern Gulf Hospital",
        "name_ar": "مستشفى الخليج الشرقي",
        "city": City.DAMMAM,
        "address_en": "King Saud Street, Dammam (fictional)",
        "address_ar": "شارع الملك سعود، الدمام (عنوان افتراضي)",
        "has_emergency": True,
        "emergency_phone": "+966 13 000 0303",
        "accreditation": "CBAHI",
    },
    "DMM_B": {
        "name_en": "Corniche Specialty Center",
        "name_ar": "مركز الكورنيش التخصصي",
        "city": City.DAMMAM,
        "address_en": "Corniche Road, Dammam (fictional)",
        "address_ar": "طريق الكورنيش، الدمام (عنوان افتراضي)",
        "has_emergency": False,
        "emergency_phone": "",
        "accreditation": "CBAHI",
    },
    "AHB_A": {
        "name_en": "Asir Highlands Hospital",
        "name_ar": "مستشفى مرتفعات عسير",
        "city": City.ABHA,
        "address_en": "King Khalid Road, Abha (fictional)",
        "address_ar": "طريق الملك خالد، أبها (عنوان افتراضي)",
        "has_emergency": True,
        "emergency_phone": "+966 17 000 0404",
        "accreditation": "CBAHI",
    },
    "AHB_B": {
        "name_en": "Abha Mountain Clinic",
        "name_ar": "عيادة جبل أبها",
        "city": City.ABHA,
        "address_en": "Al-Soudah Road, Abha (fictional)",
        "address_ar": "طريق السودة، أبها (عنوان افتراضي)",
        "has_emergency": False,
        "emergency_phone": "",
        "accreditation": "",
    },
}

# Short aliases keep the doctor table below readable as a table.
CARD, ER_MED, INT_MED, NEURO, ORTHO, GASTRO, PULM = (
    SpecialtyCode.CARDIOLOGY,
    SpecialtyCode.EMERGENCY_MEDICINE,
    SpecialtyCode.INTERNAL_MEDICINE,
    SpecialtyCode.NEUROLOGY,
    SpecialtyCode.ORTHOPEDICS,
    SpecialtyCode.GASTROENTEROLOGY,
    SpecialtyCode.PULMONOLOGY,
)
AR, EN, BOTH = ["ar"], ["en"], ["ar", "en"]

# (name_en, name_ar, hospital_key, specialties, languages, years, second_opinion,
#  telemedicine, fee_sar, rating, is_active)
# fmt: off
DOCTORS: list[tuple] = [
    # --- Riyadh ---
    ("Dr. Faisal Al-Harbi", "د. فيصل الحربي", "RUH_A", [CARD], BOTH, 18, True, True, "450", "4.8", True),
    ("Dr. Noura Al-Qahtani", "د. نورة القحطاني", "RUH_B", [CARD], AR, 11, False, True, "350", "4.6", True),
    ("Dr. James Whitfield", "د. جيمس ويتفيلد", "RUH_A", [CARD], EN, 22, True, False, "600", "4.7", True),
    ("Dr. Khalid Al-Otaibi", "د. خالد العتيبي", "RUH_A", [ER_MED], BOTH, 9, False, False, "300", "4.5", True),
    ("Dr. Reem Al-Shehri", "د. ريم الشهري", "RUH_B", [INT_MED], BOTH, 7, False, True, "250", "4.5", True),
    ("Dr. Omar Al-Dosari", "د. عمر الدوسري", "RUH_A", [NEURO], BOTH, 14, True, False, "500", "4.7", True),
    ("Dr. Lina Haddad", "د. لينا حداد", "RUH_B", [PULM], BOTH, 10, False, True, "400", "4.4", True),
    ("Dr. Sultan Al-Mutairi", "د. سلطان المطيري", "RUH_A", [ORTHO], AR, 16, True, False, "450", "4.6", True),
    ("Dr. Hana Al-Zahrani", "د. هناء الزهراني", "RUH_B", [GASTRO], BOTH, 12, False, True, "400", "4.5", True),
    # Inactive on purpose: must never be returned by tools or accepted by grounding.
    ("Dr. Rami Al-Faraj", "د. رامي الفرج", "RUH_A", [CARD], BOTH, 25, True, True, "700", "4.9", False),
    # --- Jeddah ---
    ("Dr. Ahmed Bakr", "د. أحمد بكر", "JED_A", [CARD], BOTH, 20, True, True, "500", "4.9", True),
    ("Dr. Maryam Al-Ghamdi", "د. مريم الغامدي", "JED_B", [CARD, INT_MED], AR, 8, False, False, "300", "4.3", True),
    ("Dr. Yousef Al-Amoudi", "د. يوسف العمودي", "JED_A", [ER_MED], BOTH, 11, False, False, "300", "4.6", True),
    ("Dr. Priya Raman", "د. بريا رامان", "JED_B", [INT_MED], EN, 9, False, True, "280", "4.4", True),
    ("Dr. Tariq Al-Juhani", "د. طارق الجهني", "JED_A", [NEURO], AR, 17, True, True, "520", "4.8", True),
    ("Dr. Salma Barakat", "د. سلمى بركات", "JED_A", [PULM], BOTH, 6, False, False, "350", "4.2", True),
    ("Dr. Waleed Al-Harthi", "د. وليد الحارثي", "JED_B", [ORTHO], BOTH, 13, False, False, "400", "4.5", True),
    # --- Dammam ---
    ("Dr. Abdullah Al-Shammari", "د. عبدالله الشمري", "DMM_A", [CARD], BOTH, 15, True, False, "420", "4.7", True),
    ("Dr. Fatimah Al-Nasser", "د. فاطمة الناصر", "DMM_B", [INT_MED], AR, 10, False, True, "260", "4.5", True),
    ("Dr. Hassan Al-Ali", "د. حسن العلي", "DMM_A", [ER_MED], BOTH, 8, False, False, "300", "4.4", True),
    ("Dr. Daniel Okafor", "د. دانيال أوكافور", "DMM_B", [NEURO], EN, 19, True, True, "550", "4.6", True),
    ("Dr. Mona Al-Khaldi", "د. منى الخالدي", "DMM_A", [GASTRO], BOTH, 11, True, False, "430", "4.6", True),
    ("Dr. Bader Al-Subaie", "د. بدر السبيعي", "DMM_B", [ORTHO], AR, 9, False, False, "380", "4.3", True),
    # --- Abha (no NEUROLOGY on purpose) ---
    ("Dr. Saeed Al-Asmari", "د. سعيد الأسمري", "AHB_A", [CARD], AR, 12, False, True, "380", "4.5", True),
    ("Dr. Nada Al-Qarni", "د. ندى القرني", "AHB_B", [INT_MED], BOTH, 6, False, True, "220", "4.4", True),
    ("Dr. Ibrahim Al-Shahrani", "د. إبراهيم الشهراني", "AHB_A", [ER_MED], AR, 10, False, False, "300", "4.5", True),
    ("Dr. Aisha Al-Malki", "د. عائشة المالكي", "AHB_A", [PULM], BOTH, 9, False, False, "330", "4.3", True),
    ("Dr. Majed Al-Ghamdi", "د. ماجد الغامدي", "AHB_B", [ORTHO], AR, 14, False, False, "360", "4.4", True),
]
# fmt: on


def doctor_rows() -> list[dict]:
    """Expand the compact DOCTORS tuples into dicts (keeps the table above readable)."""
    rows = []
    for (
        name_en,
        name_ar,
        hospital_key,
        specialties,
        languages,
        years,
        second_opinion,
        telemedicine,
        fee,
        rating,
        is_active,
    ) in DOCTORS:
        rows.append(
            {
                "name_en": name_en,
                "name_ar": name_ar,
                "hospital_key": hospital_key,
                "specialties": [str(s) for s in specialties],
                "languages": list(languages),
                "years_experience": years,
                "offers_second_opinion": second_opinion,
                "offers_telemedicine": telemedicine,
                "consultation_fee_sar": Decimal(fee),
                "rating": Decimal(rating),
                "is_active": is_active,
            }
        )
    return rows
