"""The gitleaks ignore list may only hold commit-qualified fingerprints (P05 V18b).

gitleaks also honours `file:rule:line` lines, which would mute that spot in every
future commit. Only `<40-hex commit>:<file>:<rule>:<line>` is allowed here, so each
entry mutes exactly one reviewed finding in one past commit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = ROOT / ".gitleaksignore"
FINGERPRINT = re.compile(r"^[0-9a-f]{40}:[^:]+:[a-z0-9-]+:\d+$")


def _entries() -> list[str]:
    text = IGNORE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return [line for line in text.split("\n") if line.strip() and not line.startswith("#")]


def test_every_entry_is_commit_qualified():
    entries = _entries()
    assert entries, ".gitleaksignore has no entries"
    bad = [line for line in entries if not FINGERPRINT.match(line)]
    assert bad == [], f"not commit-qualified: {bad}"


def test_no_duplicate_entries():
    entries = _entries()
    assert len(entries) == len(set(entries))
