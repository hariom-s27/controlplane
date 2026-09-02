"""PRODUCT-03 — focused tests for the one-screen judge dashboard
(demo/web.py, demo/templates/index.html, demo/static/app.js).

These tests do not re-test controlplane/* correctness (see tests/test_*.py
for that) or the Product-02 presentation layer's own contract (see
tests/test_product02_judge_presentation.py). They lock in that the
dashboard:
  - is a pure presentation/orchestration layer: it imports and calls the
    real scripts.judge_demo.SCENARIOS functions unchanged and reshapes the
    real product.judge_presentation.PresentationModel / product.judge_views
    output — it never re-derives evidence, claims, policy, or verdicts;
  - executes a scenario ONLY from POST /api/run, never from GET / or
    GET /api/catalog;
  - enforces the scenario x profile applicability matrix server-side, not
    just in the client;
  - keeps verdict / intervention / execution_state distinct and renders
    BLOCK/ALLOW/ESCALATE correctly;
  - never fabricates a confidence score;
  - is deterministic across repeated isolated RUNs;
  - agrees with the CLI (scripts.judge_demo / product.judge_cli) on every
    substantive field for the same scenario;
  - keeps the Evidence Passport, Decision Inspector, dashboard fields, and
    receipt in agreement (section 38).
"""

from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from controlplane.idempotency import reset_execution_ledger
from demo.web import PROFILES, SCENARIO_CATALOG, _is_supported, app
from product.judge_presentation import build_presentation_model, classify_receipt
from scripts import judge_demo as demo

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_ledger():
    reset_execution_ledger()
    demo._call_log.clear()
    yield
    reset_execution_ledger()
    demo._call_log.clear()


def _run(profile_id: str, scenario_index: int) -> dict:
    resp = client.post("/api/run", json={"profile_id": profile_id, "scenario_index": scenario_index})
    assert resp.status_code == 200, resp.text
    return resp.json()


HERO_PROFILE = "knowledge_assistant-v1"
HERO_SCENARIO = 3  # RELIABLE CONTRADICTION — the real BLOCK+PREVENTED case


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_app_imports_and_page_renders():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "CONTROLPLANE" in resp.text
    assert "profileSelect" in resp.text
    assert "scenarioSelect" in resp.text


def test_catalog_lists_profiles_and_scenarios_for_the_selectors():
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    body = resp.json()
    profile_ids = {p["id"] for p in body["profiles"]}
    assert profile_ids == {"servicing-v1", "knowledge_assistant-v1"}
    scenario_indices = {s["index"] for s in body["scenarios"]}
    assert scenario_indices == {1, 2, 3, 4, 5, 6}
    hero = [s for s in body["scenarios"] if s["hero"]]
    assert len(hero) == 1
    assert hero[0]["index"] == HERO_SCENARIO


def test_scenario_selection_and_profile_selection_each_reach_a_real_result():
    allow = _run("knowledge_assistant-v1", 1)
    assert allow["status"] == "OK"
    escalate = _run("servicing-v1", 2)
    assert escalate["status"] == "OK"


# ---------------------------------------------------------------------------
# Product-01 / Product-02 integration
# ---------------------------------------------------------------------------


def test_run_consumes_the_real_product01_result_and_product02_model():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    real_result = demo.scenario_3_contradiction()
    reset_execution_ledger()
    demo._call_log.clear()
    real_model = build_presentation_model(real_result)

    assert body["verdict"] == real_model.verdict
    assert body["intervention"] == real_model.intervention
    assert body["trace_id"] == real_model.trace_id
    assert body["idempotency_key"] == real_model.idempotency_key


def test_passport_and_inspector_data_appear_in_the_run_response():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    assert body["passport"]["kind"] == "EVIDENCE_PASSPORT"
    assert body["inspector"]["kind"] == "DECISION_INSPECTOR"
    assert body["passport"]["evidence"] != "NOT AVAILABLE"
    assert body["inspector"]["claim_evidence_chain"]


# ---------------------------------------------------------------------------
# Semantic integrity
# ---------------------------------------------------------------------------


