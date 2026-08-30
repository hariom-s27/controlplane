# P09 -- latency profile

Regenerate with `python bench/latency.py --write`. This report and `summary.json['p09_latency']` are the authoritative latency numbers; the older `summary.json['latency']` block (n=24) is a superseded interim.

## A. Measurement setup

- **Unit measured**: one intercept._run_gate() call: extract -> classify -> resolve -> predicate -> ground -> decide -> receipt, ending in a signed receipt persisted to an isolated decisions.jsonl. The downstream business tool is not invoked.
- **Workload**: P03 gold_set.jsonl (150 cases) in file order, cycled to n per config -> 1050 calls per configuration, identical across all four. Gold set SHA-256 `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e`.
- **Extraction**: stubbed to the pre-built ProposedAction per case (P04/P05/P08 convention). The 'extract' row is the gate's typed-object hand-off, NOT production extraction (one LLM call, CP_MODEL=Qwen/Qwen3-8B, temperature 0) nor the offline fixture read (~0.1-0.5 ms).
- **Clock**: frozen, CP_DEMO_DATE=2026-08-14. **Seed**: 20260814.
- **Timing**: time.perf_counter(), per stage inside _run_gate; end_to_end wraps the whole gate body.
- **Percentile method**: None
- **Concurrency**: concurrent.futures.ThreadPoolExecutor(max_workers=N). Threads, not processes: the pipeline is I/O-bound (SQLite + trail append) with a shared in-process HHEM model; the GIL is released during SQLite, file I/O and torch compute. Observed max concurrency is measured by sweep-line over per-call (enter, exit) perf_counter stamps.
- **Warm-up**: 50 calls per configuration, discarded. a fixed count of leading calls is executed and discarded, identical for all four configurations; it primes the Zen compiled-graph cache, SQLite, and (grounded configs) the first scored HHEM inference. No other observations are dropped; no outliers removed.
- **Grounding model**: `vectara/hallucination_evaluation_model` (controlplane.ground.preload() -- once, at process start, timed as cold start).
- **Runtime**: Python 3.14.3, torch 2.13.0+cpu, win32.
- **Frozen inputs unchanged during the run**: **True**.

**Stage boundaries** (each a `time.perf_counter()` block in `controlplane/intercept.py::_run_gate`; no stage is nested inside another):

| stage | starts | ends |
|---|---|---|
| extract | tool call in | typed `ProposedAction` returned (stubbed here) |
| classify | after extract | claims built + Checkability-Ladder tier/load-bearing assigned |
| resolve | after classify | every claim's `Evidence` resolved via its binding (live SQLite reads) |
| predicate | after resolve | Zen JDM graph evaluated over the resolved evidence |
| ground | after predicate | HHEM entailment score returned (only when C3 on and a clause-semantics claim exists) |
| decide | after ground | pure `decide()` returns the `Decision` |
| receipt | after decide | receipt built, HMAC-signed, and appended to the trail |
| **end_to_end** | tool call in | signed receipt persisted (spans all of the above **plus** manifest load/validate, `claim_specs`, the clause-match check and bookkeeping between stages) |

`end_to_end` is measured directly, not summed from stages, so the un-instrumented between-stage work (manifest YAML load + validation, `claim_specs`, `clause_matches_claim`) is visible as the gap `end_to_end - sum(stages)`.

## B. The four configurations

| config | C3 / HHEM | concurrency | n (timed) | warm-up discarded | observed max concurrency | wall clock (s) | throughput (calls/s) |
|---|---|--:|--:|--:|--:|--:|--:|
| C1_hhem_off_seq | off | 1 | 1050 | 50 | 1 | 9.057 | 115.9 |
| C2_hhem_on_seq | on | 1 | 1050 | 50 | 1 | 194.666 | 5.4 |
| C3_hhem_off_par | off | 10 | 1050 | 50 | 10 | 18.991 | 55.3 |
| C4_hhem_on_par | on | 10 | 1050 | 50 | 10 | 129.194 | 8.1 |

Configurations are **not** averaged together. Each is a separate >= 1,000-call distribution.

