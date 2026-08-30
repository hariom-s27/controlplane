# P05 methodology audit — evidence-source ablation (A1–A5)

**Conclusion up front: no concrete methodology defect was found in the
current implementation. No repair was made. No experiment was rerun.** This
document records the audit that reached that conclusion, independently, from
the primary source and the actual code — not from the existing report's own
prose.

## LedgerAgent — verified from the primary source (arXiv:2606.20529)

Read directly from `arxiv.org/html/2606.20529` (Method and Experiments).

| Item | Finding | Category |
|---|---|---|
| Does the verifier query an external/current store at decision time? | **No.** The ledger "stores the portion observed through tools in a domain schema. It is not long-term memory, an LLM summary, a per-task checklist, or a claim to recover unobserved world state." | PAPER-DERIVED |
| Or does it verify structured state already accumulated by the agent? | **Yes** — "successful read-tool returns are deterministically absorbed into a schema-anchored dictionary keyed by canonical paths," and the policy gate "uses only records present in the ledger." | PAPER-DERIVED |
| Is that state derived from prior tool observations / execution trace? | Yes, explicitly — the ledger is populated only by the agent's own prior tool-call returns. | PAPER-DERIVED |
| Baseline | Standard prompt-based function-calling (FC): state reconstructed from the transcript each turn, no separate policy gate. | PAPER-DERIVED |
| Treatment | LedgerAgent: a typed ledger (schema-anchored dict of prior tool observations) + a policy gate (predicates over ledger fields) evaluated before any environment-mutating call, with outcomes `allow` / `revise` / `block`. | PAPER-DERIVED |
| Held constant | "Both conditions use the same policy, tools, conversation history, decoding settings, and number of model calls." Temperature 0.0; a fixed GPT-5-mini user simulator. | PAPER-DERIVED |
| Task/domain counts | 4 domains: Airline (τ²-bench, 50 tasks), Retail (τ²-bench, 114), Telecom (τ²-bench, 114), Telehealth (τ-Trait, 20). 298 tasks total. | PAPER-DERIVED |
| Independent trials | 4 trials per task per domain–model–agent cell, for pass^1 / pass^4 consistency; decoding is temperature-0.0 (deterministic per call), so the 4 trials are not independent-of-noise statistical draws in the classical sense — they measure multi-turn interaction variance with the LLM simulator, not sampling variance. | PAPER-DERIVED |
| Reported metrics | pass^1, pass^4. Results are mixed across domains — e.g. Airline FC 54.4%→Ledger 62.3% (+7.9pp), but Telecom FC 80.9%→Ledger 69.9% (**−11.0pp**, worse under the treatment). Also compared against a separate "IRMA" baseline. | PAPER-DERIVED |

**What is genuinely reusable for P05, and what is not:**

- Reusable: the core structural distinction — verify against state the agent
  itself already observed, vs. verify against a live external query — maps
  directly onto P05's A3 (trace-only) vs. A5 (live-query) split.
