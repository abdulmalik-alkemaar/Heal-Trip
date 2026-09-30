"""Red-Flag Engine tests: English + Arabic, combinations, negation, false-positive guards."""

import pytest

from assistant.enums import Urgency, max_urgency
from assistant.safety.red_flags import detect_concepts, evaluate, normalize

EMERGENCY_PHRASES = [
    # Chest pain + companion symptom (EN)
    "I have chest pain and shortness of breath",
    "Crushing chest pressure that is spreading to my left arm",
    "chest tightness and I'm sweating a lot",
    "My chest hurts and I feel nauseous",
    "pain in my chest, and I feel dizzy",
    "Chest pain radiating to my jaw",
    "chest discomfort, cold sweat",
    "Chest pain and I fainted earlier",
    # Standalone emergencies (EN)
    "My father's face is drooping and his speech is slurred",
    "sudden weakness on one side of my body",
    "I suddenly have the worst headache of my life",
    "sudden severe headache out of nowhere",
    "I can't breathe",
    "She is unconscious and not responding",
    "He collapsed at home",
    "There is heavy bleeding that won't stop",
    "I've been vomiting blood",
    "I want to kill myself",
    # Chest pain + companion symptom (AR, several spellings/dialects)
    "عندي ألم في الصدر وضيق في التنفس",
    "ألم بالصدر ينتشر للذراع اليسرى",
    "الم في صدري مع تعرق",
    "صدري يوجعني وعندي غثيان",
    "وجع في الصدر ودوخة",
    "ألم في الصدر وإغماء",
    "ضغط على الصدر يمتد إلى الفك",
    "صدري يعورني ونفسي ضايق",
    # Standalone emergencies (AR)
    "أبوي عنده ميلان في الوجه وثقل في الكلام",
    "ضعف في جهة واحدة من الجسم",
    "صداع شديد مفاجئ",
    "ما اقدر اتنفس",
    "فقد الوعي فجأة",
    "نزيف شديد ما يوقف",
    "أفكر في الانتحار",
    # With diacritics and tatweel (normalization)
    "أَلَمٌ فِي الصَّدْرِ وَضِيقٌ فِي التَّنَفُّس",
    "ألـــم في الصدر وتعرّق",
]

URGENT_PHRASES = [
    # The exact example from the brief: chest pain alone -> URGENT (not emergency) pending questions.
    "I have chest pain and I'm not sure whether I should see a cardiologist, go to the ER, "
    "or seek a second opinion.",
    "mild chest pain when I press on my chest for 2 weeks",
    "I get short of breath when climbing stairs",
    "I feel dizzy sometimes",
    "عندي ألم في الصدر ومو متأكد هل أروح طوارئ أو أشوف دكتور قلب",
    "أحس بضيق في التنفس لما أمشي",
]

NO_FLAG_PHRASES = [
    "I have knee pain after football",
    "I need a second opinion about my MRI",
    "my stomach hurts after eating",
    "عندي ألم في الركبة",
    "أبغى رأي ثاني عن التشخيص",
    # False-positive guards
    "I'm going back to work tomorrow",  # "going back" is not radiating pain
    "I can't speak Arabic very well",  # not a stroke sign
    "there is a faint ache in my knee",  # "faint" != fainting
    "باقي لي أسبوع على الموعد",  # contains "قي" inside a word
    "I have a severe headache from stress",  # severe but not sudden -> no emergency rule
]

NEGATED_PHRASES = [
    "no chest pain",
    "I don't have chest pain",
    "I do not have any chest pain or shortness of breath",
    "without chest pain",
    "never had chest pain",
    "ما عندي ألم في الصدر",
    "لا يوجد ألم في الصدر",
    "بدون ألم في الصدر",
    "مافي ضيق في التنفس",
]


@pytest.mark.parametrize("text", EMERGENCY_PHRASES)
def test_emergency_phrases(text):
    result = evaluate([text])
    assert result.level == Urgency.EMERGENCY, (text, result)
    assert result.matched_flags


@pytest.mark.parametrize("text", URGENT_PHRASES)
def test_urgent_phrases(text):
    assert evaluate([text]).level == Urgency.URGENT, text


@pytest.mark.parametrize("text", NO_FLAG_PHRASES)
def test_no_flag_phrases(text):
    result = evaluate([text])
    assert result.level == Urgency.UNKNOWN, (text, result)


@pytest.mark.parametrize("text", NEGATED_PHRASES)
def test_negation_suppresses_flag(text):
    assert detect_concepts(text) == set(), text


def test_negation_does_not_leak_across_clauses():
    assert "CHEST_PAIN" in detect_concepts("No fever, but I have chest pain")
    assert "CHEST_PAIN" in detect_concepts("I don't sleep well and I have chest pain")
    assert "CHEST_PAIN" in detect_concepts("ما نمت زين وعندي ألم في الصدر")


def test_uncertainty_is_not_negation():
    assert "CHEST_PAIN" in detect_concepts("I'm not sure if this is chest pain or heartburn")


def test_concepts_combine_across_turns():
    """Chest pain in turn 1 + sweating in turn 2 = emergency."""
    assert evaluate(["I have chest pain"]).level == Urgency.URGENT
    result = evaluate(["I have chest pain", "yes, I'm also sweating"])
    assert result.level == Urgency.EMERGENCY
    assert "CHEST_PAIN_WITH_SWEATING" in result.matched_flags


def test_structured_state_is_evaluated():
    """A 'yes' captured as a slot (not in free text) still escalates."""
    state = {"chief_complaint": "chest pain", "radiating_pain": True}
    result = evaluate([], state)
    assert result.level == Urgency.EMERGENCY
    assert "CHEST_PAIN_WITH_RADIATING_PAIN" in result.matched_flags


def test_state_false_slots_do_not_escalate():
    state = {"chief_complaint": "chest pain", "shortness_of_breath": False, "radiating_pain": False}
    assert evaluate([], state).level == Urgency.URGENT


def test_severe_chest_pain_score_escalates():
    assert evaluate([], {"chief_complaint": "chest pain", "severity_1_10": 9}).level == (
        Urgency.EMERGENCY
    )
    assert evaluate([], {"chief_complaint": "chest pain", "severity_1_10": 4}).level == (
        Urgency.URGENT
    )


def test_arabic_normalization():
    assert normalize("أَلَمٌ") == "الم"
    assert normalize("إغماء") == "اغماء"
    assert normalize("دوخة") == "دوخه"
    assert normalize("ألـــم") == "الم"


def test_rules_never_claim_routine():
    """No match means 'no opinion' (UNKNOWN), never ROUTINE."""
    assert evaluate(["hello"]).level == Urgency.UNKNOWN


class TestMaxUrgency:
    def test_llm_can_escalate(self):
        assert max_urgency(Urgency.URGENT, Urgency.EMERGENCY) == Urgency.EMERGENCY

    def test_llm_cannot_downgrade(self):
        assert max_urgency(Urgency.EMERGENCY, Urgency.ROUTINE) == Urgency.EMERGENCY
        assert max_urgency(Urgency.URGENT, Urgency.ROUTINE) == Urgency.URGENT

    def test_unknown_and_none_are_ignored(self):
        assert max_urgency(Urgency.UNKNOWN, Urgency.ROUTINE) == Urgency.ROUTINE
        assert max_urgency(None, "garbage") == Urgency.UNKNOWN
