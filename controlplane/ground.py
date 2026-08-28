"""S8 — grounding, the C3 tier. HHEM-2.1-Open (vectara/hallucination_evaluation_model,
Apache-2.0, ~0.1B params, CPU-viable) scores whether the agent's paraphrase
of a clause is actually entailed by the clause text currently in force.

Premise = the freshly-queried clause (the registry's resolved evidence
value, never the agent's stale retrieval). Hypothesis = the agent's
paraphrase (action.claimed_clause_text). A score below the manifest's
threshold routes to CONTRADICTED at MODERATE confidence in decide() —
never certainty: published LLM-AggreFact SOTA for this class of model is
77.4%, not 100%, so C3 is labeled moderate everywhere and low confidence
escalates rather than blocks (D3), regardless of what this function returns.

Why build a whole model for this when R5 (clause_current) already catches
a version mismatch by metadata? Two reasons. First, this catches the
subtler case: the version matches but the agent paraphrased the clause
into something it doesn't actually say — the hallucination case the brief
names, not the stale-version case. Second, it's what makes the coverage
number honest — without a real C3 tier, coverage_ratio in schema.py's
Decision.coverage would either omit C3 entirely or, worse, imply it's as
checkable as C1/C2, which it demonstrably is not.

Loaded once, lazily, at first call — never per call, per the roadmap's own
instruction. The load itself is expected to dominate tail latency; that's a
measured finding for S11's rule_promotion_cost logger, not a bug to hide.

CP_GROUNDING=off (the .env default) means this module is simply never
imported — controlplane/intercept.py wraps the import in try/except
ImportError specifically so the rest of the pipeline works with neither
torch nor transformers installed. The demo runs fine without it.
"""

from __future__ import annotations

_model = None


def _load():
    global _model
    if _model is None:
        from transformers import AutoModelForSequenceClassification

        _model = AutoModelForSequenceClassification.from_pretrained(
            "vectara/hallucination_evaluation_model", trust_remote_code=True
        )
    return _model


def score(premise: str, hypothesis: str) -> float:
    """Higher = more consistent with the premise. HHEM's own scale is 0-1."""
    model = _load()
    return float(model.predict([(premise, hypothesis)])[0])


__all__ = ["score"]