def test_claim_evidence_rows_preserve_the_real_semantic_mapping():
    """Scenario 2 (servicing) is the one case with a semantically comparable
    claim (WITHIN_REFUND_WINDOW) — with no asserted value, so UNAVAILABLE,
    never a fabricated MATCH/CONFLICT (see test_product02_judge_presentation.py's
    equivalent check on the underlying model)."""
    body = _run("servicing-v1", 2)
    rows = body["claim_evidence_rows"]
    assert len(rows) == 1
    assert rows[0]["claim_kind"] == "within_refund_window"
    assert rows[0]["comparison_result"] == "UNAVAILABLE"


def test_unrelated_claim_kinds_show_no_direct_comparison():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    rows = body["claim_evidence_rows"]
    assert rows, "hero scenario has claims to check"
    for r in rows:
        assert r["claim_kind"] in (
            "doc_classification_permitted", "recipient_entitled_to_doc",
            "excerpt_contains_third_party_pii",
        )
        assert r["comparison_result"] == "NO DIRECT COMPARISON"


def test_missing_runtime_latency_renders_not_available_not_a_default():
    body = _run("servicing-v1", 2)
    assert body["runtime_latency_ms"] == "NOT AVAILABLE"
    assert "runtime_latency_ms" in body["unavailable_fields"]


def test_evidence_origin_is_preserved_not_invented():
    runtime_body = _run(HERO_PROFILE, HERO_SCENARIO)
    fixture_body = _run("servicing-v1", 2)
    assert runtime_body["evidence_origin"] == "RUNTIME"
    assert fixture_body["evidence_origin"] == "FIXTURE"


# ---------------------------------------------------------------------------
# Execution safety — only POST /api/run may execute a scenario
# ---------------------------------------------------------------------------


def test_index_page_never_executes(monkeypatch):
    def _explode(*_a, **_k):
        raise AssertionError("GET / must never dispatch/decide")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    resp = client.get("/")
    assert resp.status_code == 200
    assert demo._call_log == []


def test_catalog_endpoint_never_executes(monkeypatch):
    def _explode(*_a, **_k):
        raise AssertionError("GET /api/catalog must never dispatch/decide")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    assert demo._call_log == []


def test_unsupported_combination_does_not_execute(monkeypatch):
    def _explode(*_a, **_k):
        raise AssertionError("a NOT-APPLICABLE combination must never dispatch")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    body = _run("servicing-v1", 1)  # scenario 1 is knowledge_assistant-only
    assert body["status"] == "NOT APPLICABLE FOR PROFILE"
    assert demo._call_log == []


def test_rendering_the_passport_and_inspector_from_an_existing_result_never_executes(monkeypatch):
    """Once a RUN has produced a result, re-deriving Passport/Inspector views
    from it (what the dashboard's expandable panels do, client-side, with no
    further network call) must never re-run governance — mirrors
    tests/test_product02_judge_presentation.py's own version of this check,
    scoped to the exact model the dashboard builds."""
    result = demo.scenario_1_allow()
    reset_execution_ledger()
    demo._call_log.clear()
    model = build_presentation_model(result)

    def _explode(*_a, **_k):
        raise AssertionError("presentation must never call this")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    monkeypatch.setattr("controlplane.extract.extract_action", _explode)
    monkeypatch.setattr("controlplane.receipt.build_receipt", _explode)

    from demo.web import _claim_evidence_rows
    from product.judge_views import decision_inspector, evidence_passport

    _claim_evidence_rows(model)
    evidence_passport(model, expected_profile=HERO_PROFILE)
    decision_inspector(model, expected_profile=HERO_PROFILE)
    assert demo._call_log == []


# ---------------------------------------------------------------------------
# Profile safety
# ---------------------------------------------------------------------------


def test_scenario_profile_matrix_matches_the_actual_manifest_each_scenario_binds_to():
    """Derived from the real result, not inferred from a scenario's name:
    every scenario the catalog claims is SUPPORTED under a profile must
    actually produce that profile's manifest_id when run, and every
    scenario NOT listed as supported for a profile must not."""
    for scenario in SCENARIO_CATALOG:
        reset_execution_ledger()
        demo._call_log.clear()
        result = demo.SCENARIOS[scenario["index"] - 1]()
        model = build_presentation_model(result)
        if not model.available:
            # scenario 5: genuinely unavailable, independent of profile —
            # the catalog marks it supported everywhere for exactly this
            # reason (see demo/web.py SCENARIO_CATALOG comment).
            assert scenario["supported_profiles"] == [p["id"] for p in PROFILES]
            continue
        for profile in PROFILES:
            expected = profile["id"] in scenario["supported_profiles"]
            actual = model.profile == profile["id"]
            assert expected == actual, (
                f"scenario {scenario['key']} vs profile {profile['id']}: "
                f"catalog says supported={expected}, real profile={model.profile!r}"
            )


