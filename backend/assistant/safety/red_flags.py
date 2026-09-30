"""Deterministic Red-Flag Engine (English + Arabic). Pure Python - no LLM, no DB.

Why this exists: emergency triage is too important to depend on a probabilistic
model being up, fast, and correct. These rules run BEFORE the LLM (so an emergency
is answered instantly, even when the LLM is down) and AGAIN after it on the merged
structured state (so "yes" answers captured as slots are also caught).

Design:
1. `normalize()` lowercases and folds Arabic spelling variants (hamza forms,
   taa marbuta, alef maqsura, diacritics, tatweel) so one pattern matches many spellings.
2. Text is split into clauses (".", ",", "but", "لكن", ...). Each *concept* pattern
   (chest pain, shortness of breath, ...) is matched per clause.
3. A match is discarded if a negation cue ("no", "without", "لا", "بدون", ...) appears
   in the few words before it in the same clause ("no chest pain" does not trigger).
4. Rules combine concepts: chest pain + (breathlessness | radiation | sweating |
   nausea | fainting) => EMERGENCY; chest pain alone => URGENT; etc.

Levels: the engine only ever *escalates*. When nothing matches it returns UNKNOWN
("no rule opinion"), never ROUTINE - declaring something routine is a judgement the
rules are not qualified to make. Final urgency = max(rules, llm) (see enums.max_urgency).

Known limitations (documented in docs/AGENT_DESIGN.md):
- Keyword/regex based: misses paraphrases it has no pattern for, and dialect coverage
  is partial (Gulf/Hijazi/MSA phrases are covered; others may not be).
- Negation is a fixed look-back window; long-range negation ("I have had, for years,
  never once any chest pain") or double negatives may be misread. We bias toward
  triggering: uncertainty phrases like "not sure" are NOT treated as negation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from assistant.enums import Urgency

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
_AR_DIACRITICS = re.compile(r"[ً-ٰٟ]")  # harakat, shadda, sukun, dagger alef
_AR_TATWEEL = "ـ"
_AR_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "،": ",",  # Arabic comma
        "؛": ";",  # Arabic semicolon
        "؟": "?",  # Arabic question mark
        "’": "'",
    }
)


def _fold_arabic(text: str) -> str:
    return _AR_DIACRITICS.sub("", text.translate(_AR_FOLD)).replace(_AR_TATWEEL, "")


def normalize(text: str) -> str:
    """Lowercase + fold Arabic orthographic variants + collapse whitespace."""
    return re.sub(r"\s+", " ", _fold_arabic(text.lower())).strip()


# Uncertainty phrases contain negation words but are NOT negations of a symptom
# ("I'm not sure if it's chest pain" must still count as chest pain).
_UNCERTAINTY = re.compile(
    r"not sure|not certain|don'?t know|do not know|unsure|"
    r"مو متاكد|مش متاكد|لست متاكد|غير متاكد|ما اعرف|مدري|ما ادري"
)

# Clause boundaries: negation does not carry across these.
_CLAUSE_SPLIT = re.compile(r"[.!?;,\n]| but | however | although | لكن | بس | ولكن ")

_NEGATION_CUES = {
    # English
    "no",
    "not",
    "never",
    "without",
    "don't",
    "dont",
    "doesn't",
    "doesnt",
    "didn't",
    "didnt",
    "haven't",
    "havent",
    "hasn't",
    "isn't",
    "aren't",
    "deny",
    "denies",
    "nor",
    # Arabic (normalized forms)
    "لا",
    "ما",
    "مو",
    "مش",
    "ماني",
    "مافي",
    "ليس",
    "ليست",
    "لست",
    "لم",
    "بدون",
    "بلا",
    "غير",
    "ولا",
}
_NEGATION_WINDOW_WORDS = 4
_LIST_JOINERS = {"or", "nor", "او"}
# Words that start a new conjunct: a negation before them does not reach past them.
# ("I can't sleep and I have chest pain" -> chest pain is NOT negated.)
# Note "or" is deliberately absent: "no chest pain or sweating" negates both.
_CONJUNCTION_STOPS = {
    "and",
    "also",
    "plus",
    "with",
    "then",
    "و",
    "وعندي",
    "وفي",
    "وفيه",
    "وكمان",
    "كمان",
    "ايضا",
    "مع",
}

# ---------------------------------------------------------------------------
# Concepts: each is a list of regexes over *normalized* text.
# Arabic patterns avoid \b because words take attached prefixes (و, ب, ف, ال).
# ---------------------------------------------------------------------------
# Clauses are space-padded, so (?<=\s) is a word start; و/ف/ب may be attached.
_AR_PREFIX = r"(?<=\s)(?:و|ف|ب)?"

CONCEPTS: dict[str, list[str]] = {
    "CHEST_PAIN": [
        r"\bchest (?:pain|pains|pressure|tightness|heaviness|discomfort|ache|hurts?|is tight)",
        r"\b(?:pain|pressure|tightness|heaviness|discomfort|ache) (?:in|on|across) (?:my |the )?chest",
        r"\b(?:my )?chest (?:is )?(?:hurting|hurts|feels tight|feels heavy)",
        r"\b(?:tight|heavy|crushing|painful) chest",
        r"\bheart (?:pain|hurts)|\bmy heart (?:hurts|is hurting)",
        # Arabic: الم/وجع/ضغط/ثقل/ضيق في الصدر / بالصدر / صدري
        # Up to 2 words may sit between the noun and "chest" ("ألم شديد جدا في الصدر").
        _AR_PREFIX + r"(?:الم|الام|اوجاع|وجع|ضغط|ثقل|ضيق|انقباض|نغزه|نغزات|كتمه)"
        r"(?:\s+\S+){0,2}?\s+(?:في\s+|على\s+)?(?:ب?ال)?صدر",
        r"صدري\s+(?:يوجعني|يولمني|يالمني|يعورني|ضايق|مضغوط|ثقيل)",
        r"(?:يوجعني|يولمني|يعورني)\s+صدري",
        _AR_PREFIX + r"(?:الم|وجع)\s+(?:في\s+)?(?:ب?ال)?قلب",
    ],
    "SHORTNESS_OF_BREATH": [
        r"\bshort(?:ness)? of breath",
        r"\bbreathless",
        r"\bout of breath",
        r"\b(?:difficulty|trouble|problems?|struggling|hard time) (?:with )?breathing",
        r"\bhard to breathe",
        r"\bcan'?t (?:catch my )?breath",
        _AR_PREFIX + r"(?:ضيق|صعوبه|ضيقه)\s+(?:في\s+)?(?:ال)?(?:تنفس|نفس)",
        r"نفسي\s+(?:ضايق|مقطوع|قصير)",
        r"(?:ضايق|ضاق)\s+نفسي",
    ],
    # Severe breathing difficulty is an emergency on its own.
    "SEVERE_BREATHING": [
        r"\b(?:can'?t|cannot|unable to|can not) breathe",
        r"\bgasping",
        r"\bchoking",
        r"\b(?:lips|face) (?:are |is |turning )?blue",
        r"\bsevere(?:ly)? (?:short(?:ness)? of breath|difficulty breathing|breathless)",
        r"(?:ما\s*اقدر|مو قادر|مش قادر|لا\s*اقدر|لا\s*استطيع)\s+(?:على\s+)?(?:ا|ال)?تنفس",
        _AR_PREFIX + r"اختناق|اختنق",
        _AR_PREFIX + r"(?:ضيق|صعوبه)\s+(?:شديد|شديده)\s+(?:في\s+)?(?:ال)?تنفس",
        r"ازرقاق",
    ],
    "RADIATING_PAIN": [
        # The preposition is required so "going back to work" is not "radiating to the back".
        r"\b(?:spread\w*|radiat\w*|going|goes|moving|moves|shoot\w*|travel\w*) "
        r"(?:(?:down|up|out) )?(?:to|into|through|down|up|in) (?:my |the |his |her )?"
        r"(?:left |right )?(?:arm|arms|jaw|neck|back|shoulder|shoulders)\b",
        r"\b(?:pain|ache|numbness|tingling) (?:in|down) (?:my |the )?left arm",
        r"\bleft arm (?:pain|hurts|is numb|numbness)",
        r"\bjaw (?:pain|hurts)",
        _AR_PREFIX + r"(?:ينتشر|يمتد|ممتد|منتشر|يروح|ينزل|واصل)\s+(?:الى\s+|لل|ل|في\s+|على\s+)?"
        r"(?:ال)?(?:ذراع|يد|ايد|فك|رقبه|ظهر|كتف)",
        r"(?:الم|وجع|تنميل)\s+(?:في\s+)?(?:ال)?(?:ذراع|يد|ايد)\s+(?:ال)?(?:يسار|يسري|يسرى|اليسار)",
        r"(?:الم|وجع)\s+(?:في\s+)?(?:ال)?فك",
    ],
    "SWEATING": [
        r"\bsweat(?:ing|y|s)?\b",
        r"\bcold sweat",
        r"\bclammy",
        _AR_PREFIX + r"(?:تعرق|اتعرق|يتعرق|تتعرق|عرق بارد|عرقان|يعرق)",
    ],
    # Severe/crushing chest pain is an emergency by itself (no companion symptom needed).
    "SEVERE_CHEST_PAIN": [
        r"\b(?:severe|crushing|intense|unbearable|excruciating|worst|very bad) "
        r"(?:chest (?:pain|pressure)|pain (?:in|on) (?:my |the )?chest)",
        _AR_PREFIX + r"(?:الم|وجع|ضغط)\s+(?:شديد|شديده|قوي|فظيع|لا يحتمل|ما ينطاق)\s+"
        r"(?:جدا\s+)?(?:في\s+|على\s+)?(?:ب?ال)?صدر",
        _AR_PREFIX + r"(?:الم|وجع)\s+(?:ب?ال)?صدر\s+(?:شديد|قوي|فظيع)",
    ],
    "NAUSEA": [
        r"\bnause\w*",
        r"\bvomit\w*",
        r"\bthrowing up|\bthrew up",
        _AR_PREFIX + r"(?:غثيان|استفراغ|ترجيع|لوعه|استفرغ|قيء|تقيو|اتقيا)",
    ],
    "FAINTING_OR_DIZZINESS": [
        # Not bare "faint": "a faint ache" is mild pain, not syncope.
        r"\b(?:fainted|fainting|feel(?:ing)? faint|about to faint)",
        r"\bpass(?:ed)? out",
        r"\bdizz\w*",
        r"\blight[- ]?headed",
        r"\bblack(?:ed)? out",
        _AR_PREFIX + r"(?:اغماء|اغمي علي|دوخه|دايخ|دوار|دوخان)",
    ],
    "STROKE_SIGN": [
        r"\bface (?:is )?droop\w*|\bdroop\w* (?:face|mouth)|\bface (?:is )?drooping",
        r"\bone side of (?:my |his |her )?face",
        r"\b(?:one|1)[- ]sided weakness",
        r"\bweak(?:ness)? (?:on|in) one side",
        r"\b(?:numb(?:ness)?|weak(?:ness)?|paraly\w*) (?:on|in|of) (?:the |my )?(?:left|right) side",
        r"\bslurr\w* (?:speech|words)|\bspeech is slurr\w*|\bslurring",
        # Not bare "can't speak": "I can't speak Arabic" is not a stroke sign.
        r"\b(?:sudden(?:ly)?|slurred) (?:can'?t|cannot|unable to) (?:speak|talk)",
        r"\b(?:trouble|difficulty) (?:speaking|talking)\b",
        _AR_PREFIX + r"(?:ميلان|تدلي|ارتخاء|انحراف)\s+(?:في\s+)?(?:ال)?(?:وجه|فم)",
        r"(?:ضعف|تنميل|شلل)\s+(?:في\s+)?(?:جهه|جانب|نصف|ناحيه)\s+(?:واحد|واحده)",
        r"(?:ضعف|تنميل|شلل)\s+(?:في\s+)?(?:ال)?(?:جهه|جانب|ناحيه|نص)\s+(?:ال)?(?:يمين|يسار|اليمني|اليسري|الايمن|الايسر)",
        r"(?:ثقل|تلعثم|صعوبه)\s+(?:في\s+)?(?:ال)?(?:كلام|نطق|لسان)",
        r"كلامي\s+(?:ثقيل|مو واضح|غير واضح|متلخبط)",
    ],
    "THUNDERCLAP_HEADACHE": [
        # "Sudden severe" headache, not merely "severe" (that alone is not an emergency rule).
        r"\b(?:sudden|thunderclap|explosive)[\w ]{0,20}headache",
        r"\bworst headache",
        _AR_PREFIX + r"صداع\s+(?:شديد\s+)?(?:مفاجي|مفاجئ|فجاه|فجاءه)",
        r"(?:فجاه|فجاءه)\s+(?:\S+\s+){0,3}صداع",
        r"اسوا صداع",
    ],
    "LOSS_OF_CONSCIOUSNESS": [
        r"\bunconscious",
        r"\bunresponsive",
        r"\b(?:lost|loss of|losing) consciousness",
        r"\bcollapsed",
        r"\bnot waking up|\bwon'?t wake up",
        r"(?:فقد|فقدان|فاقد|غايب عن|غائب عن)\s+(?:ال)?وعي",
        r"مغمى عليه|ما يصحى|ما يستجيب",
    ],
    "HEAVY_BLEEDING": [
        r"\b(?:heavy|severe|uncontrolled|massive|a lot of|lots of) bleeding",
        r"\bbleeding (?:heavily|a lot|won'?t stop|that won'?t stop|non[- ]?stop)",
        r"\b(?:vomiting|throwing up|coughing(?: up)?) blood",
        _AR_PREFIX + r"نزيف\s+(?:شديد|قوي|غزير|ما يوقف|ما وقف|لا يتوقف|كثير)",
        r"(?:استفراغ|ترجيع|كحه|سعال|اكح)\s+(?:مع\s+)?دم",
    ],
    "SELF_HARM": [
        r"\b(?:kill|hurt|harm) myself",
        r"\bsuicid\w*",
        r"\bend (?:my|it) (?:life|all)",
        r"\bwant to die",
        _AR_PREFIX + r"(?:ال)?(?:انتحار|انتحر|اقتل نفسي|انهي حياتي|اذي نفسي|ابي اموت|اريد ان اموت)",
    ],
}

# Patterns get the same Arabic folding as the input text (but NOT lowercasing, which
# would corrupt regex escapes like \S), so a pattern may be written in natural spelling
# ("على", "إلى", "مفاجئ") and still match normalized input.
_COMPILED: dict[str, list[re.Pattern[str]]] = {
    concept: [re.compile(_fold_arabic(p)) for p in patterns]
    for concept, patterns in CONCEPTS.items()
}

# Concepts that are emergencies on their own.
_STANDALONE_EMERGENCY = {
    "SEVERE_CHEST_PAIN",
    "SEVERE_BREATHING",
    "STROKE_SIGN",
    "THUNDERCLAP_HEADACHE",
    "LOSS_OF_CONSCIOUSNESS",
    "HEAVY_BLEEDING",
    "SELF_HARM",
}
# Chest pain + any of these => emergency (possible acute coronary syndrome).
_CHEST_PAIN_COMPANIONS = {
    "SHORTNESS_OF_BREATH",
    "SEVERE_BREATHING",
    "RADIATING_PAIN",
    "SWEATING",
    "NAUSEA",
    "FAINTING_OR_DIZZINESS",
}
# Worth prompt attention on their own, but not emergencies without more context.
_STANDALONE_URGENT = {"CHEST_PAIN", "SHORTNESS_OF_BREATH", "FAINTING_OR_DIZZINESS"}

SEVERE_PAIN_THRESHOLD = 8  # severity_1_10 at/above this + chest pain => emergency


@dataclass(frozen=True)
class RedFlagResult:
    level: Urgency
    matched_flags: list[str] = field(default_factory=list)
    concepts: frozenset[str] = frozenset()

    @property
    def is_emergency(self) -> bool:
        return self.level == Urgency.EMERGENCY

    def as_dict(self) -> dict[str, Any]:
        return {"level": str(self.level), "matched_flags": list(self.matched_flags)}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def _is_negated(clause: str, match_start: int) -> bool:
    """True if a negation cue appears in the few words before the match (same conjunct).

    Walks backwards from the match; stops at a conjunction so a negation that
    belongs to a previous phrase cannot silence this symptom.
    """
    distance = 0
    for word in reversed(clause[:match_start].split()):
        word = word.strip("'\"()")
        if word in _NEGATION_CUES or word.endswith("n't"):
            return True
        # Arabic negation often attaches "و" (and): "ولا", "وما", "وبدون".
        if word.startswith("و") and word[1:] in _NEGATION_CUES:
            return True
        if word in _CONJUNCTION_STOPS:
            return False
        if word in _LIST_JOINERS:
            # "no chest pain or shortness of breath": negation distributes over "or",
            # so restart the window from the previous list item.
            distance = 0
            continue
        distance += 1
        if distance > _NEGATION_WINDOW_WORDS:
            return False
    return False


def detect_concepts(text: str) -> set[str]:
    """Return the set of (non-negated) concepts mentioned in free text."""
    normalized = _UNCERTAINTY.sub(" ~ ", normalize(text))
    found: set[str] = set()
    for clause in _CLAUSE_SPLIT.split(f" {normalized} "):
        clause = f" {clause.strip()} "
        for concept, patterns in _COMPILED.items():
            if concept in found:
                continue
            for pattern in patterns:
                match = pattern.search(clause)
                if match and not _is_negated(clause, match.start()):
                    found.add(concept)
                    break
    return found


def _concepts_from_state(state: Mapping[str, Any]) -> set[str]:
    """Map structured PatientState slots to the same concept vocabulary as the text."""
    concepts: set[str] = set()
    complaint_text = " ".join(
        [str(state.get("chief_complaint") or "")] + [str(s) for s in state.get("symptoms") or []]
    )
    concepts |= detect_concepts(complaint_text)
    if state.get("radiating_pain") is True:
        concepts.add("RADIATING_PAIN")
    if state.get("shortness_of_breath") is True:
        concepts.add("SHORTNESS_OF_BREATH")
    if state.get("sweating_or_nausea") is True:
        concepts.add("SWEATING")
    return concepts


def _apply_rules(concepts: set[str], severity: int | None) -> tuple[Urgency, list[str]]:
    flags: list[str] = []
    if "CHEST_PAIN" in concepts:
        companions = sorted(concepts & _CHEST_PAIN_COMPANIONS)
        flags += [f"CHEST_PAIN_WITH_{c}" for c in companions]
        if severity is not None and severity >= SEVERE_PAIN_THRESHOLD:
            flags.append("SEVERE_CHEST_PAIN")
    flags += sorted(concepts & _STANDALONE_EMERGENCY)
    if flags:
        return Urgency.EMERGENCY, flags

    urgent = sorted(concepts & _STANDALONE_URGENT)
    if urgent:
        return Urgency.URGENT, urgent
    return Urgency.UNKNOWN, []


def evaluate(texts: Iterable[str] = (), state: Mapping[str, Any] | None = None) -> RedFlagResult:
    """Evaluate the conversation's user messages and structured state together.

    Concepts are pooled across all messages, so "chest pain" in turn 1 and
    "I'm also sweating" in turn 2 combine into an emergency.
    """
    concepts: set[str] = set()
    for text in texts:
        if text:
            concepts |= detect_concepts(text)
    severity = None
    if state:
        concepts |= _concepts_from_state(state)
        raw_severity = state.get("severity_1_10")
        severity = raw_severity if isinstance(raw_severity, int) else None
    level, flags = _apply_rules(concepts, severity)
    return RedFlagResult(level=level, matched_flags=flags, concepts=frozenset(concepts))
