# ControlPlane

**A runtime verification layer for the governed agent tool calls in this
repository.** Before a registered tool call executes, the gate checks its
claims against configured authoritative sources (the included demos use
locally built SQLite stores), then allows, modifies, blocks or escalates it.
Gated decisions that complete evaluation are recorded as signed evidence
receipts.

Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2

---

## What changed after our internal audit

An internal audit identified circularity and related methodological problems
in several reported experiments and one coverage metric. The affected figures
are retired; they are not current evidence. The original findings are preserved
in [the experiment audit](docs/experiment-audit.md), and the affected figures
and reasons for retirement are recorded in
[the retraction record](docs/retired-figures.md).

The public baseline remains `6ec4261`; `origin/main` points to that commit.
The engineering state documented here is the verified local release candidate
represented by the audited HEAD. It is not a public release until it is
integrated and pushed. Its ancestor `986b65e` contains the original C/I/D
reconciliation; `dce2e4c` later corrects recipient authorization to check the
actual execution recipient; and `aac3bea`, the Step 6B endpoint and immediate
engineering parent, synchronizes the threat model with that correction. The
candidate chain adds engineering, focused-test and public-documentation
changes, but no benchmark or research artifacts.

The audit findings also exist in off-release development commit `b4ef009`,
which is not an ancestor of either the public baseline or this candidate (their
common ancestor is `42143cf`). Corrective benchmark implementations and
replacement results from that line remain off-release. The two linked audit
documents distinguish those historical results from files actually present in
the public baseline and verified candidate.

## Verified release-candidate engineering semantics

The C/I/D reconciliation introduced at `986b65e` and carried by the current
audited release candidate preserves the existing behavior of boolean predicate
results: `True` can support the normal success path and `False` the normal
contradiction path. A missing, `None`, malformed or non-boolean result enters
the existing unverifiable path; it cannot silently count as a pass. Missing
rows and nullable source fields likewise produce unavailable evidence. SQLite
availability failures are typed, ambiguous current-policy rows block as `SOURCE_UNRELIABLE`,
and schema/programming errors remain visible rather than being converted into
favorable evidence. A typed source outage becomes `UNVERIFIABLE` and then uses
the manifest's compensability-specific `fail_posture`; this is not a blanket
fail-closed policy.

For governed dispatch, `ALLOW` executes the original arguments and `BLOCK`
does not execute. `MODIFY` executes exactly an explicit dictionary of
`modified_args`, including an explicit empty dictionary. Missing, `None` or
non-dictionary modified arguments raise the existing pending/refusal path; the
original arguments are never substituted. This validation is structural, not
semantic tool-schema validation. In particular, the knowledge-assistant
manifest maps `UNVERIFIABLE` to `MODIFY`, but an unverifiable decision without
explicit modified arguments cannot call `send_document` with the original
arguments.

The idempotency ledger is deliberately process-local and in-memory. Reusing a
completed key returns the stored result without another execution; reusing an
in-flight or indeterminate key suppresses execution; distinct keys are
independent. Keys are derived from the trace id plus
`action.facts_for_predicate()`, so callers must reuse those inputs. The ledger
is not durable across restart, is not shared across processes, and has no
expiry or distributed locking.

`dispatch_tool()` is the execution boundary for the registered governed paths
in the two included demos, not a proof that arbitrary Python code cannot call
an implementation directly. `decide()` remains deterministic and side-effect
free, and predicates receive `facts_for_predicate()` rather than agent-asserted
`claimed_*` fields. These are engineering properties verified by focused
regressions; they are not evidence of research efficacy, external validation,
broad generalization, production readiness or adversarial robustness.

---

## Quick start

**Windows**

```powershell
git clone <repo-url>
cd controlplane
.\make.ps1 setup      # venv + install + build the databases
.\make.ps1 probe      # check your LLM provider works
.\make.ps1 test       # tests should pass
.\make.ps1 negative   # the agent fails, with the gate OFF
.\make.ps1 demo       # the gate catches it — BLOCK, plus a signed receipt in decisions.jsonl
```

