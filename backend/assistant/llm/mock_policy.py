"""Heuristic stand-in for the LLM when LLM_PROVIDER=mock (offline demo, no API key).

This is NOT the product's intelligence. It is a keyword-driven script that speaks
the same protocol as Claude (tool calls + submit_response), so the full pipeline
(tools, grounding, stages, UI) can be demoed and tested without network access.
The trace panel labels these turns as `llm_provider: mock`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .client import LLMResponse, tool_use

_SPECIALTY_KEYWORDS: list[tuple[str, str]] = [
    ("CARDIOLOGY", r"chest|heart|cardio|palpitation|صدر|قلب|خفقان"),
    ("NEUROLOGY", r"headache|migraine|neuro|numb|seizure|صداع|اعصاب|أعصاب|تنميل|صرع"),
    ("ORTHOPEDICS", r"knee|bone|joint|back pain|fracture|ركبه|ركبة|عظام|مفصل|ظهر|كسر"),
    ("GASTROENTEROLOGY", r"stomach|abdomen|abdominal|bowel|reflux|بطن|معده|معدة|قولون|حموضه|حموضة"),
    ("PULMONOLOGY", r"cough|lung|asthma|wheez|كحه|كحة|سعال|رئه|رئة|ربو"),
]
_CITIES = {
    "RIYADH": r"riyadh|الرياض",
    "JEDDAH": r"jeddah|jedda|جده|جدة",
    "DAMMAM": r"dammam|الدمام",
    "ABHA": r"abha|ابها|أبها",
}
_SECOND_OPINION = (
    r"second opinion|another opinion|already diagnosed|diagnosis|رأي ثاني|رأي آخر|راي ثاني|تشخيص"
)
# "I'm not sure whether ... or a second opinion" is indecision, not a stated goal.
_UNSURE = r"not sure|unsure|whether|don'?t know|مو متأكد|مش متأكد|غير متأكد|ما أدري|لا أعرف"

_QUESTIONS = {
    "en": [
        ("When did the pain start, and does it come and go or is it constant?",
         ["It started today and comes and goes", "It has been constant for hours", "It started weeks ago"]),
        ("Does the pain spread to your arm, jaw, neck or back?",
         ["Yes, it spreads to my arm or jaw", "No, it stays in my chest"]),
        ("Do you have shortness of breath, sweating, nausea or dizziness?",
         ["Yes, I am short of breath", "Yes, I am sweating or nauseous", "No, none of these"]),
    ],
    "ar": [
        ("متى بدأ الألم؟ وهل هو مستمر أم يأتي ويذهب؟",
         ["بدأ اليوم ويأتي ويذهب", "مستمر منذ ساعات", "بدأ قبل أسابيع"]),
        ("هل ينتشر الألم إلى الذراع أو الفك أو الرقبة أو الظهر؟",
         ["نعم، ينتشر إلى الذراع أو الفك", "لا، يبقى في الصدر فقط"]),
        ("هل لديك ضيق في التنفس أو تعرق أو غثيان أو دوخة؟",
         ["نعم، عندي ضيق في التنفس", "نعم، عندي تعرق أو غثيان", "لا، لا شيء من ذلك"]),
    ],
}  # fmt: skip

_REPLIES = {
    "questions": {
        "en": "I'm sorry you're dealing with this. To point you to the right next step, I need a few details.",
        "ar": "أنا آسف لما تمر به. حتى أوجهك للخطوة المناسبة، أحتاج بعض التفاصيل.",
    },
    "found": {
        "en": "Based on what you told me, a specialist visit is a sensible next step. Here are verified options from our directory. If your symptoms get worse, call 997.",
        "ar": "بناءً على ما ذكرته، زيارة طبيب مختص خطوة مناسبة. هذه خيارات موثّقة من دليلنا. إذا ساءت الأعراض فاتصل على 997.",
    },
    "alternatives": {
        "en": "There is no matching specialist in your city in our directory. These are the closest verified options in other cities.",
        "ar": "لا يوجد طبيب مطابق في مدينتك ضمن دليلنا. هذه أقرب الخيارات الموثّقة في مدن أخرى.",
    },
    "none": {
        "en": "I couldn't find a matching provider in our directory for this request.",
        "ar": "لم أجد مقدم خدمة مطابقًا في دليلنا لهذا الطلب.",
    },
}  # fmt: skip


def _current_turn(messages: list[dict[str, Any]]) -> tuple[dict[str, Any], str, list[dict]]:
    """Return (session_context, patient_text, tool_outputs seen after the new user turn)."""
    turn_index = max(
        i
        for i, m in enumerate(messages)
        if m["role"] == "user"
        and isinstance(m["content"], str)
        and "<session_context>" in m["content"]
    )
    content = messages[turn_index]["content"]
    context = json.loads(content.split("<session_context>")[1].split("</session_context>")[0])
    patient_text = content.rsplit("<patient_message>", 1)[1].split("</patient_message>")[0].strip()
    outputs = []
    for message in messages[turn_index + 1 :]:
        if message["role"] == "user" and isinstance(message["content"], list):
            for block in message["content"]:
                if block.get("type") == "tool_result" and not block.get("is_error"):
                    outputs.append(json.loads(block["content"]))
    return context, patient_text, outputs


def _match(patterns: str, text: str) -> bool:
    return re.search(patterns, text, re.IGNORECASE) is not None


def demo_policy(messages: list[dict[str, Any]]) -> LLMResponse:
    context, text, outputs = _current_turn(messages)
    lang = context["session_language"]
    facts = context["known_facts"]
    all_text = f"{facts.get('chief_complaint', '')} {text}"
    city = next((c for c, p in _CITIES.items() if _match(p, text)), facts.get("city"))
    specialty = next(
        (s for s, p in _SPECIALTY_KEYWORDS if _match(p, all_text)), "INTERNAL_MEDICINE"
    )
    wants_second_opinion = _match(_SECOND_OPINION, text) and not _match(_UNSURE, text)
    second_opinion = wants_second_opinion or facts.get("patient_goal") == "SECOND_OPINION"
    updates: dict[str, Any] = {"preferred_language": lang}
    if not facts.get("chief_complaint"):
        updates["chief_complaint"] = text[:150]
    if city:
        updates["city"] = city
    if second_opinion:
        updates.update(patient_goal="SECOND_OPINION", has_existing_diagnosis=True)

    searches = [o for o in outputs if "results" in o]
    if searches:
        last = searches[-1]
        ids = [r["provider_id"] for r in last["results"]] or [
            r["provider_id"] for r in last["nearby_alternatives"]
        ]
        key = "found" if last["results"] else ("alternatives" if ids else "none")
        return _submit(
            lang, _REPLIES[key][lang], "URGENT" if specialty == "CARDIOLOGY" else "ROUTINE",
            "SECOND_OPINION" if second_opinion else "SEE_SPECIALIST", ids[:3], updates,
            f"Mock policy: searched {specialty}" + (f" in {city}" if city else ""),
        )  # fmt: skip

    needs_questions = (
        specialty == "CARDIOLOGY" and not second_opinion and context["can_ask_more_questions"]
        and context["clarification_rounds_used"] == 0
    )  # fmt: skip
    if needs_questions:
        questions = [{"question": q, "quick_replies": r} for q, r in _QUESTIONS[lang]]
        return _submit(
            lang, _REPLIES["questions"][lang], "URGENT", "NEED_MORE_INFO", [], updates,
            "Mock policy: chest pain needs red-flag screening questions first.", questions,
        )  # fmt: skip

    args: dict[str, Any] = {"specialty": specialty, "limit": 3}
    if city:
        args["city"] = city
    if second_opinion:
        args["second_opinion"] = True
    if lang == "ar":
        args["language"] = "ar"
    return tool_use("search_providers", args)


def _submit(
    lang, reply, urgency, next_step, ids, updates, reasoning, questions=None
) -> LLMResponse:
    return tool_use(
        "submit_response",
        {
            "reply_text": reply,
            "urgency": urgency,
            "next_step": next_step,
            "clarifying_questions": questions or [],
            "recommended_provider_ids": ids,
            "state_updates": updates,
            "reasoning_summary": reasoning,
        },
    )
