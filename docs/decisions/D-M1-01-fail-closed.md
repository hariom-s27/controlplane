# D-M1-01 — The gate fails closed on missing evidence

| | |
|---|---|
| Date | 2026-11-13 |
| Status | Accepted, implemented on branch `m1-fail-closed` (base `eed05d9`) |
| Scope | `controlplane/` engine, `schemas/manifest.schema.json`, all 10 manifests, tests, docs |
| Protected files changed by this decision | `controlplane/intercept.py`, `controlplane/manifest.py`, `tests/test_manifest_hardening.py` |
| Integrity record | `docs/p06-post-p02-integrity.sha256` is **not** edited here; a v2 record follows in the next task and must cover all three files above |

## Decision

The gate never executes an action when the evidence it needs is missing,
unavailable or failed. No manifest value can configure execution on missing
evidence.

## Why

The project claims the gate is "designed to fail closed on missing data".
Audits P01/P02 found three paths, plus one path that needed checking, where
the code at `eed05d9` did not behave that way:

| # | Path at `eed05d9` | Behaviour |
|---|---|---|
| 1 | `controlplane/intercept.py:89-92`, `:125` (reached from `:210-222`) | `SourceUnavailable` with `fail_posture: open` → `Intervention.ALLOW`, outcome `"permitted"`; `:338-351` then relabelled the receipt `posture_outcome="executed"`. knowledge_assistant (`risk_tier_default: 0`, `tier_0: open`) executed `send_document` with no entitlement evidence. |
| 2 | `controlplane/intercept.py:420-429`, `controlplane/escalation.py:82` | Escalation budget exhausted with posture `open` → the original call executed; trail event `outcome: "executed"`. |
| 3 | `controlplane/decide.py:369-378` | `POLICY_CLAUSE_CURRENT` with `clause_match=None`, or `CLAUSE_SEMANTICS_MATCH` with `grounding_score=None`, was skipped silently and could end VERIFIED → ALLOW. With grounding on, an `ImportError` (`intercept.py:254-255`) gave no signal, and a timeout (`:256-262`) degraded to the C1/C2 verdict. |
| 4 | `decide.py:427` + `knowledge_assistant.yaml` `UNVERIFIABLE: allow_with_caveat` | → `Intervention.MODIFY`. **Did not execute**: `decide()` never sets `modified_args`, and `dispatch_tool` raises `Pending` for a non-dict (`intercept.py:402-408`). Removed anyway (R4) because the name promises execution and a held `Pending` is never queued for review. |

## What changed

| Rule | Change |
|---|---|
| R1: source unavailable | `fail_posture` per tier is now `closed` (BLOCK) or `escalate` (ESCALATE: held in `pending_actions.jsonl`, BLOCK once the escalation budget is exhausted). `open` is removed. The 10 manifests' `tier_0: open` became `escalate`. Active postures: knowledge_assistant tier 0 = `escalate`; all others are `closed` on their active tier, so their outage behaviour is unchanged (servicing still BLOCKs). `_execute_governed_once` now refuses any decision whose `failure_context.kind` is `source_unavailable` (defence in depth). |
| R2: budget exhausted | Always BLOCK. The configured posture is recorded in the trail event but never consulted. `record_budget_exhaustion` writes `outcome: "blocked"` unconditionally. |
| R3: missing check input | `POLICY_CLAUSE_CURRENT` with `clause_match=None` → UNVERIFIABLE (reason `clause_current_available`). C3 grounding: **off by configuration** → verdict unchanged, and the ledger row stays MODELLED + eligible + `UNVERIFIED` with reason `c3_off_by_configuration`. **On but failed** (ImportError, timeout, no clause text, no score) → UNVERIFIABLE (reason `clause_semantics_match_available`), ledger `UNAVAILABLE` / `c3_checker_failed`, `component_status.C3` names the cause. A C1/C2 hard contradiction still wins the verdict. Non-timeout grounding errors stay loud. |
| R4: verdict_handling | `allow_with_caveat` is removed from the schema for both UNVERIFIABLE and SOURCE_UNRELIABLE. knowledge_assistant uses `escalate`. `decide()` no longer reads `verdict_handling`: those verdicts always ESCALATE (BLOCK when compensability is `not`), so even a hand-built manifest dict cannot yield MODIFY. The dispatch-boundary MODIFY guards are kept and tested. |
| R5: schema/loader | The schema enum for `fail_posture.tier_*` is `["closed","escalate"]`. The loader and `active_fail_posture` reject `open` / `allow_with_caveat` with an error naming this decision. `FailureContext.fail_posture` still *reads* `"open"` so receipts written before this decision parse. The `fail_posture` key and its shape are unchanged. |

