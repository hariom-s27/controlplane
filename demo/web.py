"""PRODUCT-03 — one-screen governance dashboard + profile switcher.

This is a presentation layer over the already-completed Product-01 demo
(scripts/judge_demo.py) and Product-02 presentation model
(product/judge_presentation.py, product/judge_views.py). It creates no
second governance engine, no second decision path, no second evidence
path, and no second receipt path: every scenario call below runs the same
`scripts.judge_demo.SCENARIOS[i]()` function the CLI (product/judge_cli.py)
calls, and every field this module returns is read off the resulting
`PresentationModel` / `evidence_passport()` / `decision_inspector()` —
never re-derived.

EXECUTION BOUNDARY: only `POST /api/run` executes a scenario. Every other
route (`GET /`, `GET /api/catalog`, `POST /api/reset`) is presentation-only
or state-clearing and touches no governance execution path. `POST /api/run`
itself only ever calls one of the six real `scripts.judge_demo.SCENARIOS`
functions — nothing else in this file calls `dispatch_tool`, `decide`,
`extract_action`, `build_receipt`, or a registry resolver. `POST /api/reset`
calls only `scripts.judge_demo.reset_demo()` — the same demo-local reset
Product-01's own `--reset` CLI flag already uses — never a scenario function.

RUN CONCURRENCY (PRODUCT-04A): `_RUN_LOCK` below is a non-blocking mutex. A
RUN or RESET request that arrives while another is in flight is REJECTED
(HTTP 409, status "RUN_IN_PROGRESS") — it never queues, never executes, and
never mutates shared state. Only one governance-state-touching operation
runs at a time process-wide; since the underlying ledger/call-log state is
itself process-global (one shared demo, not a multi-tenant service), that
single in-flight slot IS this demo's session boundary — no per-browser
identity or authentication is introduced to enforce it.

Run:  python -m demo.web
      (binds 127.0.0.1:8000 by default; offline, deterministic, no API key)
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Deterministic, offline, no-API-key defaults for the dashboard process.
# setdefault only — a real .env (loaded by scripts.judge_demo below) or an
# operator-set environment variable always wins. These are the same
# development-fixture values already documented in .env.example, not new
# secrets or new behaviour.
os.environ.setdefault("CP_RECEIPT_SECRET", "development-test-fixture-not-for-production")
os.environ.setdefault("CP_DEMO_DATE", "2026-08-14")
os.environ.setdefault("CP_PII", "regex")
os.environ.setdefault("CP_GROUNDING", "off")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from controlplane.idempotency import reset_execution_ledger  # noqa: E402
from controlplane.manifest import load_manifest  # noqa: E402
from product.judge_presentation import (  # noqa: E402
    NOT_AVAILABLE,
    build_presentation_model,
)
from product.judge_views import (  # noqa: E402
    NOT_APPLICABLE_FOR_PROFILE,
    decision_inspector,
    evidence_health_disclaimer,
    evidence_passport,
)
from scripts import judge_demo as demo  # noqa: E402

# ---------------------------------------------------------------------------
# Profile catalog — the two manifests judge_demo's scenarios actually bind
# to (see product/judge_presentation.py::PresentationModel.profile, which is
# read straight off receipt["manifest_id"]). Not invented: manifests/
# servicing.yaml declares manifest_id "servicing-v1",
# manifests/knowledge_assistant.yaml declares "knowledge_assistant-v1".
# ---------------------------------------------------------------------------

PROFILES: list[dict[str, Any]] = [
    {"id": "servicing-v1", "manifest_name": "servicing", "label": "Customer Support"},
    {"id": "knowledge_assistant-v1", "manifest_name": "knowledge_assistant",
     "label": "Internal Knowledge Assistant"},
]
_PROFILE_BY_ID = {p["id"]: p for p in PROFILES}

_MANIFEST_DISPLAY_FIELDS = (
    "tool", "risk_tier_default", "window_days", "authority_ceiling_paise",
    "latency_budget_ms", "escalation_budget_pct", "fail_posture", "reliability_floor",
)


def _profile_manifest_summary(profile: dict[str, Any]) -> dict[str, Any]:
    """Reads the real manifest YAML (already loaded by controlplane.manifest,
    the same loader decide()'s own pipeline uses) — no separate config."""
    manifest = load_manifest(profile["manifest_name"])
    summary = {k: manifest.get(k) for k in _MANIFEST_DISPLAY_FIELDS}
    comp = manifest.get("compensation") or {}
    summary["compensation_action"] = comp.get("action")
    summary["compensability"] = comp.get("compensability")
    return summary


# ---------------------------------------------------------------------------
# Scenario catalog — static UI labels only (section 28: the only permitted
# hardcoding). The literal numbers/keys/titles mirror the dataclass fields
# scripts/judge_demo.py's own ScenarioResult objects are constructed with
# (see e.g. `ScenarioResult(number=3, key="contradiction", title="RELIABLE
# CONTRADICTION", ...)` in scenario_3_contradiction()) — kept in sync by
# tests/test_product03_dashboard.py, which runs every real scenario once and
# asserts this catalog's key/title match the real result exactly.
# `supported_profiles` is derived from the ACTUAL manifest each scenario
# binds to (also asserted by that same test), not inferred from the name.
# ---------------------------------------------------------------------------

SCENARIO_CATALOG: list[dict[str, Any]] = [
    {"index": 1, "key": "allow", "title": "NORMAL ALLOW",
     "supported_profiles": ["knowledge_assistant-v1"], "hero": False},
    {"index": 2, "key": "source_unreliable", "title": "SOURCE UNRELIABLE",
     "supported_profiles": ["servicing-v1"], "hero": False},
    {"index": 3, "key": "contradiction", "title": "RELIABLE CONTRADICTION",
     "supported_profiles": ["knowledge_assistant-v1"], "hero": True},
    {"index": 4, "key": "invalid_modify", "title": "INVALID MODIFY / SAFETY REFUSAL",
     "supported_profiles": ["knowledge_assistant-v1"], "hero": False},
    {"index": 5, "key": "valid_modify", "title": "VALID MODIFY",
     "supported_profiles": ["servicing-v1", "knowledge_assistant-v1"], "hero": False},
    {"index": 6, "key": "duplicate_replay", "title": "DUPLICATE / REPLAY",
     "supported_profiles": ["knowledge_assistant-v1"], "hero": False},
]
_SCENARIO_BY_INDEX = {s["index"]: s for s in SCENARIO_CATALOG}


def _is_supported(scenario_index: int, profile_id: str) -> bool:
    scenario = _SCENARIO_BY_INDEX.get(scenario_index)
    return scenario is not None and profile_id in scenario["supported_profiles"]


# ---------------------------------------------------------------------------
# Claims <-> Evidence side-by-side rows — pure reshaping of fields already on
# the PresentationModel (model.claims / model.evidence / model.claim_evidence_
# comparisons are already positionally paired by product/judge_presentation.py
# — see that module's own docstring on why positional pairing is valid here).
# This function computes no new comparison and resolves no new evidence.
# ---------------------------------------------------------------------------


def _claim_evidence_rows(model) -> list[dict[str, Any]]:
    rows = []
    for i, claim in enumerate(model.claims):
        ev = model.evidence[i] if i < len(model.evidence) else None
        cmp = model.claim_evidence_comparisons[i] if i < len(model.claim_evidence_comparisons) else None
        rows.append({
            "claim_kind": claim.get("kind", NOT_AVAILABLE),
            "tier": claim.get("tier") or NOT_AVAILABLE,
            "load_bearing": claim.get("load_bearing", NOT_AVAILABLE),
            "asserted_value": claim.get("asserted"),
            "evidence_source": ev.source if ev else NOT_AVAILABLE,
            "evidence_field": ev.field if ev else NOT_AVAILABLE,
            "evidence_query": ev.query if ev else NOT_AVAILABLE,
            "evidence_value": ev.value if ev else None,
            "reliability": ev.reliability if ev else NOT_AVAILABLE,
            "freshness_ms": ev.freshness_ms if ev else NOT_AVAILABLE,
            "comparison_rule": cmp.comparison_rule if cmp else NOT_AVAILABLE,
            "comparison_result": cmp.comparison_result if cmp else NOT_AVAILABLE,
        })
    return rows


def _scenario_ref(scenario: dict[str, Any]) -> dict[str, Any]:
    return {"index": scenario["index"], "key": scenario["key"], "title": scenario["title"]}


def _profile_ref(profile: dict[str, Any]) -> dict[str, Any]:
    return {"id": profile["id"], "label": profile["label"]}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="ControlPlane — Judge Dashboard")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Real scenario execution (scenario fn -> reset_execution_ledger ->
# demo._call_log) touches process-global state. A second RUN/RESET arriving
# while one is in flight is REJECTED, not queued — see module docstring.
_RUN_LOCK = threading.Lock()

# Section 13: raw exception text must never reach the judge-facing UI. Every
# non-2xx demo-layer response uses one of these fixed, safe messages.
_SAFE_MESSAGES = {
    "RUN_IN_PROGRESS": "RUN ALREADY IN PROGRESS",
    "SCENARIO_ERROR": "UNABLE TO COMPLETE DEMO RUN",
}


def _safe_error(status: str, scenario: dict[str, Any] | None, profile: dict[str, Any] | None,
                 status_code: int) -> JSONResponse:
    """Builds an error response from a fixed safe category only — never
    str(exc) or any other raw internal detail (section 13)."""
    body: dict[str, Any] = {"status": status, "message": _SAFE_MESSAGES[status]}
    if scenario is not None:
        body["scenario"] = _scenario_ref(scenario)
    if profile is not None:
        body["profile"] = _profile_ref(profile)
    return JSONResponse(body, status_code=status_code)


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "profiles": PROFILES,
        "scenarios": SCENARIO_CATALOG,
        "evidence_health_disclaimer": evidence_health_disclaimer(),
    })


