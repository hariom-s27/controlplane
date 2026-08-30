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
names, not the stale-version case. Second, it's what makes the per-tier
claim breakdown honest — without a real C3 tier, schema.py's
Decision.coverage would report every claim as C1/C2, implying the whole
pipeline is as deterministically checkable as SQL and arithmetic, which it
demonstrably is not. (The old scalar "coverage_ratio" that collapsed this
into a single 1.0 was retired — see docs/experiment-audit.md.)

Loaded once — never per call, per the roadmap's own instruction. Lazily at
first `score()` in normal use; `preload()` forces it at process start so a
latency harness can time it as a clean cold start (P09). The load dominates
tail latency; P09 measures both (`reports/latency.md` §E cold start,
§C/§G steady-state `ground` stage), not a bug to hide.

CP_GROUNDING=off (the .env default) means this module is simply never
imported — controlplane/intercept.py wraps the import in try/except
ImportError specifically so the rest of the pipeline works with neither
torch nor transformers installed. The demo runs fine without it.
"""

from __future__ import annotations

import threading

MODEL_NAME = "vectara/hallucination_evaluation_model"

_model = None
_load_lock = threading.Lock()


def _load():
    global _model
    if _model is None:
        # Double-checked under the lock: P09 fires the first grounded call from
        # a 10-worker pool, and without this every worker would load its own
        # ~0.1B-param copy. The one-time load is the measured cold start.
        with _load_lock:
            if _model is None:
                from transformers import AutoModelForSequenceClassification

                _model = AutoModelForSequenceClassification.from_pretrained(
                    MODEL_NAME, trust_remote_code=True
                )
    return _model


def preload() -> None:
    """Load the grounding model once, at process start, so no scored call pays
    for it. P09's latency harness calls this and times it as the cold start,
    keeping it out of the steady-state percentile table."""
    _load()


def is_loaded() -> bool:
    return _model is not None


def score(premise: str, hypothesis: str) -> float:
    """Higher = more consistent with the premise. HHEM's own scale is 0-1."""
    model = _load()
    return float(model.predict([(premise, hypothesis)])[0])


__all__ = ["score", "preload", "is_loaded", "MODEL_NAME"]