Intervention mix per config (same 1,050 inputs each): C1_hhem_off_seq -> {"ALLOW": 378, "BLOCK": 602, "ESCALATE": 70}; C2_hhem_on_seq -> {"BLOCK": 602, "ESCALATE": 448}; C3_hhem_off_par -> {"ALLOW": 378, "BLOCK": 602, "ESCALATE": 70}; C4_hhem_on_par -> {"BLOCK": 602, "ESCALATE": 448}. The C3-on configs escalate more: HHEM is an extra gate that fires on this workload's paraphrases. That is a verdict-semantics effect of `CP_GROUNDING=on` (by design, pre-P09), not a workload difference and not caused by the timing instrumentation -- `tests/test_latency.py` checks the receipt stays signed and the verdict is unchanged by the timing code.

## C. Stage percentile table (ms)

### C1_hhem_off_seq (C3 off, concurrency 1, n=1050)

| stage | n | p50 | p95 | p99 | max | mean | note |
|---|--:|--:|--:|--:|--:|--:|---|
| extract | 1050 | 0.00 | 0.00 | 0.01 | 0.03 | 0.00 | |
| classify | 1050 | 0.06 | 0.13 | 0.20 | 0.37 | 0.07 | |
| resolve | 1050 | 1.39 | 3.18 | 4.17 | 7.35 | 1.70 | |
| predicate | 1050 | 1.77 | 2.66 | 3.44 | 4.45 | 1.86 | |
| ground | 0 | - | - | - | - | - | grounding off |
| decide | 1050 | 0.11 | 0.20 | 0.30 | 0.49 | 0.12 | |
| receipt | 1050 | 0.67 | 1.22 | 1.57 | 2.13 | 0.76 | |
| _(between-stage)_ | 1050 | - | - | - | - | 3.91 | manifest YAML load+validate, claim_specs, clause-match, bookkeeping -- redone every call, not attributed to a stage |

### C2_hhem_on_seq (C3 on, concurrency 1, n=1050)

| stage | n | p50 | p95 | p99 | max | mean | note |
|---|--:|--:|--:|--:|--:|--:|---|
| extract | 1050 | 0.00 | 0.00 | 0.00 | 0.05 | 0.00 | |
| classify | 1050 | 0.14 | 0.20 | 0.35 | 1.11 | 0.15 | |
| resolve | 1050 | 4.02 | 5.42 | 8.08 | 11.81 | 4.16 | |
| predicate | 1050 | 3.24 | 4.44 | 7.90 | 18.55 | 3.44 | |
| ground | 1050 | 160.89 | 227.87 | 292.42 | 432.43 | 167.80 | |
| decide | 1050 | 0.20 | 0.29 | 0.42 | 1.74 | 0.21 | |
| receipt | 1050 | 1.33 | 1.85 | 2.56 | 5.41 | 1.39 | |
| _(between-stage)_ | 1050 | - | - | - | - | 7.92 | manifest YAML load+validate, claim_specs, clause-match, bookkeeping -- redone every call, not attributed to a stage |

### C3_hhem_off_par (C3 off, concurrency 10, n=1050)

| stage | n | p50 | p95 | p99 | max | mean | note |
|---|--:|--:|--:|--:|--:|--:|---|
| extract | 1050 | 0.00 | 0.00 | 0.01 | 0.03 | 0.00 | |
| classify | 1050 | 0.14 | 0.25 | 0.33 | 1.09 | 0.16 | |
| resolve | 1050 | 129.93 | 205.20 | 231.51 | 262.24 | 135.18 | |
| predicate | 1050 | 4.13 | 7.78 | 17.45 | 47.58 | 4.89 | |
| ground | 0 | - | - | - | - | - | grounding off |
| decide | 1050 | 0.20 | 0.34 | 0.51 | 1.51 | 0.22 | |
| receipt | 1050 | 21.17 | 57.70 | 77.64 | 96.45 | 24.75 | |
| _(between-stage)_ | 1050 | - | - | - | - | 14.79 | manifest YAML load+validate, claim_specs, clause-match, bookkeeping -- redone every call, not attributed to a stage |

### C4_hhem_on_par (C3 on, concurrency 10, n=1050)

| stage | n | p50 | p95 | p99 | max | mean | note |
|---|--:|--:|--:|--:|--:|--:|---|
| extract | 1050 | 0.00 | 0.00 | 0.01 | 0.02 | 0.00 | |
| classify | 1050 | 0.16 | 0.26 | 0.36 | 0.57 | 0.17 | |
| resolve | 1050 | 11.68 | 63.91 | 84.48 | 101.05 | 19.16 | |
| predicate | 1050 | 6.06 | 9.77 | 12.24 | 41.47 | 6.55 | |
| ground | 1050 | 1219.59 | 1550.21 | 1763.25 | 1840.32 | 1186.68 | |
| decide | 1050 | 0.26 | 0.39 | 0.48 | 2.82 | 0.28 | |
| receipt | 1050 | 2.53 | 13.74 | 24.04 | 31.59 | 4.07 | |
| _(between-stage)_ | 1050 | - | - | - | - | 10.44 | manifest YAML load+validate, claim_specs, clause-match, bookkeeping -- redone every call, not attributed to a stage |

