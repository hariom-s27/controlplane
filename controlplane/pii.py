"""S14 — PII recognition on outbound content. Tier 1, C2: a deterministic
rule (regex, or presidio's NER model) applied to text — not a raw field
read, not a semantic judgment. Detection only: this module answers "does
this text look like it contains personal data," never "is the recipient
allowed to see it." That second question is entitlement's job
(controlplane/registry/entitlements.py), not this module's — conflating the
two hides the failure mode where legitimate PII goes to the wrong recipient.

CP_PII=regex (default) needs no download and works offline — this is the
fallback presidio's model downloads sometimes fail behind on a fresh clone.
CP_PII=presidio uses presidio-analyzer's NER model for names, which regex
genuinely cannot do well; report both honestly, per the roadmap's own
instruction: "recogniser-based detection is moderate at best." Nobody
should read a PASS from this module as "no PII risk here" — only as "no
PII pattern this detector knows how to find."
"""

from __future__ import annotations

import os
import re

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\d{10}\b")
_ORDER_ID_RE = re.compile(r"\bORD-\d{4,}\b")
_PINCODE_RE = re.compile(r"\b\d{6}\b")  # Indian PIN code, 6 digits
# Name detection via regex is a known weak point — capitalised word runs of
# 2-3 tokens, deliberately not attempting anything smarter. This is exactly
# the "moderate at best" the roadmap warns about; presidio's NER model does
# meaningfully better and is the reason CP_PII=presidio exists.
_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b")


def _regex_detect(text: str) -> list[dict]:
    hits = []
    for label, pattern in (
        ("EMAIL", _EMAIL_RE),
        ("PHONE", _PHONE_RE),
        ("ORDER_ID", _ORDER_ID_RE),
        ("PINCODE", _PINCODE_RE),
        ("NAME", _NAME_RE),
    ):
        for m in pattern.finditer(text):
            hits.append({"entity_type": label, "text": m.group(), "start": m.start(), "end": m.end()})
    return hits


_presidio_analyzer = None


def _presidio_detect(text: str) -> list[dict]:
    global _presidio_analyzer
    if _presidio_analyzer is None:
        from presidio_analyzer import AnalyzerEngine

        _presidio_analyzer = AnalyzerEngine()
    results = _presidio_analyzer.analyze(text=text, language="en")
    return [
        {"entity_type": r.entity_type, "text": text[r.start : r.end], "start": r.start, "end": r.end, "score": r.score}
        for r in results
    ]


def detect(text: str) -> list[dict]:
    """CP_PII=regex (default, offline, moderate recall) or
    CP_PII=presidio (needs a model download, better on names)."""
    mode = os.environ.get("CP_PII", "regex")
    if mode == "presidio":
        try:
            return _presidio_detect(text)
        except Exception:
            # Presidio's model download failing on a fresh clone is the
            # roadmap's own named risk. Fall back rather than crash the gate.
            return _regex_detect(text)
    return _regex_detect(text)


def contains_pii(text: str) -> bool:
    return len(detect(text)) > 0


__all__ = ["detect", "contains_pii"]