- Reusable: the control-variable discipline ("same policy, tools, decoding
  settings, number of model calls") is exactly what P05 lists under
  Controls, and is verified below to actually hold in code.
- **Not reusable, and not used:** LedgerAgent's own numbers. `reports/evidence-ablation.md`
  and `bench/evidence_ablation.py` use ControlPlane's own gold set, own gold
  labels (`bench/label.py`), and own task distribution throughout — no
  LedgerAgent number appears anywhere in P05's results.
- **Not reusable:** treating repeated runs as independent statistical
  trials the way LedgerAgent's pass^k does. `decide()` is a pure,
  deterministic function (established elsewhere in this repo); P05's 3
  seeds select *which cases* are perturbed at a given fraction (a
  sensitivity range over perturbation-subset choice), not repeated
  stochastic trials — `reports/evidence-ablation.md` reports them as
  `mean [min, max]`, never as a confidence interval derived from repeated
  sampling of a random process. This is the methodologically correct framing
  and was verified, not assumed.

## A1–A5 — actual provenance, verified against source code (not names)

Read directly from `bench/evidence_ablation.py` and `bench/baselines.py`.

| Arm | What it actually reads (verified in code) | Verified against |
|---|---|---|
| A1 MessageOnly | `case['_message']` only — synthetic customer-message fixture | `MessageOnlyStrategy.resolve` |
| A2 RetrievedOnly | `case['_retrieval']` only — retrieved clause + order-snapshot chunk | `RetrievedOnlyStrategy.resolve` |
| A3 TraceOnly | `case['_trace']` only, via `_trace_result()`, which scans the trace list for a matching `get_order`/`get_policy` step's recorded result | `TraceOnlyStrategy.resolve`, `bench/evidence_ablation.py:629-666` |
| A4 CachedRead | `sqlite3.connect(REPLICA_ORDERS)` + `sqlite3.connect(self._policy_path)` — a **separate file**, `_replica/orders.db` and `_replica/policy_store_asof_200ms.db`, never `data/orders.db` / `data/policy_store.db` | `CachedReadStrategy.resolve`, `bench/evidence_ablation.py:669-709` |
| A5 LiveQuery | `resolve_bindings(...)` + `sqlite3.connect(POLICY_DB)` against the live `data/` stores; the `case` parameter (which carries `_message`/`_retrieval`/`_trace`) is accepted by the shared method signature but **never referenced in the method body** | `B.LiveQueryStrategy.resolve`, `bench/baselines.py:195-217` — `class LiveQueryStrategy(B.LiveQueryStrategy): name = "A5_live_query"` with **no overridden `resolve`**, i.e. A5 executes the byte-identical B5 code, not a re-implementation |

### A3 status: genuinely trace-only — CONFIRMED

- Reads only `case['_trace']`. No `case['_message']`, no `case['_retrieval']`,
  no `claimed_*` field, no `sqlite3`, no `resolve_bindings`, no `REPLICA`,
  `ORDERS_DB`, or `POLICY_DB` token anywhere in `TraceOnlyStrategy`'s source
  — enforced both at runtime (`isolation_probe`, a `sqlite3.connect` spy that
  records zero DB opens for A3) and statically (`assert_isolation`'s
  source-token ban over `inspect.getsource(TraceOnlyStrategy)`, which is a
  **hard gate**: `raise SystemExit` on violation, not a warning).
- `absence` for A3 means the agent's trace never contains a `get_order` step
  (that call didn't happen) — not text deleted from a message
  (`test_a3_absence_is_not_prose_deletion`).
- Verified structurally sound: `tests/test_evidence_ablation.py::test_isolation_probe_A1_A2_A3_open_no_database`,
  `test_assert_isolation_gate_passes`, `test_source_level_channel_isolation`,
  `test_a3_reads_the_trace_and_its_boundaries` — all pass.

### A4 status: genuine point-in-time replica — CONFIRMED, with an honest disclosed gap

- Queries a **separate replica database file** (`_replica/orders.db`,
  `_replica/policy_store_asof_200ms.db`), built once by
  `build_replica()`/`_policy_snapshot()` as an actual point-in-time snapshot
  — not a live query plus a `sleep()`, not a live query with a synthetic
  timestamp field rewritten. `test_a4_replica_is_a_real_point_in_time_snapshot`
  and `test_a4_latency_floor_is_not_a_sleep_and_alters_no_value` pass.
- Structurally isolated from the live stores: `isolation_probe` records A4
  opening only `orders.db` (the replica copy) and `policy_store_asof_200ms.db`,
  never `data/policy_store.db`.
- **Can A4 diverge from A5?** Yes — proven, not merely claimed, by
  `replication_lag_sensitivity()`: at a replication lag ≥ 14 days the
  replica predates the 2026-08-01 policy cutover and serves the superseded
  v3.8/30-day clause while A5 serves v4.2/7d, costing 11.4 accuracy points
  (100.0% → 88.6%). At the arm's *specified* 200 ms lag, the snapshot is
  taken 200 ms before decision time against a store whose last write is 13
  days old, so **on this specific frozen dataset** the 200 ms read happens
  to return the same values as live — this is disclosed as a **measured
  property of the frozen dataset**, not asserted as a general property of
  200 ms replication lag. The headline claim was accordingly narrowed from
  an earlier ("freshness costs 11.4 points") overclaim to "this benchmark
  isolates independence, not freshness, at 200 ms" — see § Prior repair
  history below.
- "Stale" is defined precisely: the wall-clock offset between the replica
  snapshot instant and decision time (`CDC_LAG_MS`, 200 ms in the five-arm
  grid; swept explicitly in the lag-sensitivity table at 0/1/7/13/14/30/90
  days).

### A5 status: genuine live query — CONFIRMED

- `A5 = P04's B5` is not a naming claim — it is structurally the same
  Python object: `LiveQueryStrategy(B.LiveQueryStrategy)` with no overridden
  `resolve`, so A5 executes `bench.baselines.LiveQueryStrategy.resolve`
  unchanged. `test_a5_is_p04_b5_verbatim` asserts this by AST comparison.
- Queries `data/orders.db` (via `resolve_bindings`, the same registry path
  the real gate uses) and `data/policy_store.db` live, at decision time.
  Never reads `case['_message']`/`_retrieval`/`_trace` (parameter accepted,
  never dereferenced — confirmed by direct source read above).
- Isolation confirmed: `isolation_probe` records A5 opening only
  `orders.db`/`policy_store.db`, and explicitly asserts the A4 replica file
  is never opened by A5 (`assert_isolation`).

## Control-variable audit

| Control | Held constant? | Evidence |
|---|---|---|
| Same gold case | Yes | All five arms are scored against the same 150-case `bench/gold_set.jsonl` list, loaded once (`B.load_cases()`) |
| Same proposed tool call | Yes | `test_perturbation_never_touches_gold_toolcall_or_stores` — the tool-call args are never touched by `build_view`'s perturbation |
| Same policy | Yes | Same manifest thresholds (`window_days`, `authority_ceiling_paise`) for every arm |
| Same decision logic | Yes | All five arms call `_run_pipeline(case, strategy)` → `bench.baselines._run_our_pipeline` **unchanged** — `test_one_shared_runner_delegating_to_p04` |
| Same evaluator | Yes | Same `decide()` / same verdict-accuracy scoring against the same `bench/label.py` gold labels |
| Same number of "model calls" | N/A — deterministic pipeline, no LLM call inside the scored path | `_run_our_pipeline` is pure Python + SQLite/Zen, not an LLM-in-the-loop for this measurement |
| Same perturbation grid | Yes | Full cross: 5 arms × 6 absence points × 5 staleness points × 3 seeds = 450 cells, `test_full_grid_shape` |
| Gold labels untouched by any arm/perturbation | Yes | `test_p03_gold_set_hash_is_unchanged` — the frozen gold set's SHA-256 is checked, not just assumed |
| The only varied input is the evidence source | Yes | `test_strategy_registry_entries_are_bare_classes`, `test_predict_all_varies_only_the_strategy` |

## Context-quality conditions actually exercised

- **Current/complete**: absence=0%, staleness=0% — the origin point. A3=A5 (both 100.0%): both arms agree, inherited evidence is correct.
- **Missing** (absence sweep, 10/30/50/70/100%): inherited arms (A1/A2/A3) degrade monotonically; both independent arms (A4, A5) stay flat at 100.0%.
- **Stale** (staleness sweep, 10/25/50/100%): same pattern — inherited arms degrade, independent arms flat.
- **Stale, independent arm** (replication-lag sensitivity, A4 only): genuine divergence demonstrated at lag ≥ 14 days.
- **Conflicting**: not a separately swept condition in this design — the staleness sweep is the closest analogue (the trace/retrieval disagree with the current live clause). No case type where the live store itself is wrong is included; see Limitations.
- Design permits, and the results show, more than one outcome type: both
  arms agree (origin); inherited correct/independent correct diverging as
  degradation increases (main grid); independent-vs-independent divergence
  under enough lag (A4 sensitivity). It does **not** show "live evidence
  wrong, inherited evidence right" — see Limitations for why, and that this
  is a scope boundary, not a defect.

## Critical validity matrix

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Can A3 access anything A5 can access (a live store)? | **No** | `isolation_probe`: A3 opens zero database files; source-token ban forbids `sqlite3`/`resolve_bindings`/`REPLICA`/`ORDERS_DB`/`POLICY_DB` in `TraceOnlyStrategy` |
| 2 | Can A5 access anything A3 can access (the trace)? | **No** | `B.LiveQueryStrategy.resolve` never dereferences its `case` parameter (direct source read, `bench/baselines.py:202-217`) |
| 3 | Can A4 differ from A5? | **Yes** | `replication_lag_sensitivity()`: 88.6% vs 100.0% at lag ≥ 14 days — a proven, not merely asserted, capability |
| 4 | Can inherited evidence be correct while live evidence is wrong? | **Not exercised in this design** | The live stores are never corrupted within P05's scope; A5 is 100% accurate at every grid point by construction. A store-corruption case exists in the project (P08's `SOURCE_UNRELIABLE` scenarios) but is a different, frozen experiment, not part of P05. This is a scope boundary, disclosed here, not a defect in what P05 does claim. |
| 5 | Can live evidence be correct while inherited evidence is wrong? | **Yes** | The entire main grid: every inherited arm falls below 100% as absence/staleness increase while both independent arms hold at 100.0% |
| 6 | Can both arms agree? | **Yes** | Origin point: A3 = A5 = 100.0% on both sweeps ("parity at the origin: held") |
| 7 | Are labels independent of all arms? | **Yes** | Gold labels come from `bench/label.py` against the frozen, hash-verified `bench/gold_set.jsonl`, identical for every arm; `test_p03_gold_set_hash_is_unchanged` |
| 8 | Is evidence perturbation independent of gold labels? | **Yes** | `build_view`'s perturbation is keyed by `(case_id, channel, seed)` via a seeded uniform draw, with no gold-label input; `test_perturbation_never_touches_gold_toolcall_or_stores` |

No property in this matrix is impossible in a way that invalidates the
comparison. **No defect was found. No repair was made.**

## Prior repair history (for the record, not repeated here)

`reports/evidence-ablation.md`'s own "Differences from the first (invalid)
P05 implementation" section documents that this exact class of audit was
already performed, twice, in earlier work on this repository: the first A3
implementation read full context (message + retrieved + `claimed_*`) and was
rejected as not trace-only; the first A4 was "live query + a latency
constant" (could never diverge) and a second pass over-corrected it into an
artificially stale snapshot mislabeled "200 ms." Both were rebuilt to the
implementation verified above. This audit re-derived that verification
independently from the current code and tests, rather than trusting that
history's own narrative, and reached the same conclusion: the current
implementation is valid.

## Defects found in this audit: none

## Repairs made in this audit: none

## Validity assessment

**Valid.** Every item in the critical validity matrix holds with direct code
evidence; all 25 `tests/test_evidence_ablation.py` tests pass (verified this
audit: `43 passed` combined with P04's 18); the gold set is hash-verified
unchanged; the isolation gate is a hard `SystemExit`, not a soft check.

## Limitations

- **No live-store-corruption condition.** P05 never scores a case where the
  authoritative store itself is wrong — A5 is 100% accurate at every grid
  point by construction of this experiment. That scenario exists in this
  project (P08, `SOURCE_UNRELIABLE`) but as a separate, already-frozen
  experiment, not folded into P05.
- **Single domain, single tool.** All 150 cases are `issue_refund` cases from
  the same synthetic seed data as P03/P04; the 50 ALLOW cases sit on 5
  source orders, and every P05 confidence interval resamples clusters, not
  cases, for exactly this reason.
- **A4's 200 ms model is not stressed by this dataset.** The replica-vs-live
  divergence is real and measured (§ A4 status), but only visible once the
  swept lag exceeds 13 days; the arm's *specified* 200 ms sits on the flat
  part of that step function. The report already withdraws its earlier
  "freshness costs 11.4 points at 200 ms" framing for exactly this reason.
- **"AgentLTL" is referenced in `reports/evidence-ablation.md`'s positioning
  paragraph but was not one of the three sources this audit was instructed
  to verify (only LedgerAgent, AEGIS, OAP were in scope).** That reference is
  therefore neither confirmed nor disputed here — flagged as out of this
  audit's scope, not verified PAPER-DERIVED evidence.
- **This is one ablation.** It measures where independent evidence helps
  *this* task under *this* degradation model; it does not establish causal
  superiority of ControlPlane's architecture in general, and the existing
  report does not claim that ("ControlPlane is better" framing was
  deliberately avoided in favor of "does the source of evidence matter" —
  confirmed by direct reading of `reports/evidence-ablation.md`'s framing).

## Measured vs. paper-derived claims — final separation

- **PAPER-DERIVED**: everything in the LedgerAgent table above, taken from
  arXiv:2606.20529.
- **REPOSITORY-DERIVED**: the A1–A5 provenance table, the control-variable
  audit, and the validity matrix — read from `bench/evidence_ablation.py`,
  `bench/baselines.py`, and `tests/test_evidence_ablation.py`.
- **OUR MEASURED RESULT**: the accuracy figures in `reports/evidence-ablation.md`
  (crossover ≈ 11.7% absence / 40.0% staleness, A4 vs A5 divergence at ≥14
  days lag) — unchanged by this audit, re-verified valid, not re-run.
- **No INFERRED claim** is made in this document beyond what the matrix
  above supports with direct evidence.