def test_unsupported_scenario_profile_combination_is_rejected():
    body = _run("servicing-v1", 1)
    assert body["status"] == "NOT APPLICABLE FOR PROFILE"
    assert "verdict" not in body


def test_stale_result_never_silently_reused_under_a_new_profile():
    """The same underlying data (product.judge_presentation.is_stale_for_profile)
    the dashboard's client-side staleness guard is built on: a result
    produced under one profile must never validate as current for another."""
    from product.judge_presentation import is_stale_for_profile

    result = demo.scenario_1_allow()
    model = build_presentation_model(result)
    assert model.profile == "knowledge_assistant-v1"
    assert is_stale_for_profile(model, "servicing-v1") is True
    assert is_stale_for_profile(model, "knowledge_assistant-v1") is False


def test_not_available_scenario_is_reported_for_every_profile():
    for profile in PROFILES:
        body = _run(profile["id"], 5)
        assert body["status"] == "NOT_AVAILABLE"
        assert "not currently implemented" in body["reason"]


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------


def test_receipt_verified():
    body = _run(HERO_PROFILE, 1)
    assert body["receipt_verification"] == "VERIFIED"


def test_receipt_tamper_is_detected_via_a_temporary_copy(tmp_path):
    """One byte flipped in a temporary copy of a real demo receipt — the
    canonical in-memory receipt this session produced is never touched."""
    result = demo.scenario_1_allow()
    receipt = copy.deepcopy(result.receipt)

    raw = json.dumps(receipt).encode("utf-8")
    tampered_path = tmp_path / "tampered_receipt.json"
    idx = raw.index(b"VERIFIED")
    tampered = bytearray(raw)
    tampered[idx] ^= 0x01
    tampered_path.write_bytes(bytes(tampered))

    tampered_receipt = json.loads(tampered_path.read_text(encoding="utf-8"))
    status = classify_receipt(
        tampered_receipt, expected_verdict=receipt["verdict"], expected_intervention=receipt["intervention"]
    )
    assert status == "TAMPERED"
    assert classify_receipt(
        receipt, expected_verdict=receipt["verdict"], expected_intervention=receipt["intervention"]
    ) == "VERIFIED"


def test_receipt_result_mismatch_is_surfaced():
    result = demo.scenario_1_allow()
    status = classify_receipt(result.receipt, expected_verdict="CONTRADICTED", expected_intervention="ALLOW")
    assert status == "RECEIPT / RESULT MISMATCH"


# ---------------------------------------------------------------------------
# Product semantics — BLOCK / ALLOW / ESCALATE, no confidence score
# ---------------------------------------------------------------------------


def test_block_renders_correctly():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    assert body["verdict"] == "CONTRADICTED"
    assert body["intervention"] == "BLOCK"
    assert body["execution_state"] == "PREVENTED"
    assert body["call_count"] == "0"


def test_allow_renders_correctly():
    body = _run(HERO_PROFILE, 1)
    assert body["verdict"] == "VERIFIED"
    assert body["intervention"] == "ALLOW"
    assert body["execution_state"] == "EXECUTED"
    assert body["call_count"] == "1"


def test_escalate_renders_correctly():
    body = _run("servicing-v1", 2)
    assert body["verdict"] == "SOURCE_UNRELIABLE"
    assert body["intervention"] == "ESCALATE"
    assert body["execution_state"] == "NOT_EXECUTED"


def test_verdict_intervention_execution_stay_distinct_fields():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    assert body["verdict"] != body["intervention"]
    assert body["intervention"] != body["execution_state"]


def test_no_confidence_score_is_fabricated_anywhere_in_the_response():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    blob = json.dumps(body)
    assert "confidence_score" not in blob
    assert "% confidence" not in blob
    for r in body["claim_evidence_rows"]:
        assert r["reliability"] in (
            "corroborated", "inferred", "unverified", "NOT AVAILABLE",
        )