**macOS / Linux** — same, with `make setup`, `make probe`, and so on.

You do **not** need an API key to run the demo: LLM responses for the demo
scenarios are cached as committed fixtures. Set `CP_MODE=live` in `.env` to
call the provider for real.

---

## Implementation approach

`agents/servicing_agent.py` proposes a tool call from a customer message
that never states an order ID, amount, or date — the agent has to resolve
all three itself, from a deliberately stale retrieval index. Every proposal
passes through `controlplane/intercept.py::dispatch_tool()`, the execution
choke point for these registered paths: with the gate off, it calls the
implementation directly
(the negative control — `docs/evidence/negative_control.txt`); with the
gate on, it runs the full pipeline — extract the agent's claims (Instructor,
`Mode.JSON`) → classify each into a Checkability Ladder tier → resolve fresh
evidence from the configured SQLite stores, independent of whatever the agent's
stale context claimed → evaluate business rules as data (a Zen Engine JDM
graph, not Python `if` statements) → decide a verdict and an intervention →
sign and persist a Decision Receipt. `docs/evidence/gate_condition_check.txt`
records the roadmap's five-phrasing gate-condition check; it is repository
evidence for that demo condition, not external validation.

## Solution architecture

```
customer message
      │
      ▼
agents/servicing_agent.py ── proposes issue_refund(order_id, amount_paise, currency)
      │
      ▼
controlplane/intercept.py::dispatch_tool()   ◄── governed registry calls execute here
      │
      │  gate OFF ──────────────────────────────► impl() directly (negative control)
      │
      ▼  gate ON
controlplane/extract.py       Instructor, Mode.JSON → ProposedAction + Claims
      ▼
controlplane/ladder.py        Checkability Ladder: C1-C5 tier, load-bearing
      ▼
controlplane/registry/*.py    fresh Evidence from orders.db / policy_store.db / manifest
      ▼
controlplane/predicates/      Zen Engine JDM graph — rules as data, R1-R4
      ▼
controlplane/ground.py        HHEM-2.1-Open, C3 only, optional (CP_GROUNDING)
      ▼
controlplane/decide.py        pure: verdict + intervention (D49 compensability)
      ▼
controlplane/receipt.py ──┬── decisions.jsonl (signed, HMAC-SHA256)
controlplane/telemetry.py ┘   + coverage / latency / promotion-cost blocks
```

Built: S0-S18. The existing `make bench` targets include the historical
SEB-1 Exp 3 and Exp 5 harnesses, but their previously reported outputs are
retired and must not be treated as current evidence; see the audit documents
above. `make reviewer` runs the human-in-the-loop
console (terminal, per the roadmap's own sanctioned alternative to
FastAPI+HTMX — the effort went into the pipeline it measures instead of a
web UI for it). `make report` can generate `reports/` from `decisions.jsonl`
and the bundled harnesses, but those harnesses still include the retired
circular experiments and historical grounding constants. Generated reports
therefore do not become current evidence merely by being regenerated.

`agents/knowledge_assistant.py` is the second use case (S13): same gate,
`send_document(recipient_id, doc_id, excerpt)` instead of `issue_refund`,
entitlement instead of correctness. Retrieval doesn't know about
entitlement any more than S2's stale policy index knew about
`effective_to` — ask about the escalated delivery-dispute ticket and it
surfaces `DOC-2277`, which is about `CUST-7788`, to `EMP-4410`, who is
entitled to `CUST-2291` only. In the included deterministic fixture scenario,
the proposal has `doc_classification_permitted: true` and
`recipient_entitled_to_doc: false`, producing `BLOCK` with root cause
`recipient_entitled`. `controlplane/pii.py` (S14) separately detects the
fixture's third-party PII (name, email and order ID) but is deliberately not
load-bearing. This is a demo/tested behavior, not a claim of live external
validation.

The historical `controlplane/bias_probe.py` result is retired. Its synthetic
group label never enters `decide()`, so equal block rates were forced by
construction and do not support a bias-performance claim. A structural
replacement was prepared in `b4ef009`, but it is in neither the public baseline
nor the verified candidate; neither reports a replacement result.

