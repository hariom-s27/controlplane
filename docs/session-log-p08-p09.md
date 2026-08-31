# Session Log — P08 Completion & Freeze Audit, P09 Latency Profile

**Repository:** `phase 2/controlplanestarter/controlplane` (ControlPlane — Accenture Innovation Challenge 2026, Round 2)
**Scope of this file:** everything requested and completed in this chat session, in order. Written so the work can be reviewed on GitHub without replaying the conversation.
**Status of underlying work:** all described below is implemented in the working tree and verified by the test runs and hash checks quoted in this file. Nothing here is a projection or a plan — every number quoted was measured in this session.

---

## Table of contents

1. [Part A — P08 continuation (robustness & failure injection)](#part-a)
2. [Part B — P08 freeze audit (read-only)](#part-b)
3. [Part C — P09 latency profile](#part-c)
4. [Consolidated files changed](#files-changed)
5. [Consolidated test results](#tests)
6. [Key numbers — quick reference](#numbers)
7. [Known limitations / residuals](#limitations)

---

<a id="part-a"></a>
## Part A — P08 continuation (robustness & failure injection)

### A.0 Starting state

A prior agent ("Codex") had implemented most of P08 (`doc/task/P08-robustness.txt`) and hit a usage limit mid-task. The instruction for this session was explicit: **continue from the current worktree, do not reset/revert/restart, preserve P01–P05 frozen work.**

Reported starting state:
- P08 preflight complete; Scenario 1 (wrong-record) corruption grid locked: 21 points, 0.00–1.00 step 0.05, deterministic SHA-256 record ranking, comparator = frozen P04 B4 binary accuracy = 123/140 = 0.8785714286.
- Pre-fix diagnostic findings already captured for scenarios 2, 3, 5, 6, 8 (record outage escaping silently, NULL `delivered_at` raising `RuntimeError`, duplicate current-policy row silently accepted, HHEM timeout escaping, same idempotency key executing twice).
- `tests/test_failure_injection.py` reported at "10 passed" for the parts already built.
- Two **P05** isolation tests were reported failing because a new SQLite source layer opened stores with a `?mode=rw` URI suffix, which broke P05's frozen `sqlite3.connect` spy (`tests/test_evidence_ablation.py::test_isolation_probe_A5_only_the_live_stores`).

### A.1 Recovery / inspection

Before any change: inspected `git status`, `git diff`, and every file named in the handoff (`controlplane/registry/sqlite_source.py`, `errors.py`, `idempotency.py`, `schema.py`, `registry/orders.py`, `registry/entitlements.py`, `registry/policy.py`, `predicates/__init__.py`, `decide.py`, `receipt.py`, `telemetry.py`, `manifest.py`, `intercept.py`, `tests/test_failure_injection.py`).

Finding: the reported P05 regression was **already resolved** in the on-disk `sqlite_source.py` — `connect_readwrite()` does a `path.is_file()` existence check (raising typed `SourceUnavailable` for a missing/replaced store) and then a **plain** `sqlite3.connect(path)` with no URI suffix, so `Path(target).name` stays `orders.db` / `policy_store.db` for the P05 spy. Verified by running `tests/test_evidence_ablation.py` (25 tests, all pass) before touching anything.

### A.2 A regression I found and fixed: `decide()` purity

Running the full suite before any edits surfaced one real failure:

```
FAILED tests/test_no_protected_attributes.py::test_decide_signature_takes_no_protected_attribute_parameter
AssertionError: decide() grew unexpected parameter(s): {'idempotency_key_override', 'component_status'}
```

`decide()` is a hard-constraint pure function (CLAUDE.md rule 4) — no I/O, no clock, no hidden inputs, and a structural test pins its exact parameter list. Codex's in-progress edit had added two parameters to thread operational context through it.

**Fix (minimal, no test weakened):** removed both parameters from `decide()`; `intercept._run_gate()` now sets `decision.component_status` and a caller-supplied `decision.idempotency_key` on the **returned** `Decision` object, after `decide()` returns — at the I/O boundary, not inside the pure core. `decide()`'s signature is back to exactly the 10 parameters the structural test expects. `tests/test_no_protected_attributes.py` was **not edited**.

### A.3 A bug I found and fixed: Windows SQLite connection leak in the P08 harness

First run of `bench/failure_injection.py` failed every scenario with `PermissionError [WinError 32]` at `TemporaryDirectory` cleanup. Root cause: `sqlite3.connect(...) as conn` only manages a *transaction* in Python's sqlite3 module — it never closes the connection. On Windows, the leaked handle keeps the cloned `.db` file locked, so cleanup fails.

**Fix:** wrapped every `sqlite3.connect(...)` in the bench harness (`_clone_store`, `_eligible_dates`, `_corrupt_dates`, the NULL-field and ambiguous-policy fixture setup) in `contextlib.closing(...)`. All 8 scenarios then ran clean.

### A.4 The eight scenarios — implemented, measured, and verified

All scenarios run the **real** `controlplane.intercept._run_gate()` path (never a synthetic shortcut), with every mutable store cloned into an isolated `tempfile.TemporaryDirectory` and every process global (`decisions.jsonl` trail, escalation queue, execution ledger, clock) redirected and restored in a `finally` block.

| # | scenario | pre-fix finding | post-fix result |
|--:|---|---|---|
| 1 | **Wrong record** | No crash — gate trusted the corrupted date and blocked (reported as a **limitation**, not a win) | Directed witness (`ORD-10227`, in-window) blocked at `root_cause=outside_window` after `delivered_at` is set 8 days early. Crossover measured at **10.6%** record-error rate (see §A.5). |
| 2 | **Record unavailable** | Both SQLite outages escaped dispatch with no signed receipt; no fail posture applied | servicing (`orders.db`, tier 2) → fails **closed**, not executed; knowledge_assistant (`entitlements.db`, tier 0) → fails **open**, executes, receipt `verification_state="unverified"`. Postures come from the manifest YAML, not a hardcode. |
| 3 | **NULL field** | Orders resolver returned NULL as corroborated/HIGH; Zen date coercion raised an uncaught `RuntimeError` | `delivered_at=NULL` → `SOURCE_UNRELIABLE` → `ESCALATE`, no exception, signed receipt records the NULL. |
| 4 | **Inferred field, high severity** | No production resolver path existed for an inferred field on a load-bearing claim | Real `order_status` column (genuinely `inferred` in `orders.db`'s `field_reliability` table, seeded from a USPS OIG finding) → `SOURCE_UNRELIABLE` → `ESCALATE`. No hand-built Evidence shortcut. |
| 5 | **Ambiguous policy** | `PolicyResolver` used `fetchone()`, silently accepted one of two current rows | `.fetchall()` + hard raise (`AmbiguousPolicyState`) on >1 current row → fail **closed**, logged data-quality event. |
| 6 | **Grounding timeout** | `TimeoutError` escaped the grounding stage, no receipt produced | Caught; `component_status.C3 = {status: unavailable, reason: timeout}`; verdict degrades to C1/C2 only; non-timeout errors still propagate loudly. |
| 7 | **Tampered receipt** | Only in-memory tamper detection was tested | A real persisted receipt is reloaded from disk, edited, and re-verified: `verify()` goes `True → False`. |
| 8 | **Retry / idempotency** | Deterministic key was metadata only; two dispatches executed the tool twice | Caller times out *after* commit, retries with the same key → tool executes **once**, retry replays the stored result, signed replay receipt (`failure_context.kind=idempotent_replay`). |

### A.5 Wrong-record corruption grid — the headline limitation number

- **Method:** fixed 21-point grid (0.00→1.00, step 0.05), locked before any result was seen. Records ranked by `SHA256("p08-wrong-record-v1|order_id")`; point *k* selects the nested prefix of `floor(rate·85+0.5)` date-bearing `orders.db` records; each selected `delivered_at` is flipped across the frozen v4.2 seven-day boundary. Every point runs on its own SQLite clone through the real gate; scored on the P04 binary-direction estimand over the 140 non-ambiguous P03 gold cases.
- **Comparator:** frozen P04 B4 TraceGrounded = 123/140 = 0.8785714286.
- **Crossover:** first grid point strictly below B4 = **10.6%** (achieved rate 0.10588, accuracy 0.8357 = 117/140). Cluster bootstrap (5,000 iters, seed 20260814) over public source-order clusters: median 10.6%, 95% interval **[10.6%, 44.7%]**.
- **Framing:** reported explicitly as a **limitation** — "we do not claim to catch a wrong record; we claim to be exactly as right as the record, and here is the rate at which that stops being good enough."

### A.6 Deliverables written

- **`bench/failure_injection.py`** — finalized with `--write` flag; generates `reports/robustness.md` and merges `summary.json['p08_robustness']` without touching any other key.
- **`reports/robustness.md`** — result table (scenario / expected / observed / pass-fail / receipt excerpt), the full 21-point crossover curve, per-scenario pre-fix-vs-post-fix detail with signed-receipt JSON excerpts (raw `sig` hex stripped — it covers wall-clock `latency_ms` and isn't reproducible byte-for-byte; `signature_valid` is kept).
- **`docs/limitations.md`** — new sections: *"We inherit the system of record's errors"* (crossover ≈10.6%, USPS OIG 2.45% context) and *"What SOURCE-UNRELIABLE does and does not cover"* (explicit does/does-not lists, including the idempotency-ledger durability gap).
- **`reports/summary.json['p08_robustness']`** — crossover number, full curve, per-scenario results, frozen-input-integrity flag.
- **`.gitignore`** — added `!reports/robustness.md` (was previously excluded by the blanket `reports/*` ignore).
- **`Makefile` / `make.ps1`** — new `robustness` target.

### A.7 Test results (Part A)

- `tests/test_failure_injection.py` — **10 passed**.
- `tests/test_no_protected_attributes.py`, `tests/test_evidence_ablation.py` (25), `tests/test_baselines.py` (18) — all pass after the `decide()` fix.
- Full suite: **225 passed, 0 failed**.
- `bench/failure_injection.py` (no args): `all_pass: true`, `frozen_input_integrity.unchanged: true`.

---

<a id="part-b"></a>
## Part B — P08 freeze audit (read-only)

A second request asked for a **read-only audit** of the completed P08 work against the authoritative `doc/task/P08-robustness.txt` — no file edits, no re-running the experiment, no report regeneration.

### Method

Re-inspected every scenario from the *actual current files* (not from memory of Part A): `bench/failure_injection.py`, `tests/test_failure_injection.py`, `reports/robustness.md`, `docs/limitations.md`, `reports/summary.json`, and the full runtime path (`intercept.py`, `decide.py`, `receipt.py`, `errors.py`, `idempotency.py`, `sqlite_source.py`, `registry/{orders,policy,entitlements,freshness}.py`, `manifest.py`, `predicates/__init__.py`, `ladder.py`, both manifest YAMLs). Ran the test suite (this is neither an edit nor a re-run of the experiment).

### Verdicts

| requirement | verdict |
|--:|---|
| Wrong record — grid locked / comparator 123/140 / first-below crossover / reported as limitation | **PASS** |
| Record unavailable — per-manifest source, configured posture, no cross-dependency, unverified receipt | **PASS** (with a noted, pre-approved interpretation: fail-posture keys on the manifest's *tier*, not literally on compensability — transparently documented in the report itself) |
| NULL field — no RuntimeError, SOURCE_UNRELIABLE produced | **PASS** |
| Inferred field — real resolver path, INFERRED → SOURCE_UNRELIABLE → ESCALATE, no shortcut | **PASS** |
| Ambiguous policy — no silent row selection, fail closed, data-quality event | **PASS** |
| HHEM timeout — C3 unavailable recorded, C1/C2 distinguishable, non-timeout stays loud | **PASS** |
| Tampered receipt — persisted-receipt reload rejected by signature validation | **PASS** |
| Idempotency — at-most-once, timeout/retry covered, durability limitation documented | **PASS** |
| `robustness.md` / `limitations.md` / `summary.json` deliverables | **PASS** |
| P03 / P04 / P05 frozen integrity | **PASS** |
| No fault-injected DB in repo / no tests weakened / honest pytest | **PASS** |

**Conclusion returned: "P08 SAFE TO FREEZE."**

---

<a id="part-c"></a>
## Part C — P09 latency profile

Third request: implement `doc/task/P09-latency.txt` exactly as specified — an honest latency profile, not a favorable number, with an explicit instruction to report unfavorable findings (HHEM dominating the tail, concurrency hurting the tail) rather than hide or tune them away.

### C.0 Preflight (read-only, reported before any edit)

- **Existing timing:** `intercept._run_gate()` already timed 6 of 7 required stages (extract, classify, resolve, predicate, ground, decide) with `time.perf_counter()`. Missing: a `receipt` stage timer and any true `end_to_end` measurement (the existing report script faked end-to-end as `sum(stages)`, which misses real between-stage work).
- **Grounding load:** `controlplane/ground.py` already loaded the HHEM model once, lazily, on first call — but at *first call*, not *process start*. Measured (diagnostic, single call): import ~1.5 ms, cold load ~4.7 s, warm scored call ~38 ms (on short strings — real gold-set clause text scores higher, see below). Model is cached locally and loads fully offline.
- **Call path:** P08's pattern — call `intercept._run_gate()` directly with `extract_action` stubbed to a pre-built `ProposedAction` — was reused as "the gate."
- **Concurrency-safety gaps found:** `receipt.persist()` had **no lock** on the `decisions.jsonl` append (a real corruption risk under a 10-worker thread pool); `ground._load()` had a first-call race if 10 threads triggered the model load simultaneously.
- **A landmine found (unrelated to P09 but load-bearing):** `bench/report.py::main()` **overwrote** `summary.json` wholesale, which would have **destroyed** `p04_baselines` / `p05_evidence_ablation` / `p08_robustness` if anyone ran `make report`. Hardened to merge (see below); not executed during this session.
- **Old claim status:** "75% of traffic finishes in 1–20 ms" was already labelled "design target" / "retired" / "interim" everywhere it appeared (`docs/ROADMAP.md` ×3, `docs/retired-figures.md`) — no artifact stated it as a current fact. No blockers found.

### C.1 Implementation

- **`controlplane/intercept.py`** — added `gate_t0` at the top of `_run_gate`; a `_with_totals()` helper builds a **new** timing dict carrying `receipt` and `end_to_end` in addition to the 6 existing stages. Critical detail: the signed receipt holds a *reference* to the original 6-key `latency_ms` dict and its HMAC is computed over it — so the two after-the-fact totals must never be written into that same object, or the persisted receipt's signature would silently stop matching its content. Verified by a dedicated test (`test_timing_leaves_the_signed_receipt_consistent_and_verdict_unchanged`).
- **`controlplane/receipt.py`** — added a `threading.Lock` around the trail-file append (JSON serialization stays outside the lock; only the write is serialized).
- **`controlplane/ground.py`** — added `preload()` (forces the one-time load at process start), `is_loaded()`, and a double-checked `_load_lock` so a 10-worker pool's first grounded call doesn't trigger 10 redundant model loads.
- **`bench/report.py`** — changed `main()` from overwrite to read-merge-write for `summary.json`; its own thin latency table now writes to `reports/latency_trail.md` instead of clobbering P09's `reports/latency.md`.
- **New `bench/latency.py`** (~780 lines) — the harness. Four configurations, `ThreadPoolExecutor(max_workers=10)` for the concurrent ones, a thread-local stub extractor (concurrency-safe, no `_run_gate` signature change), nearest-rank percentiles (`pXX = sorted[ceil(XX/100·n)-1]`, no interpolation), a sweep-line concurrency verifier, and a merge-safe `summary.json['p09_latency']` writer with the same sibling-preservation guard pattern as P08.
- **New `tests/test_latency.py`** (16 tests) — the 12 required proofs (stage instrumentation, non-negative timings, model-loaded-once via a fake loader, configs kept separate, concurrency=10 verified via a small real run, all percentile fields present, `summary.json` preserves P04/P05/P08, old claim absent, cold/steady distinct, timing code proven not to mutate the signed receipt or the decision).

### C.2 A measurement-integrity incident, caught and corrected

The first full run was launched with `nohup ... &`, which appeared to exit immediately; a second run was then launched believing the first had died. **Both ran concurrently**, contending for CPU for the full ~10-minute measurement. This was caught because the harness's own `frozen_input_integrity` check flipped to `False` (each run observed `reports/summary.json` mutate mid-run — the other run's write) and the two runs' numbers disagreed materially (15.67 ms vs 19.51 ms for the same configuration).

**Resolution:** both contaminated runs were discarded. Confirmed no stray process remained, then ran **one single, solo** measurement. That run reported `frozen_input_integrity.unchanged: true` throughout, and its numbers are what is reported below and committed to `reports/latency.md` / `summary.json`.

### C.3 Final measured results (the clean, uncontaminated run)

**Setup:** unit = one `intercept._run_gate()` call (extract→classify→resolve→predicate→ground→decide→receipt, signed + persisted). Workload = the full 150-case P03 gold set, file order, cycled ×7 = **1,050 calls per configuration**, identical across all four. **50 calls/config warm-up, discarded**, identical policy. Frozen clock `CP_DEMO_DATE=2026-08-14`, seed `20260814`. Extraction stubbed (P04/P05/P08 convention) — the `extract` row measures only the gate's typed-object hand-off, not the LLM call or the fixture read. Runtime: Python 3.14.3, torch 2.13.0+cpu, Windows.

**End-to-end (ms):**

| config | C3/HHEM | concurrency | n | p50 | p95 | p99 | max | throughput |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| **C1** | off | 1 | 1050 | **7.67** | 12.65 | 14.52 | 26.47 | 115.9/s |
| **C2** | on | 1 | 1050 | 177.56 | 248.42 | 311.50 | 460.23 | 5.4/s |
| **C3** | off | 10 | 1050 | 171.56 | 264.57 | 292.80 | 319.53 | 55.3/s |
| **C4** | on | 10 | 1050 | 1264.81 | 1592.28 | 1813.41 | 1886.48 | 8.1/s |

**Stage p50 (ms), C1 (HHEM off, sequential — the headline config):**

| extract | classify | resolve | predicate | decide | receipt | (un-instrumented gap*) |
|--:|--:|--:|--:|--:|--:|--:|
| 0.00 | 0.06 | 1.39 | 1.77 | 0.11 | 0.67 | ~3.9 mean |

\* manifest YAML load + validation + `claim_specs` + clause-match, redone every call — visible only as `end_to_end − Σ(stages)`, ~47% of C1's end-to-end mean.

**Cold start:** HHEM one-time model load = **9,163 ms (9.2 s)**, measured on C2, excluded from every steady-state number (noisy across the session: 4.7 s–13.5 s depending on OS page cache).

**Finding — HHEM dominates the tail:** `ground` stage (C2) p50 **160.89 ms**, p95 227.87, p99 292.42, max 432.43 — **91% of C2's end-to-end**. End-to-end p50 goes 7.67 → 177.56 ms (23×) turning grounding on. Reported as measured, not hidden or tuned: `CP_GROUNDING=off` is the project default; C3 degrades to C1/C2 on timeout (P08 scenario 6).

**Finding — concurrency=10 badly worsens per-call latency and barely helps throughput:**

| | concurrency 1 → 10 | multiplier | throughput 1 → 10 |
|---|--:|--:|--:|
| HHEM off, end-to-end p50 | 7.67 → 171.56 ms | **22×** | 115.9 → 55.3/s (halved) |
| HHEM on, end-to-end p50 | 177.56 → 1264.81 ms | **7.1×** | 5.4 → 8.1/s |

Attribution: `resolve` p50 blows up 1.4 → 130 ms (93×) — every gate call opens/closes a fresh SQLite connection per claim, and the surrounding Python is GIL-bound; `receipt` p50 goes 0.7 → 21 ms (32×) — the new trail-append lock serializes all 10 workers; with HHEM on, the model call itself contends across the 10 threads. Observed max concurrency was verified at 10 (sweep-line over per-call enter/exit timestamps) — this is real 10-way execution, not accidental serialization; the *latency* cost, not the concurrency mechanism, is the finding. Reported as a real property of the gate as currently written; a production deployment would use process-level workers, async I/O, manifest caching, and connection pooling — none of that was retrofitted here, because the point of P09 is to measure the system as it stands.

### C.4 Required comparison line

> **AEGIS 8.3 ms median (48 attacks / 500 benign / 1,000 interceptions); OAP 53 ms median (N=1,000); ControlPlane 7.67 ms median (C1: C3/HHEM off, concurrency 1, n=1,050, end-to-end).**

ControlPlane's median sits essentially at AEGIS's and well under OAP's. The HHEM-on and concurrency-10 numbers are reported separately (§C.3) and are **not** blended into this line.

**Required caveat, stated verbatim in `reports/latency.md`:** *"Our figure includes a live database query that neither cited system performs, so the comparison is not like-for-like."* **Direction of bias, stated explicitly:** the live SQLite read (the `resolve` stage, p50 1.39 ms in C1) makes our measured number **higher** than it would be without it — the caveat explains the gap, it does not discount the measurement, because that lookup is the entire point of the architecture.

### C.5 Old claim removal

"75% of traffic finishes in 1–20 ms" was searched across `README.md`, `docs/**`, `reports/**` (no deck/slide files exist in the repo). Found only in `docs/ROADMAP.md` (3 places) and `docs/retired-figures.md` (1 row) — all already labelled retired/interim, now updated to **cite the measured 7.67 ms** and point at `reports/latency.md` in past tense instead of "P09 will replace it." `README.md`'s HHEM paragraph updated to the measured numbers. A dedicated test (`test_old_latency_claim_is_not_a_current_factual_claim`) scans all current artifacts and asserts no unlabelled occurrence remains.

### C.6 Deliverables written

- **`bench/latency.py`** — the harness, with `--write` to persist the report + merge summary.json, `--smoke` for a fast (non-committable) wiring check.
- **`reports/latency.md`** — full report: measurement setup, all four configs' stage and end-to-end percentile tables, cold-start vs steady-state, the HHEM finding, the concurrency finding, the comparison line + caveat, honesty/limitations, exact reproduction command.
- **`reports/summary.json['p09_latency']`** — exact (unrounded) percentiles per stage per config, cold start, workload/seed/model metadata, reproduction command. Every pre-existing key (`p04_baselines`, `p05_evidence_ablation`, `p08_robustness`, and all others) verified byte-identical.
- **`docs/ROADMAP.md`**, **`docs/retired-figures.md`**, **`README.md`** — old-claim references updated to the measured result.
- **`.gitignore`** — added `!reports/latency.md`.
- **`Makefile` / `make.ps1`** — new `latency` target.

### C.7 Test results (Part C)

- `tests/test_latency.py` — **16 passed** (all 12 required proofs).
- Full suite: **241 passed, 0 failed** (225 + 16 new).
- `git diff --check` clean for every P09 file (two pre-existing "blank line at EOF" flags remain on the *frozen* `reports/baselines.md` / `reports/evidence-ablation.md` — not P09's doing, hashes unchanged).

---

<a id="files-changed"></a>
## Consolidated files changed (this whole session)

**New:**
- `bench/latency.py`, `tests/test_latency.py`, `reports/latency.md` (P09)
- (P08's `bench/failure_injection.py`, `tests/test_failure_injection.py`, `controlplane/errors.py`, `controlplane/idempotency.py`, `controlplane/registry/sqlite_source.py`, `reports/robustness.md` were already present from the prior session and continued here.)

**Modified:**
- `controlplane/decide.py` — reverted 2 added params, restored purity (Part A)
- `controlplane/intercept.py` — field-setting moved out of `decide()` (Part A); `gate_t0` / `_with_totals()` for `receipt` + `end_to_end` timing (Part C)
- `controlplane/receipt.py` — `threading.Lock` around the trail append (Part C)
- `controlplane/ground.py` — `preload()`, `is_loaded()`, `MODEL_NAME`, double-checked `_load_lock` (Part C)
- `bench/failure_injection.py` — Windows `contextlib.closing` fix, `--write` report generation (Part A)
- `bench/report.py` — merge instead of overwrite `summary.json`; `latency.md` → `latency_trail.md` (Part C)
- `reports/summary.json` — `+p08_robustness` (Part A), `+p09_latency` (Part C); every other key byte-identical throughout
- `docs/limitations.md` — P08 sections added (Part A)
- `docs/ROADMAP.md`, `docs/retired-figures.md`, `README.md` — old-latency-claim references updated (Part C)
- `.gitignore` — `!reports/robustness.md` (Part A), `!reports/latency.md` (Part C)
- `Makefile`, `make.ps1` — `robustness` target (Part A), `latency` target (Part C)

---

<a id="tests"></a>
## Consolidated test results

| checkpoint | result |
|---|---|
| `tests/test_failure_injection.py` | 10 passed |
| `tests/test_latency.py` | 16 passed |
| `tests/test_no_protected_attributes.py` | passed (after the `decide()` purity fix) |
| `tests/test_baselines.py` (P04) | 18 passed |
| `tests/test_evidence_ablation.py` (P05) | 25 passed |
| Full suite, end of Part A | 225 passed |
| Full suite, end of Part C | **241 passed, 0 failed** |
| `bench/failure_injection.py` | `all_pass: true` |
| `bench/latency.py --write` (clean run) | `frozen_input_integrity.unchanged: true` for all 4 configs |
| `git diff --check` | clean on every file this session touched |

**P03 / P04 / P05 / P08 frozen-artifact integrity, verified by hash before and after every write in this session:**
`bench/gold_set.jsonl`, `ground_truth_holdout.jsonl`, `human_label_sample.csv` (P03); `bench/baselines.py`, `reports/baselines.md` (P04); `bench/evidence_ablation.py`, `reports/evidence-ablation.md` + both PNGs (P05); `bench/failure_injection.py`, `reports/robustness.md`, `docs/limitations.md` (P08) — **all unchanged**. `summary.json`'s `p04_baselines` / `p05_evidence_ablation` / `p08_robustness` subtrees are byte-identical to their pre-P09 state; only `p09_latency` was appended.

---

<a id="numbers"></a>
## Key numbers — quick reference

| metric | value |
|---|---|
| P08 wrong-record crossover | **10.6%** record-error rate (95% CI [10.6%, 44.7%]) |
| P08 scenarios passing | 8 / 8 |
| P09 headline latency (C1: HHEM off, seq) | **median 7.67 ms**, p95 12.65 ms, p99 14.52 ms, max 26.47 ms |
| P09 vs AEGIS / OAP | AEGIS 8.3 ms · OAP 53 ms · **ControlPlane 7.67 ms** (not like-for-like — see caveat) |
| HHEM `ground` stage (C2, seq) | p50 160.89 ms, p95 227.87 ms, p99 292.42 ms, max 432.43 ms |
| HHEM cold start | 9.16 s (one-time, excluded from steady-state) |
| Concurrency=10 impact (HHEM off) | end-to-end p50 **22×** worse, throughput **halved** |
| Concurrency=10 impact (HHEM on) | end-to-end p50 **7.1×** worse |
| Full test suite | 241 passed, 0 failed |

---

<a id="limitations"></a>
## Known limitations / residuals (carried forward honestly, not hidden)

**From P08:**
- The verifier inherits the system of record's errors by design; SOURCE-UNRELIABLE does not catch a record that is present, well-formed, corroborated, and simply wrong.
- SOURCE-UNRELIABLE does not cover semantic staleness (a technically-current row that is operationally out of step), corruption of non-load-bearing claims, or non-availability-class SQLite errors (those stay loud on purpose).
- The idempotency execution ledger is in-process only — no durability across a process restart.
- Five permission-locked temporary directories from a *previous* agent session remain under the OS temp folder, outside the repository and inaccessible to this session; harmless, not part of the repo.

**From P09:**
- The comparison to AEGIS/OAP includes a live database query neither of those systems performs (biases our number upward — stated explicitly, not used to discount the measurement).
- `extract` is stubbed to isolate the gate's own overhead from LLM-call latency; production extraction (one Featherless API call) is not part of this profile.
- Single machine, single measurement run; deterministic workload (fixed seed, frozen clock, deterministic HHEM classifier) makes it reproducible modulo host scheduling noise.
- The concurrency=10 latency blow-up is a real, reported property of the gate as currently written (per-call manifest YAML re-parse, a fresh SQLite connection per claim per call, and the newly-added trail-append lock) — not tuned away, per the task's explicit instruction.
- Raw per-call timing observations are not persisted in `summary.json` (would be ~4 × 1,050 × 8 numbers); the exact percentiles and full reproduction metadata are, and the one documented command reproduces the sample.

---

*This file is a record of what was done and measured in this chat session. It contains no secrets, API keys, or receipt-signing material.*