# ---------------------------------------------------------------------------
# Determinism — repeated isolated RUN
# ---------------------------------------------------------------------------

_SUBSTANTIVE_FIELDS = (
    "scenario", "profile", "proposed_action", "ai_intent", "claim_evidence_rows",
    "policy_version", "policy_lines", "predicate_result", "verdict", "intervention",
    "root_cause", "reason_lines", "execution_state", "call_count",
    "receipt_verification", "idempotency_key", "evidence_origin", "unavailable_fields",
)


def test_double_run_is_substantively_deterministic():
    first = _run(HERO_PROFILE, HERO_SCENARIO)
    second = _run(HERO_PROFILE, HERO_SCENARIO)
    for field in _SUBSTANTIVE_FIELDS:
        assert first[field] == second[field], f"field {field!r} differs between runs"
    # trace_id is deterministic here too (fixed per scenario), but it is not
    # in the required substantive set — spot-check it separately.
    assert first["trace_id"] == second["trace_id"]


def test_run_concurrency_is_rejected_not_serialized_and_never_corrupts_a_result():
    """PRODUCT-04A (section 9): a duplicate RUN that arrives while another is
    still executing is REJECTED, not serialized/queued behind it — fixing
    the earlier behavior (this test previously asserted all 5 concurrent
    requests returned status "OK", i.e. every one of them executed). Fires
    several concurrent RUN requests for the replay scenario (which itself
    makes two real calls inside one RUN) and asserts exactly one executes;
    the rest are rejected with 409/RUN_IN_PROGRESS, never queued, never
    executed, never corrupting the one real result. See
    tests/test_product04a_hardening.py for the implementation-call-count
    oracle behind this same fix."""

    def _fire(_i):
        return client.post("/api/run", json={"profile_id": HERO_PROFILE, "scenario_index": 6})

    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(_fire, range(5)))

    oks = [r.json() for r in responses if r.status_code == 200]
    rejected = [r for r in responses if r.status_code == 409]
    assert len(oks) == 1, "exactly one concurrent RUN should execute, the rest must be rejected"
    assert len(rejected) == 4
    for r in rejected:
        assert r.json()["status"] == "RUN_IN_PROGRESS"

    body = oks[0]
    assert body["status"] == "OK"
    assert body["verdict"] == "VERIFIED"
    assert body["intervention"] == "ALLOW"
    assert body["execution_state"] == "REPLAYED"
    assert body["call_count"] == "1"


# ---------------------------------------------------------------------------
# CLI <-> dashboard consistency (section 37)
# ---------------------------------------------------------------------------


def test_cli_and_dashboard_agree_on_the_hero_scenario():
    dashboard_body = _run(HERO_PROFILE, HERO_SCENARIO)

    reset_execution_ledger()
    demo._call_log.clear()
    cli_result = demo.scenario_3_contradiction()  # exactly what product/judge_cli.py runs

    assert dashboard_body["ai_intent"] == cli_result.ai_intent
    assert dashboard_body["verdict"] == cli_result.verdict
    assert dashboard_body["intervention"] == cli_result.intervention
    assert dashboard_body["root_cause"] == cli_result.receipt.get("root_cause")
    assert dashboard_body["proposed_action"] == cli_result.receipt.get("action")
    assert dashboard_body["receipt_verification"] == "VERIFIED"
    assert cli_result.receipt_verified is True


# ---------------------------------------------------------------------------
# Passport <-> Inspector <-> Dashboard <-> Receipt consistency (section 38)
# ---------------------------------------------------------------------------


def test_passport_inspector_dashboard_and_receipt_agree():
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    passport, inspector = body["passport"], body["inspector"]

    assert body["verdict"] == passport["verdict"] == inspector["verdict"]
    assert body["intervention"] == passport["intervention"] == inspector["intervention"]
    assert body["execution_state"] == passport["execution_state"] == inspector["execution_state"]
    assert body["receipt_verification"] == passport["receipt_verification"] == inspector["receipt_verification"]
    assert body["trace_id"] == passport["trace_id"] == inspector["trace_id"]
    assert body["receipt_reference"] == passport["receipt_reference"] == inspector["receipt_reference"]
