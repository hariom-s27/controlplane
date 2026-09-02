"""PRODUCT-04A — targeted hardening fixes for the judge-facing dashboard
(demo/web.py, demo/static/app.js, demo/templates/index.html).

Scope (see the PRODUCT-04A task spec): these tests cover ONLY the blockers
this task exists to fix — autorun/refresh execution, duplicate-RUN
rejection, demo-local state isolation, dashboard reset, the error-leak
firewall, and the truthful receipt/runtime separation. They do not
re-litigate Product-01 (tests/test_judge_demo.py), Product-02
(tests/test_product02_judge_presentation.py), or Product-03's own existing
contract (tests/test_product03_dashboard.py) — those suites are re-run
unmodified (except for the one duplicate-RUN test whose expectations
encoded the pre-hardening "serialize" bug; see the comment on
test_run_concurrency_is_rejected_not_serialized_and_never_corrupts_a_result
in tests/test_product03_dashboard.py) to prove this task changed nothing
else about their behavior.

"Product-01 unchanged" / "Product-02 unchanged" (spec items 16-17) are
verified by running those suites unmodified and by `git diff --name-status`
showing zero changes under scripts/judge_demo.py, product/judge_*.py, and
controlplane/ — not by a bespoke test here, since there is no PRODUCT-04A
behavior change to assert in those files at all.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from controlplane.idempotency import reset_execution_ledger
from demo.web import _RUN_LOCK, app
from scripts import judge_demo as demo

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_ledger():
    reset_execution_ledger()
    demo._call_log.clear()
    yield
    reset_execution_ledger()
    demo._call_log.clear()


HERO_PROFILE = "knowledge_assistant-v1"
HERO_SCENARIO = 3  # RELIABLE CONTRADICTION — the real BLOCK+PREVENTED case


def _run(profile_id: str, scenario_index: int) -> dict:
    resp = client.post("/api/run", json={"profile_id": profile_id, "scenario_index": scenario_index})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Section 6/7/19 — autorun / refresh / query-param execution firewall
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", [
    "",
    "?autorun=1",
    "?scenario=3",
    "?profile=knowledge_assistant-v1&scenario=3&autorun=1",
])
def test_get_index_never_executes_regardless_of_query_params(monkeypatch, query):
    def _explode(*_a, **_k):
        raise AssertionError("GET / must never dispatch/decide, for any query string")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    resp = client.get("/" + query)
    assert resp.status_code == 200
    assert demo._call_log == []


def test_browser_refresh_causes_zero_additional_executions(monkeypatch):
    """A RUN followed by a simulated refresh (a fresh GET /) must not
    execute a second time — the page carries no server-side session that
    would replay the last RUN on load."""
    _run(HERO_PROFILE, HERO_SCENARIO)
    calls_after_run = len(demo._call_log)

    def _explode(*_a, **_k):
        raise AssertionError("GET / (refresh) must never dispatch/decide")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    resp = client.get("/")
    assert resp.status_code == 200
    assert len(demo._call_log) == calls_after_run


def test_served_javascript_has_no_autorun_trigger():
    """Regression guard for the removed client-side autorun (section 6):
    the served app.js must no longer read the autorun query parameter to
    fire a RUN on page load."""
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    js = resp.text
    assert 'get("autorun")' not in js
    assert "get('autorun')" not in js


# ---------------------------------------------------------------------------
# Section 9 — duplicate RUN is rejected, not serialized/coalesced
# ---------------------------------------------------------------------------


def test_concurrent_duplicate_run_is_rejected_with_exactly_one_execution():
    """Fires 5 concurrent identical RUN requests. Exactly one must execute
    (200/OK); the rest must be rejected outright (409/RUN_IN_PROGRESS) —
    never queued behind the first, never executed a second time, never
    mutating the winning result. Uses scenario 1 (ALLOW, RUNTIME) so a real
    implementation_call_count is directly observable (section 9's oracle).

    demo.SCENARIOS is a plain list (no .get()), so it is saved/restored by
    hand here rather than via monkeypatch.setitem, which requires a mapping.
    """
    calls: list[int] = []
    real_scenario = demo.SCENARIOS[0]

    def _counting_wrapper():
        calls.append(1)
        return real_scenario()

    demo.SCENARIOS[0] = _counting_wrapper
    try:
        def _fire(_i):
            return client.post("/api/run", json={"profile_id": HERO_PROFILE, "scenario_index": 1})

        with ThreadPoolExecutor(max_workers=5) as pool:
            responses = list(pool.map(_fire, range(5)))
    finally:
        demo.SCENARIOS[0] = real_scenario

    oks = [r for r in responses if r.status_code == 200]
    rejected = [r for r in responses if r.status_code == 409]
    assert len(oks) == 1, "exactly one concurrent duplicate RUN should execute"
    assert len(rejected) == 4, "every other concurrent duplicate RUN must be rejected"
    for r in rejected:
        body = r.json()
        assert body["status"] == "RUN_IN_PROGRESS"
        assert "ALREADY IN PROGRESS" in body["message"]
        assert "Traceback" not in body["message"]  # section 13, belt and braces

    assert len(calls) == 1, "implementation_call_count must increase exactly once (section 9 oracle)"
    assert len(demo._call_log) == 1

    ok_body = oks[0].json()
    assert ok_body["verdict"] == "VERIFIED"
    assert ok_body["intervention"] == "ALLOW"
    assert ok_body["execution_state"] == "EXECUTED"


def test_rejected_duplicate_run_does_not_touch_shared_state():
    """A rejected RUN must not reset the ledger, clear the call log, or
    otherwise mutate any state — it returns before touching anything."""
    _run(HERO_PROFILE, 1)  # establish a real result / non-empty call log
    calls_before = list(demo._call_log)

    assert _RUN_LOCK.acquire(blocking=False)  # simulate "a RUN is in flight"
    try:
        resp = client.post("/api/run", json={"profile_id": HERO_PROFILE, "scenario_index": 1})
        assert resp.status_code == 409
        assert resp.json()["status"] == "RUN_IN_PROGRESS"
        assert demo._call_log == calls_before
    finally:
        _RUN_LOCK.release()


def test_reset_is_also_rejected_while_a_run_is_in_flight():
    assert _RUN_LOCK.acquire(blocking=False)
    try:
        resp = client.post("/api/reset")
        assert resp.status_code == 409
        assert resp.json()["status"] == "RUN_IN_PROGRESS"
    finally:
        _RUN_LOCK.release()


# ---------------------------------------------------------------------------
# Section 10 — unrelated runs do not leak state
# ---------------------------------------------------------------------------


def test_unrelated_sequential_runs_do_not_leak_state():
    first = _run(HERO_PROFILE, 1)                # ALLOW
    second = _run(HERO_PROFILE, HERO_SCENARIO)    # CONTRADICTED / BLOCK

    assert first["idempotency_key"] != second["idempotency_key"]
    assert first["trace_id"] != second["trace_id"]
    assert first["verdict"] != second["verdict"]
    assert first["call_count"] == "1"
    assert second["call_count"] == "0"  # BLOCK never reaches the implementation
    assert second["receipt_reference"] != first["receipt_reference"]


# ---------------------------------------------------------------------------
# Section 11/12 — dashboard reset
# ---------------------------------------------------------------------------


def test_reset_clears_demo_local_state_and_executes_nothing(monkeypatch):
    _run(HERO_PROFILE, 1)
    assert demo._call_log  # sanity: there is state to clear

    def _explode(*_a, **_k):
        raise AssertionError("RESET must never dispatch/decide")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)

    resp = client.post("/api/reset")
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESET_OK"
    assert demo._call_log == []


def test_reset_only_touches_the_demo_local_decision_trail(tmp_path, monkeypatch):
    """Section 11/20: RESET must only ever remove the demo-local decision
    trail (decisions.jsonl / decisions_privileged.jsonl) — never a canonical
    fixture, gold/holdout file, or other repo source file. Redirects the
    trail paths into a tmpdir so this test proves what RESET deletes without
    depending on the real repo-root files' existence."""
    from controlplane import receipt as cp_receipt

    fake_op = tmp_path / "decisions.jsonl"
    fake_priv = tmp_path / "decisions_privileged.jsonl"
    fake_op.write_text("{}\n", encoding="utf-8")
    fake_priv.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cp_receipt, "OPERATIONAL_TRAIL", fake_op)
    monkeypatch.setattr(cp_receipt, "PRIVILEGED_TRAIL", fake_priv)

    resp = client.post("/api/reset")
    assert resp.status_code == 200
    assert not fake_op.exists()
    assert not fake_priv.exists()


