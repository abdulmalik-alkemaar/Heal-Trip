"""Best-effort PII redaction for anything we log.

We never ask patients for identifiers, but people paste them anyway. Before free
text reaches logs (application logs, ToolCallLog arguments) we mask the obvious
patterns. This is defense in depth, not a guarantee (see docs/SECURITY.md).
"""

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    # Saudi national ID / Iqama: 10 digits starting with 1 or 2.
    (re.compile(r"(?<!\d)[12]\d{9}(?!\d)"), "[NATIONAL_ID]"),
    # Phone numbers: +966 / 05x / international formats with separators.
    (re.compile(r"(?<!\w)(?:\+|00)\d{1,3}[\s-]?\d{1,4}(?:[\s-]?\d{2,4}){2,3}(?!\w)"), "[PHONE]"),
    (re.compile(r"(?<!\d)05\d(?:[\s-]?\d){7}(?!\d)"), "[PHONE]"),
    # Any other long digit run (card numbers, MRNs, ...).
    (re.compile(r"(?<!\d)\d{8,}(?!\d)"), "[NUMBER]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value):
    """Recursively redact strings inside JSON-like structures."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    return value