## D. End-to-end percentile table (ms)

| config | C3 | concurrency | n | p50 | p95 | p99 | max | mean |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| C1_hhem_off_seq | off | 1 | 1050 | 7.67 | 12.65 | 14.52 | 26.47 | 8.42 |
| C2_hhem_on_seq | on | 1 | 1050 | 177.56 | 248.42 | 311.50 | 460.23 | 185.07 |
| C3_hhem_off_par | off | 10 | 1050 | 171.56 | 264.57 | 292.80 | 319.53 | 180.00 |
| C4_hhem_on_par | on | 10 | 1050 | 1264.81 | 1592.28 | 1813.41 | 1886.48 | 1227.36 |

## E. Cold-start measurement

- **HHEM one-time model load: 9163 ms** (9.16 s), measured on `C2_hhem_on_seq` via `controlplane.ground.preload()`.
- wall time of the one-time HHEM model load (controlplane.ground.preload). Excluded from every steady-state percentile below.
- C2, C4 (grounding on). N/A for C1, C3.
- The model is a module-global loaded exactly once per process (`controlplane/ground.py`, double-checked lock). It is **not** loaded per call; test `tests/test_latency.py` asserts this.

## F. Steady-state measurement

the n timed calls per configuration, after the fixed warm-up and after preload(); the model is already resident, so no call pays the cold start. Every percentile in sections C and D is steady-state. Cold start is never folded into them.

## G. C3 / HHEM contribution

- HHEM `ground` stage, sequential (C2): p50 **160.89 ms**, p95 **227.87 ms**, p99 **292.42 ms**, max **432.43 ms** over 1050 scored calls.
- End-to-end p50 with HHEM off (C1) = **7.67 ms**; with HHEM on (C2) = **177.56 ms**.
- End-to-end p99: C1 = **14.52 ms**, C2 = **311.50 ms**. End-to-end max: C1 = **26.47 ms**, C2 = **460.23 ms**.

**Finding: HHEM dominates the tail.** When C3 grounding is on, the HHEM entailment call is the single largest stage at p95/p99/max and drives end-to-end latency roughly an order of magnitude above the HHEM-off path. This is reported, not optimised away: C3 is optional coverage (`CP_GROUNDING=off` is the default), the verdict degrades to C1/C2 on timeout (P08 scenario 6), and the gate's own deterministic overhead is the HHEM-off number.

## H. Concurrency comparison

| pair | metric | concurrency 1 | concurrency 10 | direction |
|---|---|--:|--:|---|
| HHEM off (end_to_end) | p50 | 7.67 | 171.56 | worse under load |
| HHEM off (end_to_end) | p95 | 12.65 | 264.57 | worse under load |
| HHEM off (end_to_end) | p99 | 14.52 | 292.80 | worse under load |
| HHEM off (end_to_end) | max | 26.47 | 319.53 | worse under load |
| HHEM on (end_to_end) | p50 | 177.56 | 1264.81 | worse under load |
| HHEM on (end_to_end) | p95 | 248.42 | 1592.28 | worse under load |
| HHEM on (end_to_end) | p99 | 311.50 | 1813.41 | worse under load |
| HHEM on (end_to_end) | max | 460.23 | 1886.48 | worse under load |

- Observed max concurrency: C3 = 10, C4 = 10 (target 10). C1/C2 = 1/1 (sequential).
- Throughput: C1 115.9/s vs C3 55.3/s; C2 5.4/s vs C4 8.1/s.
- Same workload on both sides of every comparison (same 1,050 gold-case calls).