def test_post_reset_run_remains_substantively_deterministic():
    """RUN, capture the substantive result, RESET, RUN the same scenario
    again — the substantive result must be unchanged (section 11's required
    flow)."""
    first = _run(HERO_PROFILE, HERO_SCENARIO)
    resp = client.post("/api/reset")
    assert resp.status_code == 200
    second = _run(HERO_PROFILE, HERO_SCENARIO)

    substantive = (
        "scenario", "profile", "proposed_action", "ai_intent", "claim_evidence_rows",
        "policy_version", "policy_lines", "predicate_result", "verdict", "intervention",
        "root_cause", "reason_lines", "execution_state", "call_count",
        "receipt_verification", "idempotency_key", "evidence_origin", "unavailable_fields",
    )
    for field in substantive:
        assert first[field] == second[field], f"field {field!r} changed after reset"


# ---------------------------------------------------------------------------
# Section 12/19 — Passport, Inspector, and receipt verification never execute
# ---------------------------------------------------------------------------


def test_passport_inspector_and_receipt_verification_never_execute_then_reset_is_clean(monkeypatch):
    """Runs the hero scenario once, then re-derives the Evidence Passport,
    Decision Inspector, and receipt verification from that SAME result
    (exactly what expanding those panels does client-side, with no further
    network call) with dispatch_tool/decide/extract_action/build_receipt
    monkeypatched to explode — proving none of the three re-executes
    governance — then RESETs, proving reset itself does not execute
    anything either."""
    from product.judge_presentation import build_presentation_model, classify_receipt
    from product.judge_views import decision_inspector, evidence_passport

    result = demo.scenario_1_allow()
    reset_execution_ledger()
    demo._call_log.clear()
    model = build_presentation_model(result)
    calls_before = len(demo._call_log)

    def _explode(*_a, **_k):
        raise AssertionError("presentation-only view must never call this")

    monkeypatch.setattr("controlplane.intercept.dispatch_tool", _explode)
    monkeypatch.setattr("controlplane.decide.decide", _explode)
    monkeypatch.setattr("controlplane.extract.extract_action", _explode)
    monkeypatch.setattr("controlplane.receipt.build_receipt", _explode)

    evidence_passport(model, expected_profile=HERO_PROFILE)
    decision_inspector(model, expected_profile=HERO_PROFILE)
    classify_receipt(result.receipt, expected_verdict=result.verdict, expected_intervention=result.intervention)

    assert len(demo._call_log) == calls_before

    resp = client.post("/api/reset")
    assert resp.status_code == 200
    assert demo._call_log == []


