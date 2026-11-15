"""SECURITY.md stays short and honest.

It must send reporters to GitHub's private vulnerability reporting (not a
public issue and not an email address), stay under 25 lines, and promise no
response time or fix date that this small project could not keep.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = (ROOT / "SECURITY.md").read_text(encoding="utf-8")


def test_security_policy_is_short():
    assert len(TEXT.splitlines()) < 25


def test_reports_go_to_private_vulnerability_reporting_not_email():
    assert "private" in TEXT.lower() and "Report a vulnerability" in TEXT
    assert "Do not open a public issue" in TEXT
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", TEXT), "no email address"


def test_no_response_time_promise():
    assert "cannot promise a response" in TEXT
    assert not re.search(r"\bwithin \d+\s*(hours?|days?|business days?)\b", TEXT, flags=re.I)
