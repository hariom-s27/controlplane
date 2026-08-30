"""S14, replacing the deleted bias probe.

The old probe (controlplane/bias_probe.py) drew a synthetic group label with
rng.choice(["A","B"]) and never passed it to decide(), which is a pure
function of record facts that exclude it. With no path by which the label
could affect the outcome, the probe could only ever report "no detectable
difference" — it passed by construction, not by correctness. See
docs/experiment-audit.md and the paragraph in docs/limitations.md.

This is the honest check: decide() and every type feeding it are verified
STRUCTURALLY to carry no protected-attribute field. A structural guarantee
that the function cannot read the variable is stronger than a statistical
test over a variable it cannot read.
"""

from __future__ import annotations

import inspect
import re

import pytest

from controlplane import decide as decide_module
from controlplane.decide import decide
from controlplane.schema import (
    Claim,
    Decision,
    Evidence,
    ProposedAction,
    Reason,
    SessionContext,
    ToolCall,
)

# Tokens that would indicate a protected attribute (US Title VII / ECOA /
# UK Equality Act 2010 protected characteristics, plus common proxies).
PROTECTED_TOKENS = {
    "race", "racial", "ethnic", "ethnicity", "gender", "sex", "sexual",
    "orientation", "religion", "religious", "creed", "age", "birthdate",
    "date_of_birth", "dob", "disability", "disabled", "pregnancy", "pregnant",
    "marital", "maritalstatus", "nationality", "national_origin", "citizenship",
    "immigration", "veteran", "genetic", "caste", "postcode", "zipcode",
    "zip_code", "ssn", "aadhaar",
    # proxies for a person's name / identity as a demographic signal
    "firstname", "first_name", "lastname", "last_name", "surname",
    "full_name", "customer_name", "given_name", "family_name",
}

# Merchandise/domain fields that contain a protected-looking substring but
# are not about a person. Each needs a one-line justification here.
ALLOWLIST = {
    "item_colour": "colour of the returned MERCHANDISE, not a person",
    "item_category": "product category of the merchandise",
}

TYPES_FEEDING_DECIDE = [ProposedAction, Claim, Evidence, Reason, Decision, SessionContext, ToolCall]


def _offending_tokens(field_name: str) -> list[str]:
    """A token matches only when every one of its underscore-delimited parts
    appears as a whole part of the field name — so 'trace_id' is not flagged
    for 'race', and 'agent_role' is not flagged for 'age'."""
    if field_name in ALLOWLIST:
        return []
    field_parts = set(field_name.lower().split("_"))
    hits = []
    for tok in PROTECTED_TOKENS:
        tok_parts = set(tok.lower().split("_"))
        if tok_parts <= field_parts:
            hits.append(tok)
    return hits


@pytest.mark.parametrize("model", TYPES_FEEDING_DECIDE, ids=lambda m: m.__name__)
def test_decide_input_types_have_no_protected_attribute_field(model):
    offenders = {}
    for field_name in model.model_fields:
        hits = _offending_tokens(field_name)
        if hits:
            offenders[field_name] = hits
    assert not offenders, (
        f"{model.__name__} has protected-attribute-shaped field(s): {offenders}. "
        "decide() must remain a pure function of record facts. If this field is "
        "legitimate merchandise/domain data, add it to ALLOWLIST with a reason."
    )


def test_decide_signature_takes_no_protected_attribute_parameter():
    params = list(inspect.signature(decide).parameters)
    expected = {
        "trace_id", "manifest_id", "action", "claims", "evidence",
        "predicate_result", "manifest", "clause_match", "grounding_score",
        "grounding_threshold",
    }
    unexpected = set(params) - expected
    assert not unexpected, f"decide() grew unexpected parameter(s): {unexpected}"
    for p in params:
        assert not _offending_tokens(p), f"decide() parameter {p!r} looks like a protected attribute"


def test_decide_module_has_no_protected_attribute_reference_in_source():
    src = inspect.getsource(decide_module).lower()
    strong = {"race", "ethnic", "gender", "religion", "disability", "marital", "nationality"}
    present = sorted(tok for tok in strong if re.search(rf"\b{tok}\w*\b", src))
    assert not present, f"controlplane/decide.py source references: {present}"


def test_bias_probe_module_is_gone():
    """The circular probe must not come back under its old import path."""
    with pytest.raises(ModuleNotFoundError):
        __import__("controlplane.bias_probe")