### `decide()` signature change

`decide(..., grounding_state: str = "off")` is a new keyword argument. The
caller at the I/O boundary (`intercept._run_gate`) passes `"off"`, `"scored"`
or `"failed"`. The default is `"off"` so that direct callers (B4/B5 in
`bench/baselines.py`, the mutation and invariant harnesses) keep their
behaviour. Any other default would have turned all 150 gold cases'
`CLAUSE_SEMANTICS_MATCH` claims into failures. `decide()` remains pure.
`tests/test_no_protected_attributes.py` pins the parameter set and now lists
`grounding_state`; the protected-token check still runs on every parameter.

### Other code

- `scripts/judge_demo.py`: notes for scenarios 4/5 updated. `_run_dispatch` now labels a returned `{"status": "pending"}` as PENDING, not EXECUTED.
- `tests/conftest.py` (new): every test's trail, privileged trail and review queue (including the import-time path defaults in `escalation.py` and `telemetry.py`) go to `tmp_path`. A session guard fails the run if the repo-root runtime files change.
- `.gitignore`: `pending_actions.jsonl`.

## Tests whose expectations changed

| Test | Was | Now | Why |
|---|---|---|---|
| `test_knowledge_assistant.py::test_knowledge_source_outage_uses_configured_escalate_posture` (was `…_open_posture`) | executes, ALLOW | pending, not executed, ESCALATE | R1 |
| `test_failure_injection.py::test_p08_record_unavailable_knowledge_honours_escalate_posture_and_marks_unverified` (was `…_open_posture…`) | executed, `fail_posture=open`, `posture_outcome=executed` | pending, 1 queued, `escalate` / `escalated` | R1 |
| `test_cid_regressions.py::test_gate_honors_configured_source_unavailability_posture` | `open→ALLOW` | `escalate→ESCALATE` (`closed→BLOCK` kept) | R1/R5 |
| `test_escalation.py::test_budget_exhausted_blocks_even_with_legacy_open_posture_for_tier_zero` (was `…_uses_open_posture…`) | `"executed"` | `Blocked`, posture recorded | R2 |
| `test_failure_injection.py::test_p08_grounding_timeout_is_unverifiable_and_marks_c3_unavailable` (was `…_degrades_to_c1_c2…`) | VERIFIED / ALLOW | UNVERIFIABLE / ESCALATE | R3, reverses the P08 "timeout degrades to C1/C2" choice |
| `test_cid_regressions.py` MODIFY helper (`:194-195`) | `decide()` → MODIFY | `decide()` → ESCALATE; MODIFY decision built directly for the 4 guard tests | R4 |
| `test_judge_demo.py:79, :89`, `test_product03_dashboard.py:470` | `MODIFY` | `ESCALATE` | R4 |
| `test_manifest_hardening.py::test_lint_is_read_only_no_execution_no_writes` | watched repo-root `decisions.jsonl` | watches the per-test trail | no test reads the repo-root trail |
| `test_no_protected_attributes.py::test_decide_signature_takes_no_protected_attribute_parameter` | 10 parameters | + `grounding_state` | signature change above |

`test_failure_injection.py::test_p08_record_unavailable_servicing_honours_closed_posture` is **unchanged**: servicing still BLOCKs on an outage.

**New tests:**
- `tests/test_fail_closed_m1.py`: schema/loader rejection, migration of all 10 manifests, grounding off/failed, the clause_match rule, R1/R2 at dispatch, the execution guard, MODIFY-without-args, and a receipt tamper test on `verification_coverage` only.
- M6 in `tests/test_invariants.py` and `docs/invariants.md`, as Hypothesis properties at the `decide()` and `dispatch_tool()` levels over 10 manifests × tier × posture × budget × fault.

