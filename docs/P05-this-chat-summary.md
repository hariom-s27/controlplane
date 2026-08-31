# P05 — this chat's session log (evidence-source ablation)

**Scope of this file:** only what happened in *this* conversation thread. This
repository has multiple independent chat sessions working on it in parallel
(see `docs/session-handoff-2026-08-31.md`, `docs/SESSION-LOG.md`,
`docs/chat-session-handoff.md`, `docs/session-log-p08-p09.md` for other
threads' P02/P06/P07/P08/P09 work) — this file does not summarize those and
makes no claim about them. It exists so this thread's P05 work can be
reviewed and committed to GitHub without reconstructing it from chat history.

Local HEAD at the time of this work: `b4ef009ab309372d1cd683145684a313696fa06a`.

---

## 1. The task

**P05 — the evidence-source ablation**, priority P0, depends on P03 (the
independent gold set) and P04 (the B0–B5 baseline table). The brief:

> Our claim is not "we intercept tool calls" (AEGIS) and not "we ground
> claims in evidence" (AgentLTL, where the witness is one of the agent's own
> tool results). Our claim is: the evidence is FETCHED by an independent
> query at decision time, not INHERITED from the agent's context.

Required: five arms (A1 MessageOnly, A2 RetrievedOnly, A3 TraceOnly, A4
CachedRead, A5 LiveQuery) sharing one pipeline and differing only by the
injected evidence strategy; two sweeps (context absence 0/10/30/50/70/100%,
policy staleness 0/10/25/50/100%) at 3 seeds each; a prediction recorded in
`reports/evidence-ablation.md` **before** the results; two charts; a
statistically supported crossover point; and constraints — never drop or
reweight an inconvenient arm, and stop rather than approximate if structural
identity across arms can't be achieved.

---

## 2. What was built, in three rounds

### Round 1 — first implementation