`docs/invariants.md` states five metamorphic invariants (M1-M5) over
`decide()`, property-tested with `hypothesis` in `tests/test_invariants.py`.
The historical mutation score is also retired: its operators were derived
from checks already implemented by the gate, so the result restated those
checks. A specification-derived replacement was prepared in `b4ef009`, but it
is in neither the public baseline nor the verified candidate; neither reports a
replacement score.

## Dependencies

Every dependency is MIT or Apache-2.0; see `requirements.txt` for the
per-package licence. Two libraries were deliberately excluded on licence
grounds **before** we knew a public repository would be required:
Bespoke-MiniCheck-7B (CC BY-NC) and SDV (BUSL-1.1).

## Execution instructions

```powershell
.\make.ps1 setup
.\make.ps1 probe
.\make.ps1 test
.\make.ps1 negative   # gate off — money moves, unchecked
.\make.ps1 demo       # gate on  — BLOCK, plus a signed receipt in decisions.jsonl
```

## Honest limitations

*(this section grows as the build lands — keep it. It is the most credible
thing in the repo.)*

- **The policy corpus is hand-authored, not scraped.** `scripts/scrape_policies.py`
  exists. The repository records a historical Firecrawl attempt that returned
  `401 Unauthorized: Invalid token`, but no response artifact is committed and the
  candidate did not revalidate it. The v3.8/v4.2 clause text in
  `data/seed/clauses.json` therefore stays hand-authored. The version history (a
  clause silently superseded, still
  reachable from a stale retrieval index) is the actual point being demonstrated and
  is unaffected by this.
- **A historical local `issue_refund` BLOCK receipt exceeded the ~2 KB
  target** — the seven-claim/seven-evidence example was reported at ~3.8 KB
  signed. No committed receipt corpus supports treating that as a current
  candidate aggregate. Two rounds of legitimate trimming happened before it:
  a claim that was tracked but not yet checked by `decide()` was excluded
  until it was real rather than kept for appearances, and `reasons` lists
  only the checks that actually failed rather than restating every pass
  (`claims`+`evidence` already show what was checked). Further compaction
  would mean shorter field names or dropping evidence entries, which trades
  against the receipt's actual job — being a complete, readable audit trail
  — so it wasn't done. The separate n=120 receipt-size aggregate described in
  `docs/retired-figures.md` is off-release evidence, not a public result.
- **R3 (entity match) is extended**, per D52: `item_colour`/`item_category`
  are now required structural arguments on the `issue_refund` tool call
  (declared in the tool schema, filled by native function-calling, never
  agent prose — the same mechanism order_id already uses), checked against
  the resolved order's seeded source attributes as a second Zen predicate,
  `attributes_match`. The committed fixture for ORD-88461 supplies
  `item_colour='blue', item_category='shoes'`, matching the seeded order;
  this is deterministic demo coverage, not a live-validation result.
  `tests/test_predicates.py` also covers the D52 distractor case
  (ORD-88472, same customer and colour, different category) directly.
- **Escalation rate-limiting against the manifest's `escalation_budget_pct`
  is not implemented.** `decide()` must stay pure (no I/O, no clock — hard
  constraint) for S15's metamorphic tests to exercise it;
  rate-limiting needs state across calls, so it belongs at the `dispatch_tool`
  caller level, which isn't wired up.
- **Logger 2 (extraction accuracy under noise, the SEB-1 sweep) is an
  honest stub**, not a measured number. SEB-1's harness
  (`seb1_v2_recoverability.py`, `servicing_extraction_bench.py`) exists in
  `phase 1/`'s scratch folders and has not been ported into this repo.
  `controlplane/telemetry.py` reports `"status": "not_measured"` for it
  rather than inventing a figure.