# ---------------------------------------------------------------------------
# Section 13 — error-leak firewall
# ---------------------------------------------------------------------------


SECRET = "SECRET_TEST_VALUE"
SECRET_PATH = r"C:\private\path"
SECRET_HEADER = "Authorization: test"


def test_raw_exception_content_never_reaches_the_http_response():
    def _boom():
        raise RuntimeError(f"{SECRET} leaked from {SECRET_PATH} with header {SECRET_HEADER}")

    original = demo.SCENARIOS[0]
    demo.SCENARIOS[0] = _boom
    try:
        resp = client.post("/api/run", json={"profile_id": HERO_PROFILE, "scenario_index": 1})
    finally:
        demo.SCENARIOS[0] = original

    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "SCENARIO_ERROR"
    assert body["message"] == "UNABLE TO COMPLETE DEMO RUN"

    raw = resp.text
    assert SECRET not in raw
    assert SECRET_PATH not in raw
    assert SECRET_HEADER not in raw
    assert "Traceback" not in raw


# ---------------------------------------------------------------------------
# Section 5 — receipt (decision-time, signed) vs runtime execution state
# ---------------------------------------------------------------------------


def test_receipt_verification_and_execution_state_are_never_conflated():
    """The signed receipt's verification outcome (a decision-time signature
    check) and the runtime execution outcome (a post-decision fact) are
    different questions and must stay in different fields — never collapsed
    into one combined label such as "RECEIPT VERIFIED EXECUTED" (section 5)."""
    block_body = _run(HERO_PROFILE, HERO_SCENARIO)  # BLOCK -> PREVENTED
    allow_body = _run(HERO_PROFILE, 1)               # ALLOW -> EXECUTED

    valid_verifications = {
        "VERIFIED", "TAMPERED", "VERIFICATION ERROR", "RECEIPT / RESULT MISMATCH", "NOT AVAILABLE",
    }
    valid_execution_states = {"EXECUTED", "PREVENTED", "REFUSED", "REPLAYED", "NOT_EXECUTED"}

    for body in (block_body, allow_body):
        assert body["receipt_verification"] in valid_verifications
        assert body["execution_state"] in valid_execution_states
        assert body["receipt_verification"] not in valid_execution_states
        assert body["execution_state"] not in valid_verifications


def test_execution_state_is_genuinely_absent_from_the_signed_receipt():
    """execution_state is computed from the runtime dispatch outcome, which
    happens strictly AFTER the receipt is built and signed
    (controlplane/intercept.py builds+signs the receipt, then dispatches).
    PRODUCT-04A represents this truthfully rather than fabricating an
    execution_state field onto the receipt to satisfy a UI consistency
    check (section 5): verdict/intervention are real shared fields and must
    agree between the receipt and the dashboard; execution_state is
    runtime-only and must not appear on the receipt at all."""
    body = _run(HERO_PROFILE, HERO_SCENARIO)
    result = demo.scenario_3_contradiction()
    reset_execution_ledger()
    demo._call_log.clear()
    receipt = result.receipt

    assert body["verdict"] == receipt["verdict"]
    assert body["intervention"] == receipt["intervention"]
    assert "execution_state" not in receipt
    assert "executed" not in receipt
