# P06 — External validation on tau2-bench (retail)

**Status: PROTOCOL LOCKED — C1 not yet run.** This section was written and
frozen at 2026-08-30T16:42:06Z, before any simulation in this experiment was
executed. Do not edit the sections below this line once C1 begins; append new
sections instead.

## Benchmark

- Repository: `sierra-research/tau2-bench` (external, third-party, unmodified)
- Pinned tag: `v1.0.1`
- Pinned commit: `fc0055dc4e0a316c3f83133267fbd6faaa770992` ("chore: prepare
  release v1.0.1 — banking_knowledge grading fixes (#408)")
- Checkout timestamp: 2026-08-30 (this session)
- Checkout location: `phase 2/external/tau2-bench/` — sibling to, and outside
  of, the ControlPlane git repository
- Retail domain: 114 base tasks (`data/tau2/domains/retail/tasks.json`),
  split into train=74 / test=40 (`split_tasks.json`)
- Retail write tools (7): `cancel_pending_order`,
  `exchange_delivered_order_items`, `modify_pending_order_address`,
  `modify_pending_order_items`, `modify_pending_order_payment`,
  `modify_user_address`, `return_delivered_order_items`
- Official evaluator: `tau2.evaluator.evaluator.evaluate_simulation`. Reward
  is the product of the components listed in each task's own
  `evaluation_criteria.reward_basis`; components not listed run as
  diagnostics only and do not gate the score. This experiment does not modify
  the evaluator, scorer, tasks, or policy in any way.
- Official pass^k: `pass_hat_k(n, c, k) = C(c, k) / C(n, k)` where `n` =
  trials, `c` = successes, `k` = k
  (`src/tau2/metrics/agent_metrics.py::pass_hat_k`, citing arXiv:2406.12045,
  the original τ-bench paper).

### Deviation log entry D1 — `docs/evaluation.md` vs. shipped `tasks.json` (repository-derived, not introduced by us)

`docs/evaluation.md` in tau2-bench v1.0.1 states the default `reward_basis`
for retail is `[DB, COMMUNICATE]` and that `NL_ASSERTION` is "not used at all"
in retail. Direct inspection of the shipped `data/tau2/domains/retail/tasks.json`
contradicts this: 112/114 retail tasks carry `reward_basis=[DB, NL_ASSERTION]`
(2/114 carry `[DB]` alone). Of those 112, 40 have non-empty `nl_assertions`
that trigger a real LLM-judge call inside `NLAssertionsEvaluator`; the other
72 have `nl_assertions=null` and vacuously score `NL_ASSERTION=1.0` with no
judge call (verified directly against `evaluator_nl_assertions.py`). This is
upstream documentation/data drift in the external benchmark itself — we did
not modify either file. Practical effect: tau2's own official retail score is
partly LLM-judged for ~35% of retail tasks (an external-benchmark property,
orthogonal to ControlPlane's own no-LLM-judge-on-critical-path design, which
governs the WRITE-interception decision, not tau2's reward computation).

## Experimental setup — LOCKED before C1

| Parameter | Value |
|---|---|
| Domain | retail |
| Task split | `test` (tau2's own held-out evaluation split; not selected post-hoc) |
| Task count (N) | 40 |
| Task IDs | `5, 9, 12, 17, 18, 26, 27, 32, 33, 36, 38, 39, 40, 42, 45, 49, 51, 53, 55, 56, 60, 61, 62, 64, 65, 68, 70, 71, 74, 77, 79, 86, 90, 94, 97, 100, 101, 102, 108, 111` |
| Benchmark-agent model | `featherless_ai/Qwen/Qwen3-8B` (`--agent-llm`) |
| User-simulator model | `featherless_ai/Qwen/Qwen3-8B` (`--user-llm`) — **deviation**: tau2's own default for this role is `gpt-4.1-2025-04-14`; substituted to reuse existing project credentials (no OpenAI key available). Held identical across C1/C2/C3. |
| Agent/user temperature | 0.0 / 0.0 (tau2 default — deterministic decoding) |
| Seed | 300 (tau2 default, `--seed 300`) |
| K (num-trials) | 1 |
| max-concurrency | 3 |
| max-steps | 200 (tau2 default) |
| max-errors | 10 (tau2 default) |
| max-retries | 3, retry-delay 1.0s (tau2 defaults) |
| Evaluation type (CLI) | `ALL_WITH_NL_ASSERTIONS` (tau2 CLI default — diagnostic action_checks always populated); **official score uses each task's own `reward_basis`**, per tau2's own documented distinction between diagnostic and official scoring |
| tau2 package version | 1.0.1 |
| litellm version | 1.81.11 |
| openai (litellm dep) version | 2.20.0 |
| Python | 3.12.14 (isolated `uv`-managed venv, since tau2-bench requires `<3.14` and this machine's default Python is 3.14.3) |
| Cost reporting | **Tokens, not dollars.** LiteLLM has no price-table entry for `featherless_ai/Qwen/Qwen3-8B` (`get_response_cost` logs "This model isn't mapped yet" and silently returns $0.0000 — confirmed during the pre-C1 dry-run below, this is a missing-data gap, not a real zero). Dollar cost is not claimed anywhere in this report. |
| Latency scope | ControlPlane gate overhead only (C2/C3), measured at `dispatch_tool` entry/exit. Tau2's own per-task `Duration` (agent+user LLM turns, evaluator) is reported separately and is not attributed to ControlPlane. |

### Pre-C1 dry-run (diagnostic only — NOT part of frozen C1 evidence)

A 2-task timed probe (`task-ids 5 9`, same model/seed/config as above,
`--max-concurrency 2`) was run before locking the above table, purely to
calibrate real wall-clock time before committing to a task-set size. Both
tasks completed normally (`TerminationReason.USER_STOP`, no infra errors on
the second attempt; a first attempt failed outright on a local `.env`-sourcing
bug unrelated to tau2 or Featherless, corrected before this run). Task 9:
145.73s. Task 5: succeeded on retry 1. Total wall-clock for both: 4m39s at
concurrency=2. Both scored `reward=0.0` (DB check failed on both) — not a
performance claim, n=2, purely a pipeline smoke test. These two outputs are
saved under `data/simulations/DRYRUN_2task_timing_probe_v2/` in the external
tau2-bench checkout and are excluded from every C1/C2/C3 metric in this
report.

## Addendum — safeguards applied during C1 (added 2026-08-30T16:53:41Z, C1 in progress, 8/40 tasks complete)

This section was added while C1 was running, per an explicit user instruction
to apply additional immutability/determinism safeguards without restarting,
resetting, or redefining the already-locked protocol above. Nothing in the
"Experimental setup — LOCKED before C1" table changed; this only adds
evidence and documentation.

**Determinism classification**: nominally deterministic by requested
configuration (temperature=0.0 for both agent and user-simulator roles,
tau2's own default), single seed (300), K=1 — matching tau2's own CLI
default and locked before C1 was observed. This is **not** independently
verified as bit-exact reproducible: Featherless is shared-batch GPU
inference infrastructure, and temperature=0.0 is not a guaranteed bit-exact
contract on such infrastructure. No repeated-trial uncertainty is manufactured
here — with a single locked seed by design, per-seed variation does not
apply.

**tau2-bench repository-integrity check** (re-run mid-C1): HEAD still
`fc0055dc4e0a316c3f83133267fbd6faaa770992`. `git status --short` showed one
worktree diff: `uv.lock`, a single self-referential line (tau2's own package
version string, `1.0.0` → `1.0.1`), auto-corrected by `uv sync` during initial
environment setup (before C1 began) to match the checked-out `pyproject.toml`.
Confirmed unrelated to and non-overlapping with retail task/policy/db/evaluator
content — see SHA-256 hashes in `bench/tau2_config_identity.json`, all
recorded directly from the live tau2-bench checkout while C1 was running.
Not reverted, per instruction not to restore/revert automatically; disclosed
here instead.

**Machine-readable configuration identity**: `bench/tau2_config_identity.json`,
written while C1 was running, holds the full locked configuration (commit,
model, seed, decoding, task set, run settings, initial-state mechanism,
integrity hashes) in one artifact shared verbatim across C1/C2/C3 except the
`conditions` block.

**Initial-state proof**: the static `db.json` driving every task's fresh
environment is hash-recorded above. The per-task *target* DB-state hash
(computed by tau2's own evaluator by replaying `evaluation_criteria.actions`
on a fresh environment) is produced at evaluation time, not run time — `tau2
run` alone leaves `reward_info: null` in raw results (confirmed by direct
inspection of `C1_vanilla_baseline/results.json` mid-run). This will be
captured immediately after C1 finishes and re-verified identical per task_id
across C2/C3.

## C1 — Vanilla baseline

### Attempt 1 — ABORTED (disclosed deviation, logged here rather than hidden)

Launched 2026-08-30 with `--max-concurrency 3` (tau2's own CLI default).
Stopped deliberately at 16:xx UTC after 8/40 tasks completed, of which only
3/8 (37.5%) succeeded normally; the other 5/8 failed with
`litellm.RateLimitError: Featherless_aiException — Concurrency limit
exceeded` (account plan cap: 4 concurrent units; each tau2 task can need 2
concurrent Featherless slots — agent + user-simulator, both
`featherless_ai/Qwen/Qwen3-8B` — so `--max-concurrency 3` could demand up to
6 slots against a 4-slot plan). This is a structural oversubscription, not a
transient blip: tau2's internal per-task retry (`max_retries=3`) does not
help when the account stays oversubscribed for the retry too, so affected
tasks were trending toward permanent `infrastructure_error` (excluded from
tau2's own scoring automatically, per `agent_metrics.get_metrics_df`, but
shrinking valid N well below 40).

Partial data from this aborted attempt is preserved, not deleted, at
`data/simulations/C1_ABORTED_concurrency3_rate_limited/` in the external
tau2-bench checkout (renamed from its original `C1_vanilla_baseline` save
path for clarity). It is excluded from all C1 metrics in this report.

**Why abort rather than let it finish**: the same oversubscription would
have had to be avoided for C2/C3 anyway for the three conditions to be
comparable, so finishing this attempt at concurrency=3 would not have
produced a usable, complete baseline and would still have required a
concurrency change for the other two conditions — an asymmetry not worth
accepting when a clean restart was available. Stopping and restarting a
not-yet-complete, not-yet-frozen C1 attempt is not the same as overwriting
frozen C1 evidence (section 11's protection applies once C1 is complete and
frozen, which this attempt never reached).

### Attempt 2 — concurrency corrected

Same configuration as the locked protocol table above, with one change:
`--max-concurrency 1` (down from 3), safely under the account's 4-unit plan
cap even accounting for 2 Featherless slots per task. Save path:
`C1_vanilla_baseline` (the original name, now free). All other locked
parameters (model, seed, task set, decoding, K) are unchanged from the
original lock.

STATUS: about to be (re)launched.

## C2 — ControlPlane + fresh policy

STATUS: PENDING — requires `bench/tau2_adapter.py` and
`manifests/tau2_retail.yaml`, not yet built as of this lock.

## C3 — ControlPlane + stale policy context

STATUS: PENDING.

Stale-snapshot candidate identified during preflight (not yet applied):
`sierra-research/tau-bench` (the tau2-bench predecessor repo), commit
`c86a7604176864bc590703523e3b3e780cc0169f` (2024-07-25), file
`tau_bench/envs/retail/wiki.md`. This is a real, dated, externally-published
prior version of the retail policy document — substantively different from
tau2-bench v1.0.1's `policy.md` (confirmed by direct diff), not a fabrication.
Retail's `policy.md` inside tau2-bench itself has never changed (single
"release" commit in its own history), so no in-repo prior version exists;
this predecessor-repo snapshot is the legitimate alternative the task's own
rules allow ("a real previous policy state OR an explicitly documented
historical snapshot").

## Protected-artifact hashes (ControlPlane side)

Recorded 2026-08-30T16:30:05Z, before this file was created. All 21 hashes
matched the values already recorded in `docs/onboarding-measurement.md` —
nothing had drifted. Full list preserved in this session's scratchpad
(`p06_preflight_snapshot.txt`); will be re-verified after C1/C2/C3.

ControlPlane HEAD at lock time: `8a48bf7ac4a20d8d57c9fc86ac47de6eb784971e`
(branch `p03-m4-blind-human-label-sheet`). Working tree has substantial
uncommitted P02/P04/P05/P07/P08/P09/onboarding work at lock time, by the
user's explicit choice not to checkpoint-commit before P06; hash-freezing is
the operative integrity mechanism instead (consistent with
`docs/onboarding-measurement.md`'s own approach).
