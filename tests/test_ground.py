"""S8 checkpoint — the two required fixtures. Skipped entirely when
torch/transformers aren't installed (CP_GROUNDING=off is the documented
default specifically because this is a ~600MB+ optional download; the rest
of the suite must never depend on it being present).
"""

from __future__ import annotations

import pytest

pytest.importorskip("transformers")

from controlplane import ground  # noqa: E402

V42_TEXT = (
    "Customers may request a full refund within 7 days of the delivery date. "
    "Requests made after 7 days may be eligible for store credit at the "
    "discretion of a supervisor. Refunds are issued to the original payment "
    "method within 5-7 business days of approval."
)

THRESHOLD = 0.5


def test_accurate_paraphrase_scores_above_threshold():
    paraphrase = (
        "The current policy allows a full refund within 7 days of delivery; "
        "after that, customers may get store credit instead, at a "
        "supervisor's discretion."
    )
    assert ground.score(V42_TEXT, paraphrase) >= THRESHOLD


def test_paraphrase_asserting_30_day_window_scores_below_threshold():
    """This is the actual hallucination case: a fluent, plausible-sounding
    claim that the current policy simply does not say."""
    paraphrase = "Customers can get a full refund within 30 days of delivery."
    assert ground.score(V42_TEXT, paraphrase) < THRESHOLD