Run against the `eed05d9` engine, 44 of the 51 new or changed test IDs fail and 7 pass. The 7 are deliberate pins of unchanged behaviour (closed posture still BLOCKs, a C1/C2 contradiction still wins, a real grounding score is honoured, the tamper and MODIFY guards). M6 on the old engine finds the original flaw on its own (`discount_approval`, tier 0, `open`, source unavailable → executed).

## Measured effect

**Full suite** (fresh copy, keys unset): `1 failed, 713 passed`. The one failure is the known, pre-existing `test_tau2_c2_controlplane_side.py::test_post_p02_integrity_record_accounts_for_one_authorized_change`. Baseline before this decision: 673 passed / 1 failed (same test).

**Headline (R6)**, B4/B5 on the 140 non-ambiguous cases of `bench/gold_set.jsonl`, offline, old vs new engine:

| | old (`eed05d9`) | new |
|---|---|---|
| B5 direction accuracy | 100.0% | 100.0% |
| B4 direction accuracy | 87.9% | 87.9% |
| discordant (B5 right / B4 right) | 17 (17 / 0) | 17 (17 / 0) |
| McNemar exact p | 1.53e-05 | 1.53e-05 |

No case changed direction, and no intervention label changed on any of the 150 cases for either system.

**Latency C1** (HHEM off, sequential, n = 1,050, 50 warm-up; `bench/latency.py::run_config`), old and new run in one session in A-B-B-A order. End-to-end, ms:

| run | p50 | p95 | p99 |
|---|---|---|---|
| old (1st) | 65.98 | 92.82 | 117.61 |
| new (1st) | 41.77 | 93.95 | 121.44 |
| new (2nd) | 73.68 | 93.23 | 125.55 |
| old (2nd) | 47.37 | 78.50 | 98.64 |

Which side is faster depends on run order, not code. The machine in this session was several times slower than when `reports/latency.md` recorded 7.67 / 12.65 / 14.52 ms, so those figures were **not** reproduced here and are not restated by this decision. Every run produced the same intervention distribution (ALLOW 378, BLOCK 602, ESCALATE 70) with all signatures valid. `reports/latency.md` is unchanged.

## Known limitations (unchanged by this decision)

- **15 of the 150 gold cases have no asserted policy version** (`claimed_policy_version` is None). For them `clause_matches_claim` returns True (`controlplane/predicates/__init__.py:128-130`, "no assertion is not a mismatch"), so `POLICY_CLAUSE_CURRENT` passes rather than being UNVERIFIABLE. R3 covers a missing *check result* (`clause_match=None`), not a missing *agent assertion*. Changing this is a separate decision.
- With grounding off (the default), `CLAUSE_SEMANTICS_MATCH` is not checked, and the B5 headline treats it as such. The ledger reports it as `UNVERIFIED` / `c3_off_by_configuration`, never `VERIFIED`.
- An `escalate` posture still reduces service: actions wait for a reviewer, and BLOCK once the budget is used. tau2 manifests have no `escalation_budget_pct` (0), so any ESCALATE there ends in BLOCK.
- `bench/failure_injection.py` scenarios 2 and 6 still expect the old knowledge-outage and grounding-timeout outcomes, so their self-checks would report a failure if re-run. `reports/robustness.md` is unchanged. `docs/ROADMAP.md` (historical spec) still mentions fail-open and `allow_with_caveat`.

## Deferred

- **Engine path binding.** `controlplane/escalation.py` (`escalation_budget_exhausted`, `enqueue_pending`, `record_budget_exhaustion`, `pending_items`, `record_review`) and `controlplane/telemetry.py::latency_percentiles` bind their file paths as default arguments at import time, so patching a module attribute does not redirect them. `tests/conftest.py` works around this. Making these resolve their paths at call time is a separate refactor.
- The v2 integrity record covering `controlplane/intercept.py`, `controlplane/manifest.py` and `tests/test_manifest_hardening.py`.