- **S8 grounding (HHEM-2.1-Open) is optional and off by default** —
  `CP_GROUNDING=off` is still the default (it's a ~600MB+ `torch`+`transformers`
  download the base pipeline never needs; `controlplane/intercept.py` wraps
  the import so the rest of the gate works identically with neither
  installed). When the optional model is installed, `tests/test_ground.py`
  checks only that an accurate paraphrase is above the 0.5 threshold and a
  fluent 30-day-window contradiction is below it. Exact scores and timings
  formerly reported here were historical local observations, were not rerun
  for `986b65e`, and are not external validation; the P09 latency profile is
  off-release evidence recorded as such in `docs/retired-figures.md`.
  An environment bug surfaced during that historical work and was fixed:
  `transformers>=5.0` breaks HHEM's `trust_remote_code` model class
  (`AttributeError: ... no attribute 'all_tied_weights_keys'`) because it
  changed an internal model-loading API HHEM's remote code depends on.
  `requirements.txt` now pins `transformers>=4.40,<5.0`.
- **The invariant suite found a real bug in `decide()`, and it's worth naming.**
  M5 (source-degradation monotonicity) failed on the very first Hypothesis run,
  twice, at two different scenarios. An earlier version applied the verdict
  precedence ("SOURCE_UNRELIABLE > CONTRADICTED") *globally*: degrading ONE
  claim's evidence reliability could suppress a completely unrelated, still-
  fully-reliable claim's hard contradiction, turning what should stay BLOCK
  into the strictly more permissive ESCALATE — a defect class an agent (or a
  bug) could trigger by degrading its own evidence quality, identified by
  Hypothesis property-based testing rather than an observed exploit. Fixed by
  scoping the
  precedence per-claim and, for the case where the SAME claim is both
  unreliable and would itself fail, decoupling the verdict label (still
  honestly `SOURCE_UNRELIABLE`) from the intervention floor (never weaker
  than a hard contradiction would earn). `controlplane/decide.py`'s
  docstring and `tests/test_invariants.py` both carry the full explanation.
  This is the "found this and we fixed it" sentence the roadmap asked for —
  it isn't hypothetical.
- **The reported Exp 3 100% / 75% comparison and the prior Exp 5 confusion
  matrix are retired.** The audit found that their labels and predictions
  were circular, so the figures could not provide independent evidence.
  They remain recoverable from Git history but are not valid current results.
  Repairs and replacement figures described by the historical audit documents
  were prepared in `b4ef009`; they are not merged here, and neither the public
  baseline nor verified candidate generated replacement numbers. Logger 2 (SEB-1
  extraction-accuracy-under-noise) remains an honest `not_measured` stub.
- **The report harness's `noise_sweep.png` output is not a noise sweep.** No
  noise-level experiment exists in this build, and no `reports/` directory is
  committed in the public baseline or candidate. If generated, that file is
  the retired Exp 3 comparison and is not a current result.
- **The reviewer console's human-gate agreement rate needs an actual
  human.** `bench/reviewer_console.py --auto-approve` exists only to prove
  the console doesn't crash — it is explicitly NOT a measurement, and says
  so in its own output. Run it without that flag, interactively, for a
  real number.

---

## Repository map

| Path | What it is |
|---|---|
| `controlplane/` | The product. The gate, the registry, the receipt. |
| `agents/` | Two demo agents — servicing, and an internal knowledge assistant. |
| `data/` | Committed JSON seeds + a deterministic database builder. |
| `manifests/` | Policy configuration for the two included use cases; shared decision engine, manifest-selected behavior. |
| `bench/` | SEB-1 and the measurement harnesses. |
| `docs/` | Architecture, receipt schema, invariants, limitations, evidence. |
| `tests/` | Unit, golden-file, metamorphic and mutation tests. |

## Reproducibility

The included deterministic builders and demo fixtures use `CP_SEED=20260814`,
and the demo clock is frozen at `CP_DEMO_DATE=2026-08-14`.
`python data/build_db.py` produces byte-identical
databases on every run — `tests/test_data.py` asserts it. This reproducibility
statement does not revive the audit-retired figures, and the verified release
candidate did not rerun or generate replacement experiments.
