"""P07 Fix 7 — the "Deming sentence" is replaced by the Runbook §02 reformulation.

The kp-rule / all-or-none theorem is proved for a process *in statistical
control*. The old pitch sentence ("Deming proved that when defects are
correlated there is no optimal sample size", "Deming, 1986 — ...") inverts
that assumption set. The Round 2 Runbook §02 supplies a safe reformulation
that leans on the OC curve's i.i.d. assumption instead.

This test guards three things:
  1. the authoritative reformulation is captured verbatim in-repo;
  2. docs/ROADMAP.md points at that capture (Fix 7 is wired, not dangling);
  3. no shippable doc asserts the prohibited theorem framing or writes
     "Deming, 1986" as a bare attribution.

If (3) fails: use the verbatim text in docs/round2-runbook-block0.md — do
not paraphrase it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK_02 = ROOT / "docs" / "round2-runbook-block0.md"
ROADMAP = ROOT / "docs" / "ROADMAP.md"

# The verbatim reformulation, transcribed from the Round 2 Runbook §02
# ("Safe reformulation, which survives either reading:"). Artifact
# 7337b733-8db8-4126-8f57-4d0a9ff48e23, retrieved 2026-08-30.
REFORMULATION_OPENING = (
    "Acceptance sampling rests on operating-characteristic curves, and OC curves "
    "assume binomial or hypergeometric draws at a constant proportion nonconforming "
    "— i.i.d. defects from a process in statistical control."
)
REFORMULATION_CLOSING = (
    "Sampling theory says sampling is the wrong tool here, and it says so twice, "
    "for two different reasons."
)

# Assertion-of-theorem forms + bare-attribution forms that P07 Fix 7 forbids.
_PROHIBITED = re.compile(
    r"Deming\s+(showed|proved|demonstrated)"
    r"|Deming(?:'s)?[, ]+1986\s*[—–-]"          # "Deming, 1986 —" attribution
    r"|Caption:\s*Deming"
    r"|(?:when\s+defects\s+are\s+(?:correlated|systematic)[^.]*?there\s+is\s+no\s+optimal\s+sample\s+size)",
    re.IGNORECASE,
)

# Docs that legitimately quote the citation/reformulation and must be exempt.
_EXEMPT = {RUNBOOK_02.resolve(), ROADMAP.resolve()}
_SHIPPABLE_DOCS = [
    p for p in (ROOT / "docs").rglob("*.md")
    if p.resolve() not in _EXEMPT
] + [ROOT / "README.md"]


def test_runbook_02_reformulation_is_captured_verbatim():
    assert RUNBOOK_02.is_file(), "docs/round2-runbook-block0.md is missing — Fix 7 has no source"
    text = RUNBOOK_02.read_text(encoding="utf-8")
    assert REFORMULATION_OPENING in text, "the reformulation's opening sentence is not verbatim in the capture"
    assert REFORMULATION_CLOSING in text, "the reformulation's closing sentence is not verbatim in the capture"
    assert 'Safe reformulation, which survives either reading:' in text


def test_roadmap_points_at_the_captured_reformulation():
    text = ROADMAP.read_text(encoding="utf-8")
    assert "round2-runbook-block0.md" in text, "docs/ROADMAP.md still dangles on an absent runbook"
    # the three fix-instruction rows must carry the verbatim quote or the pointer
    assert REFORMULATION_CLOSING in text or text.count("round2-runbook-block0.md") >= 3


@pytest.mark.parametrize("path", _SHIPPABLE_DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_prohibited_deming_framing_in_shippable_docs(path):
    if not path.is_file():
        pytest.skip(f"{path} not present")
    m = _PROHIBITED.search(path.read_text(encoding="utf-8"))
    assert not m, (
        f"{path.relative_to(ROOT)} uses the retired Deming/kp-rule framing "
        f"({m.group(0)!r}). Replace with the verbatim text in docs/round2-runbook-block0.md."
    )