Five `EvidenceStrategy` subclasses routed through a shared `_run_pipeline` →
`bench.baselines._run_our_pipeline` (P04's own runner, unmodified). Two new
sweeps perturbed a copy of each P03 gold case. Produced `bench/evidence_ablation.py`,
`tests/test_evidence_ablation.py`, `reports/evidence-ablation.md`, two charts,
and a `summary.json[p05_evidence_ablation]` entry.

First-round headline numbers (**superseded — do not cite**): absence
crossover ≈10%, staleness crossover ≈25%, A4 ≡ A5, framed as "independence,
not freshness, is the active ingredient."

### Round 1 audit (self-requested methodology audit)

Before accepting the first-round result, an audit was run against the literal
arm definitions. Findings:

- **A1** read a synthesized "message" whose delivery date/total came from
  `orders.db` at build time — not authentically a customer-authored message,
  and not clearly labelled as synthetic.
- **A3 ("TraceOnly")** actually read the agent's message *and* retrieved
  chunks *and* its `claimed_*` assertions — full-context grounding, not
  "the agent's own prior tool outputs" as AgentLTL κ-3 requires. There was no
  serialized tool-call trace in P03 for it to read.
- **A4 ("CachedRead")** was literally `A5`'s live-query code plus a
  `latency_floor_ms = 200.0` constant added only to the reported timing. It
  could never diverge from A5 by construction — the "independence, not
  freshness" claim was true by construction, not by measurement.

None of P03 or P04 was touched by the audit or by round 1; the audit was
read-only and reported the mismatch rather than silently patching numbers.

### Round 2 — rebuild (A3 → genuine trace, A4 → genuine replica)

- **New P05-only fixtures** (`bench/fixtures/p05/context_fixtures.jsonl`,
  synthetic, deterministic, SHA-pinned, provenance documented in
  `bench/fixtures/p05/README.md`): a labelled synthetic `customer_message`,
  `retrieval_chunks`, and an `agent_trace` — `get_order` / `get_policy` tool
  results as the agent would have received them earlier in its trajectory.
- **A3 rebuilt** to read `case['_trace']` only. Absence now means "the agent
  never called `get_order`" (the trace step is missing), not "text was
  deleted from a message." A3 also began correctly catching wrong-order
  distractor cases, because the trace's `get_order` result carries the
  *resolved* order's real attributes.
- **A4 rebuilt** to query an isolated SQLite replica
  (`bench/fixtures/p05/_replica/`) built fresh at run start — never the live
  stores, never the agent's context.
- **A structural-isolation gate** (`isolation_probe()` + `assert_isolation()`)
  spies on `sqlite3.connect` for one representative case per arm, before the
  grid runs, and raises `SystemExit` if A1/A2/A3 open any database, if A4
  opens anything other than its replica, or if A5 opens anything other than
  the live stores. This is a hard gate, not a comment.

Round-2 numbers (**also superseded on A4/freshness — see round 3**): A3 ≈ A5
at 0/0 (prediction held), absence crossover ≈10%, staleness crossover ≈25%
(later re-measured as ≈12% / ≈40% once the fixed grid was rerun — see round
3's final table), and A4 built as a **weeks**-old historical policy snapshot
(2026-07-15, well before the 2026-08-01 refund-window cutover) reported
alongside a "200 ms" latency figure. That pairing was the round-3 audit's
finding.

### Round 2 audit — was A4 actually 200 ms stale?

A second self-requested audit asked, specifically: is the round-2 A4 *literally*
200 ms behind the primary, as the arm's own name requires, or was "200 ms"
just a label attached to a differently-stale fixture?

Traced from the data: `data/orders.db` is byte-deterministic and never
written during a run; `data/policy_store.db`'s only relevant state change is
the `refund_window` v3.8→v4.2 cutover at `effective_from = 2026-08-01`, and
the demo clock is frozen at `2026-08-14` — **13 days** after that cutover.
The clause table's effective dates are day-granular. **A genuinely
200 ms-stale read of this frozen data is therefore byte-identical to a live
read; there is no sub-day write dynamics for 200 ms to catch.** The round-2
implementation's 2026-07-15 snapshot was roughly **17 days pre-cutover** and
had nothing to do with 200 ms — the label was wrong, not just imprecise.

### Round 3 — the honest fix

- `build_replica()` rewritten to build `_replica/policy_store_asof_200ms.db`
  as a genuine point-in-time snapshot at `clock.now() − 200 ms`
  (`2026-08-14T09:59:59.800Z`). On this frozen dataset that snapshot serves
  `refund_window v4.2/7d` — identical to live. **A4 = A5 in every returned
  value, measured** (A4 genuinely queries a separate file; it isn't asserted
  to be identical, it turns out to be).
- Added `replication_lag_sensitivity()` — an explicitly **separate**, clearly
  labelled analysis (not one of the five arms, not on the two main charts)
  that points A4's strategy at snapshots as of `clock − L` for
  `L ∈ {200 ms, 1 d, 7 d, 13 d, 14 d, 30 d, 90 d}` and scores each. Result: a
  **step function** — 0-point cost for any lag under 13 days, 11.4 points
  once the lag crosses the last real write.
- Both prior "freshness" headlines (round 1's "independence, not freshness is
  the active ingredient", round 2's "freshness costs 11.4 points") are
  explicitly withdrawn in `reports/evidence-ablation.md` itself. The honest
  statement: **at the specified 200 ms lag, this benchmark cannot separate
  independence from freshness for A4**, because there is nothing in the
  frozen data recent enough for 200 ms to matter. What it *does* show:
  every inherited-context arm (A1/A2/A3) degrades as context degrades, and
  both independent arms (A4, A5) hold flat — independence is what's proven;
  freshness is answered only by the separate sensitivity table.

---

## 3. Final, current numbers (round 3 — the ones to cite)

All from `reports/evidence-ablation.md` / `reports/summary.json[p05_evidence_ablation]`.

| Quantity | Value |
|---|---|
| Origin parity, A3 vs A5 (absence=0/staleness=0) | gap = **0.0 pts**, both sweeps — prediction held |
| Absence crossover (5-pt margin, cluster bootstrap) | **≈11.7%**, 95% CI **[6.6%, 34.4%]** |
| Staleness crossover | **≈40.0%**, 95% CI **[9.9%, 67.0%]** — wide, reported as *not* strongly statistically defensible |
| A4 vs A5 at the specified 200 ms lag | **identical** (A4 == A5 == 100.0% on both sweeps, every grid point) |
| Replication-lag sensitivity step | 0 pts for lag < 13 days; **11.4 pts** for lag ≥ 13 days (the age of the last real store write) |
| A1 (MessageOnly) | flat **64.3%** (escalate-everything floor) |
| A2 vs A3 | track each other closely throughout (both "inherit from context") |

Grid: 5 arms × 6 absence points × 5 staleness points × 3 seeds = 450 cells,
scored on the 140 non-ambiguous P03 gold cases, ≈25–30 s wall time.

---

## 4. Files touched by this thread's P05 work

**New (this thread):**
- `bench/evidence_ablation.py`
- `tests/test_evidence_ablation.py`
- `bench/fixtures/p05/context_fixtures.jsonl` (synthetic, SHA-pinned, committed)
- `bench/fixtures/p05/README.md` (fixture provenance)
- `reports/evidence-ablation.md`
- `reports/evidence-ablation-absence.png`
- `reports/evidence-ablation-staleness.png`
- `docs/P05-this-chat-summary.md` (this file)

**Modified (small, additive):**
- `.gitignore` — tracks the two P05 report artifacts and the P05 markdown
  the way `reports/baselines.md` already is; ignores the rebuildable
  `bench/fixtures/p05/_replica/` directory.
- `Makefile` / `make.ps1` — added one `ablation` target
  (`python bench/evidence_ablation.py`), alongside the pre-existing P01–P04
  targets. No P03/P04 target's behavior was changed.
- `reports/summary.json` — only the `p05_evidence_ablation` key was
  written/replaced; `merge_summary_json()` reads-then-merges, and the
  existing `p04_baselines` key was verified byte-preserved after every write
  in this thread.

**Explicitly NOT touched by this thread:** `bench/gold_set.jsonl`,
`bench/ground_truth_holdout.jsonl`, `bench/human_label_sample.csv`,
`bench/label.py`, `bench/gold_set_build.py`, `bench/baselines.py`,
`tests/test_baselines.py`, `tests/test_gold_set_determinism.py`,
`reports/baselines.md`, `controlplane/decide.py`, any predicate graph, any
manifest threshold. Verified each round by re-hashing the three P03 artifacts
against `tests/test_gold_set_determinism.py`'s pinned SHA-256 values and by
`git status`/`git diff --check` showing no P03/P04 file in this thread's
change set.

---

## 5. Test results (this thread, final round)

```
tests/test_evidence_ablation.py   25 passed
full repo suite (tests/)          212 passed, 0 failed
git diff --check                  exit 0 (only pre-existing repo-wide LF/CRLF warnings)
```

P03 gold-set SHA-256 pins (`bench/gold_set.jsonl`, `ground_truth_holdout.jsonl`,
`human_label_sample.csv`) all matched their pinned values after this thread's
changes.

---

## 6. What a reviewer should look at, and how

1. **`reports/evidence-ablation.md`** is the primary artifact — prediction
   stated first, then arm provenance, a structural-isolation table (which
   database files each arm actually opened, captured by a live spy), the two
   sweep results, the replication-lag sensitivity table, whether the
   prediction held, and an explicit "Differences from the first (invalid) P05
   implementation" section that narrates rounds 1→2→3 in the artifact itself
   (not just in chat).
2. **`tests/test_evidence_ablation.py`** enforces the structural claims
   mechanically: one shared runner (AST-checked), bare-class strategy
   registry (AST-checked), per-arm channel isolation (source-token bans +
   runtime connect-spy), A4's replica genuinely differing from a larger-lag
   snapshot (not from a sleep or a metadata flag), A5 byte-identical to P04's
   B5.
3. **`bench/fixtures/p05/README.md`** documents exactly what's synthetic in
   the three context fixtures and why (P03 doesn't carry a customer-message
   field or a tool-call trace, so P05 had to construct both).
4. To regenerate everything from scratch: `python bench/evidence_ablation.py`
   (or `make ablation` / `.\make.ps1 ablation`), optionally with
   `--rebuild-fixtures` to regenerate the committed context-fixture file (it
   should reproduce the same SHA-256 each time — that's asserted in the
   tests).

---

## 7. Suggested GitHub commit grouping for this thread's work

1. **P05 core** — `bench/evidence_ablation.py`, `tests/test_evidence_ablation.py`,
   `bench/fixtures/p05/context_fixtures.jsonl`, `bench/fixtures/p05/README.md`.
2. **P05 generated report** — `reports/evidence-ablation.md`, the two PNGs,
   the `p05_evidence_ablation` key inside `reports/summary.json` (note: that
   file also carries P04's key — verify with a diff that only the P05 key
   changed before committing, since other threads may also be writing to it).
3. **Plumbing** — `.gitignore`, `Makefile`, `make.ps1` (the `ablation` target
   only).
4. **This log** — `docs/P05-this-chat-summary.md`.

Do not commit alongside this: anything from the other in-repo session logs
this thread did not produce or verify (`docs/session-handoff-2026-08-31.md`,
`docs/SESSION-LOG.md`, `docs/chat-session-handoff.md`,
`docs/session-log-p08-p09.md`, `docs/plan-package-2-reconciliation.md`,
P02/P06/P07/P08/P09 artifacts) — review those independently against whatever
thread actually produced them before including them in the same PR as P05.

---

## 8. Honesty notes carried over from the chat

- The two withdrawn "freshness" headlines are kept **visible, not deleted**,
  in `reports/evidence-ablation.md`'s own "Differences" section — the report
  says what was wrong and why, rather than silently presenting only the
  final numbers.
- The staleness-sweep crossover (≈40%, CI spanning 10–67%) is reported as
  weak on purpose; the brief's own instruction — "if no statistically
  defensible crossover exists, say so" — was followed rather than rounded up
  to a cleaner-looking number.
- Every numeric claim above traces to a specific file this thread generated
  and re-verified after each correction; none is carried forward from a
  prior round without being re-measured against the current code.