@app.get("/api/catalog")
def api_catalog() -> dict[str, Any]:
    """Presentation-only: profile/scenario metadata and the applicability
    matrix. Executes nothing."""
    profiles = []
    for p in PROFILES:
        profiles.append({**_profile_ref(p), "manifest": _profile_manifest_summary(p)})
    scenarios = []
    for s in SCENARIO_CATALOG:
        scenarios.append({
            **_scenario_ref(s),
            "hero": s["hero"],
            "supported_profiles": s["supported_profiles"],
        })
    return {"profiles": profiles, "scenarios": scenarios}


class RunRequest(BaseModel):
    profile_id: str
    scenario_index: int


@app.post("/api/run")
def api_run(req: RunRequest) -> JSONResponse:
    """The ONLY route that executes a scenario. Every RUN starts from a
    fresh isolated demo state (reset_execution_ledger + clearing the demo's
    own call log — the same isolation tests/test_product02_judge_presentation.py's
    `_isolated_ledger` fixture applies) so unrelated RUNs never share
    mutable state. Scenario 6 (duplicate/replay) still makes its own two
    calls inside this single RUN, by design (scripts/judge_demo.py itself).
    A RUN that arrives while another is already executing is REJECTED
    (never queued) by `_RUN_LOCK` below — see module docstring."""
    profile = _PROFILE_BY_ID.get(req.profile_id)
    scenario = _SCENARIO_BY_INDEX.get(req.scenario_index)
    if profile is None or scenario is None:
        raise HTTPException(status_code=400, detail="unknown profile_id or scenario_index")

    if not _is_supported(scenario["index"], profile["id"]):
        return JSONResponse({
            "status": NOT_APPLICABLE_FOR_PROFILE,
            "scenario": _scenario_ref(scenario),
            "profile": _profile_ref(profile),
            "reason": f"{scenario['title']} is not applicable under the {profile['label']} profile.",
        })

    if not _RUN_LOCK.acquire(blocking=False):
        return _safe_error("RUN_IN_PROGRESS", scenario, profile, 409)
    try:
        try:
            reset_execution_ledger()
            demo._call_log.clear()
            fn = demo.SCENARIOS[scenario["index"] - 1]
            result = fn()
        except Exception as exc:  # pragma: no cover - defensive, see section 33
            print(f"[demo] scenario error ({scenario['key']!r}): {exc!r}", file=sys.stderr)
            return _safe_error("SCENARIO_ERROR", scenario, profile, 500)
    finally:
        _RUN_LOCK.release()

    model = build_presentation_model(result)

    if not model.available:
        passport = evidence_passport(model)
        inspector = decision_inspector(model)
        return JSONResponse({
            "status": "NOT_AVAILABLE",
            "scenario": _scenario_ref(scenario),
            "profile": _profile_ref(profile),
            "reason": model.unavailable_reason,
            "passport": passport,
            "inspector": inspector,
        })

    passport = evidence_passport(model, expected_profile=profile["id"])
    inspector = decision_inspector(model, expected_profile=profile["id"])
    if passport.get("status") == NOT_APPLICABLE_FOR_PROFILE:
        # Defensive: the applicability matrix above should make this
        # unreachable, but never silently show a stale-profile result.
        return JSONResponse({
            "status": NOT_APPLICABLE_FOR_PROFILE,
            "scenario": _scenario_ref(scenario),
            "profile": _profile_ref(profile),
            "reason": passport.get("note", NOT_APPLICABLE_FOR_PROFILE),
        })

    receipt = result.receipt or {}
    policy_lines = demo._receipt_policy_lines(receipt) if receipt else []
    reason_lines = demo._receipt_reason_lines(receipt) if receipt else []

    return JSONResponse({
        "status": "OK",
        "scenario": _scenario_ref(scenario),
        "profile": _profile_ref(profile),
        "demo_mode": True,
        "evidence_source": result.evidence_source,
        "ai_intent": model.ai_intent,
        "proposed_action": model.proposed_action,
        "claim_evidence_rows": _claim_evidence_rows(model),
        "policy_version": model.policy_version,
        "policy_lines": policy_lines,
        "predicate_result": model.predicate_result,
        "verdict": model.verdict,
        "intervention": model.intervention,
        "root_cause": model.root_cause,
        "reason_lines": reason_lines,
        "execution_state": model.execution_state,
        "execution_status_raw": model.execution_status_raw,
        "call_count": result.call_count,
        "idempotency_key": model.idempotency_key,
        "receipt_reference": model.receipt_reference,
        "receipt_verification": model.receipt_verification,
        "trace_id": model.trace_id,
        "runtime_latency_ms": model.runtime_latency_ms,
        "evidence_origin": model.evidence_origin,
        "unavailable_fields": sorted(model.unavailable_fields),
        "passport": passport,
        "inspector": inspector,
    })


@app.post("/api/reset")
def api_reset() -> JSONResponse:
    """PRODUCT-04A dashboard reset (section 11). Clears only demo-local
    state: the idempotency ledger, the implementation call log, and the
    demo-generated decision trail files (decisions.jsonl /
    decisions_privileged.jsonl) — by calling `scripts.judge_demo.reset_demo()`,
    the exact same primitive Product-01's own `--reset` CLI flag already
    uses. Touches no canonical fixture, no research artifact, no
    controlplane/ production file, and executes no scenario."""
    if not _RUN_LOCK.acquire(blocking=False):
        return _safe_error("RUN_IN_PROGRESS", None, None, 409)
    try:
        demo.reset_demo()
    finally:
        _RUN_LOCK.release()
    return JSONResponse({"status": "RESET_OK"})


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
