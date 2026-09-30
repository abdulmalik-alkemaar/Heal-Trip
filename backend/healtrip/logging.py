"""Logging helpers: PII redaction on every record, optional JSON output.

Log lines carry identifiers (session_id, tool names, latencies, outcome codes), never
the patient's message text. As defense in depth, this filter also redacts
phone/email/ID-like strings from the message and from any string `extra` field.
"""

import logging

from assistant.safety.pii import redact

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class PiiRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        for key, value in list(record.__dict__.items()):
            if key not in _STANDARD_ATTRS and isinstance(value, str):
                setattr(record, key, redact(value))
        return True
