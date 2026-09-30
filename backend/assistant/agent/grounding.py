"""Grounding Validator: the model's claims about providers must be backed by the DB.

Checks, in order:
1. Every recommended_provider_id must (a) exist, (b) be active, and (c) have been
   returned by a successful `search_providers` call IN THIS SESSION (see ADR-006).
   Anything else is dropped and recorded as a violation.
2. reply_text is scanned for doctor/hospital names from the directory that were NOT
   returned to this session, and for "Dr. X" / "د. X" patterns that match no returned
   provider. These are stripped and recorded.

The API then renders provider cards from the DB rows of the *kept* IDs only, so
even a fully fabricated reply cannot put an unverified provider card on screen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from assistant.models import ChatSession, ToolCallLog
from assistant.tools.registry import SEARCH_TOOL
from providers.models import Doctor, Hospital

REMOVED_MARKER = {"en": "[unverified name removed]", "ar": "[تم حذف اسم غير موثّق]"}

# "Dr. Ahmed Al-Harbi", "Doctor John Smith": title + 1-3 capitalized name tokens.
_EN_DOCTOR_PATTERN = re.compile(
    r"\b(?:Dr\.?|Doctor)\s+((?:[A-Z][\w'-]+)(?:\s+(?:al-|Al-|bin |Bin |ibn )?[A-Z][\w'-]+){0,3})"
)
# "د. أحمد الحربي": the Arabic title abbreviation followed by up to 3 words.
_AR_DOCTOR_PATTERN = re.compile(r"(?:^|\s)د\s?\.\s?((?:[ء-ي]+\s?){1,3})")


@dataclass
class GroundingResult:
    kept_provider_ids: list[int]
    reply_text: str
    violations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def all_recommendations_dropped(self) -> bool:
        return not self.kept_provider_ids and any(
            v["type"] in {"unknown_provider_id", "provider_not_from_session_search"}
            for v in self.violations
        )


def session_search_ids(session: ChatSession) -> set[int]:
    """Doctor ids returned by successful search_providers calls in this session."""
    ids: set[int] = set()
    for result_ids in ToolCallLog.objects.filter(
        session=session, tool_name=SEARCH_TOOL, success=True
    ).values_list("result_ids", flat=True):
        ids.update(int(i) for i in result_ids)
    return ids


def session_hospital_ids(session: ChatSession) -> set[int]:
    ids: set[int] = set()
    for result_ids in ToolCallLog.objects.filter(session=session, success=True).values_list(
        "result_hospital_ids", flat=True
    ):
        ids.update(int(i) for i in result_ids)
    return ids


def _check_ids(recommended: list[int], allowed: set[int]) -> tuple[list[int], list[dict[str, Any]]]:
    active = set(
        Doctor.objects.filter(
            pk__in=recommended, is_active=True, hospital__is_active=True
        ).values_list("pk", flat=True)
    )
    kept, violations = [], []
    for provider_id in recommended:
        if provider_id not in active:
            violations.append({"type": "unknown_provider_id", "provider_id": provider_id})
        elif provider_id not in allowed:
            violations.append(
                {"type": "provider_not_from_session_search", "provider_id": provider_id}
            )
        else:
            kept.append(provider_id)
    return kept, violations


def _name_variants(name: str) -> set[str]:
    """'Dr. Faisal Al-Harbi' -> {'dr. faisal al-harbi', 'faisal al-harbi'} (+ Arabic w/o 'د.')."""
    lowered = name.lower().strip()
    variants = {lowered}
    for prefix in ("dr. ", "dr ", "د. ", "د."):
        if lowered.startswith(prefix):
            variants.add(lowered[len(prefix) :].strip())
    return {v for v in variants if len(v) >= 4}


def _strip(text: str, needle: str, marker: str) -> str:
    return re.sub(re.escape(needle), marker, text, flags=re.IGNORECASE)


def _check_names(
    reply_text: str,
    allowed_doctor_ids: set[int],
    allowed_hospital_ids: set[int],
    language: str,
) -> tuple[str, list[dict[str, Any]]]:
    marker = REMOVED_MARKER.get(language, REMOVED_MARKER["en"])
    violations: list[dict[str, Any]] = []
    allowed_names: set[str] = set()
    text = reply_text

    # 1. Known directory names that this session never received.
    for doctor in Doctor.objects.only("pk", "name_en", "name_ar"):
        variants = _name_variants(doctor.name_en) | _name_variants(doctor.name_ar)
        if doctor.pk in allowed_doctor_ids:
            allowed_names |= variants
            continue
        for variant in sorted(variants, key=len, reverse=True):
            if variant in text.lower():
                violations.append({"type": "unverified_doctor_name", "provider_id": doctor.pk})
                text = _strip(text, variant, marker)
                break
    for hospital in Hospital.objects.only("pk", "name_en", "name_ar"):
        names = {hospital.name_en.lower(), hospital.name_ar}
        if hospital.pk in allowed_hospital_ids:
            allowed_names |= names
            continue
        for name in names:
            if name.lower() in text.lower():
                violations.append({"type": "unverified_hospital_name", "hospital_id": hospital.pk})
                text = _strip(text, name, marker)
                break

    # 2. "Dr. X" patterns that match no provider returned to this session (invented names).
    for pattern in (_EN_DOCTOR_PATTERN, _AR_DOCTOR_PATTERN):
        for match in list(pattern.finditer(text)):
            candidate = match.group(1).strip().lower()
            if any(candidate in name or name in candidate for name in allowed_names):
                continue
            violations.append({"type": "fabricated_doctor_name", "text": match.group(0).strip()})
            text = text.replace(match.group(0).strip(), marker)
    return text, violations


def validate(
    *,
    session: ChatSession,
    recommended_provider_ids: list[int],
    reply_text: str,
    language: str,
) -> GroundingResult:
    allowed_ids = session_search_ids(session)
    kept, violations = _check_ids(recommended_provider_ids, allowed_ids)
    text, name_violations = _check_names(
        reply_text, allowed_ids, session_hospital_ids(session), language
    )
    return GroundingResult(
        kept_provider_ids=kept, reply_text=text, violations=violations + name_violations
    )