**Finding: concurrency=10 with in-process threads badly worsens per-call latency and barely helps throughput.** End-to-end p50 goes 7.7 -> 171.6 ms (22x) with HHEM off and 178 -> 1265 ms (7.1x) with HHEM on, while throughput moves only 116 -> 55/s (0.48x) and 5.4 -> 8.1/s. Attribution (HHEM off): the `resolve` stage p50 blows up 1.4 -> 130 ms (93x -- each gate call opens and closes a fresh SQLite connection per claim, and the surrounding Python is GIL-bound) and the `receipt` stage p50 goes 0.7 -> 21 ms (32x -- the trail-append lock serializes all ten workers). With HHEM on, the model call itself contends across the ten threads (161 -> 1220 ms). The gate re-loads and re-validates the manifest YAML on every call (the `end_to_end - Sigma(stages)` gap, ~3.9 ms/call at concurrency 1), which is also GIL-bound. P09 reports this as measured, not optimised: a real deployment would use process-level workers or async I/O, cache the manifest, and pool connections; this run measures the gate exactly as it stands under a thread pool, as the task specifies.

## I. AEGIS comparison

AEGIS 8.3 ms median over 1,000 interceptions (48 attacks / 500 benign). See the combined comparison line below.

## J. OAP comparison

OAP 53 ms median, N=1,000. See the combined comparison line below.

### Comparison line

> AEGIS 8.3 ms median (48 attacks / 500 benign / 1,000 interceptions); OAP 53 ms median (N=1,000); ControlPlane 7.67 ms median (**C1**: C3/HHEM off, concurrency 1, n=1050, end-to-end).

The ControlPlane figure quoted on this axis is the **C1 end-to-end p50** = 7.67 ms -- HHEM off, sequential -- because that is the configuration comparable to a median over mixed traffic with no grounding model. The HHEM-on numbers (C2/C4) are reported separately in sections C, D and G and are **not** blended into this line. For reference on the same axis: C2 (HHEM on, seq) end-to-end p50 = 177.56 ms, p95 = 248.42 ms.

## K. Honesty / limitations

- **Live database query.** Our figure includes a live SQLite read of the system of record on every call (the `resolve` stage) -- neither AEGIS nor OAP performs a source-of-record lookup. The comparison is **not like-for-like**. **Direction of bias: the live query makes our measured latency higher than it would be without that lookup.** This caveat explains the gap; it does not discount the measurement -- the lookup is the point of the architecture.
- **extract is stubbed** (see section A). Production extraction is one LLM call and would dominate a full agent-turn measurement; it is deliberately excluded because the gate's own overhead is what P09 measures (`docs/ROADMAP.md`: report the gate's latency excluding the agent's own model call).
- **Single machine, single run.** One host, one OS (see runtime above), one process. Percentiles are over calls, not over repeated runs; the workload is deterministic (fixed seed, frozen clock, deterministic HHEM classifier) so a re-run reproduces them closely modulo host scheduling noise.
- **Raw per-call observations are not stored** in `summary.json` (4 x ~1,050 x 8 numbers). `summary.json['p09_latency']` retains the unrounded percentiles; the full sample is reproduced by re-running the one command.
- **Threads, not processes.** True parallelism is bounded by the GIL between the C-extension release points; concurrency=10 measures the gate under a realistic in-process worker pool, not 10 isolated CPUs. See section H for the resulting per-call blow-up -- it is a real property of the gate as written (per-call manifest YAML re-parse, per-claim SQLite connect/close), reported, not tuned away.
- **The trail-append lock is a deliberate correctness/latency trade.** `controlplane/receipt.py` now serializes the `decisions.jsonl` append (P09 fires the gate from a thread pool; two interleaved writes would corrupt the trail -- and all 4400 persisted lines across the run parse cleanly). At concurrency 10 with sub-30 ms calls this adds ~21 ms of serialization to the `receipt` stage (C3); a persistent append handle would cut it, but that would break the per-test/per-config trail redirection P08/P09 rely on. It is visible in section C, not hidden.
- **Cold start is I/O-bound and noisy.** The one HHEM load measured 9.2 s in this run; separate loads this session ranged ~4.7-13.5 s depending on OS page-cache state. It is reported as a single measurement, kept entirely out of the steady-state tables.

## L. Exact reproduction command

```
python bench/latency.py --write
```

Deterministic inputs: `CP_DEMO_DATE=2026-08-14`, seed `20260814`, `CP_MODEL=Qwen/Qwen3-8B` (unused -- extract stubbed), grounding model `vectara/hallucination_evaluation_model` (no decoding params -- a classifier, greedy by construction), gold set `bench/gold_set.jsonl` SHA-256 `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e`, 1050 calls/config, 50 warm-up calls/config discarded.
