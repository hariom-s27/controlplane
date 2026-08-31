# ControlPlane

**A runtime verification layer for enterprise AI agents.** When an agent
proposes an action, we intercept the tool call *before it executes*, check the
claims inside it against the enterprise's own live systems of record, and
decide whether to allow, modify, block or escalate — emitting a signed
evidence receipt for every decision.

Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2

---

## What changed after our internal audit

An internal audit identified circularity and related methodological problems
in several reported experiments and one coverage metric. The affected figures
are retired; they are not current evidence. The original findings are preserved
in [the experiment audit](docs/experiment-audit.md), and the affected figures
and reasons for retirement are recorded in
[the retraction record](docs/retired-figures.md).

Those two documents are unchanged historical artifacts from commit
`b4ef009ab309372d1cd683145684a313696fa06a`. They describe audit findings and
repairs prepared in that source commit. This publication commit merges the
disclosures and retires the public claims; it does not merge those repair
implementations, and it did not generate replacement results.

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
passes through `controlplane/intercept.py::dispatch_tool()`, the single
choke point: with the gate off, it calls the real implementation directly
(the negative control — `docs/evidence/negative_control.txt`); with the
gate on, it runs the full pipeline — extract the agent's claims (Instructor,
`Mode.JSON`) → classify each into a Checkability Ladder tier → resolve fresh
evidence from the actual databases, independent of whatever the agent's
stale context claimed → evaluate business rules as data (a Zen Engine JDM
graph, not Python `if` statements) → decide a verdict and an intervention →
sign and persist a Decision Receipt. `docs/evidence/gate_condition_check.txt`
is the roadmap's own required proof that this isn't staged: five different
phrasings of the same request, majority propose the refund unprompted.

## Solution architecture

```
customer message
      │
      ▼
agents/servicing_agent.py ── proposes issue_refund(order_id, amount_paise, currency)
      │
      ▼
controlplane/intercept.py::dispatch_tool()   ◄── the only place impl() is ever called
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
web UI for it); `make report` regenerates `reports/` and `summary.json`
from whatever's actually in `decisions.jsonl`, never from hand-typed numbers.

`agents/knowledge_assistant.py` is the second use case (S13): same gate,
`send_document(recipient_id, doc_id, excerpt)` instead of `issue_refund`,
entitlement instead of correctness. Retrieval doesn't know about
entitlement any more than S2's stale policy index knew about
`effective_to` — ask about the escalated delivery-dispute ticket and it
surfaces `DOC-2277`, which is about `CUST-7788`, to `EMP-4410`, who is
entitled to `CUST-2291` only. Verified live: the model correctly proposes
sending it, `doc_classification_permitted: true` (the classification
itself is fine — "internal" docs are within this employee's general
remit), `recipient_entitled_to_doc: false` (wrong customer) — BLOCK, root
cause `recipient_entitled`. `controlplane/pii.py` (S14) independently
confirms the excerpt genuinely contains third-party PII (name, email,
order ID) — detection works — and is deliberately NOT load-bearing on its
own, so the receipt shows detection succeeding *and* not being what
blocked it. Both halves matter; that's the actual thesis.

The historical `controlplane/bias_probe.py` result is retired. Its synthetic
group label never enters `decide()`, so equal block rates were forced by
construction and do not support a bias-performance claim. A structural
replacement was prepared in `b4ef009`, but it is not merged here; this branch
reports no replacement result.

`docs/invariants.md` states five metamorphic invariants (M1-M5) over
`decide()`, property-tested with `hypothesis` in `tests/test_invariants.py`.
The historical mutation score is also retired: its operators were derived
from checks already implemented by the gate, so the result restated those
checks. A specification-derived replacement was prepared in `b4ef009`, but
it is not merged here; this branch reports no replacement score.

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
  exists and a real attempt was made with a live Firecrawl key; every request came
  back `401 Unauthorized: Invalid token`. Rather than spend hours chasing a working
  key for a non-essential step, the v3.8/v4.2 clause text in `data/seed/clauses.json`
  stays hand-authored. The version history (a real clause silently superseded, still
  reachable from a stale retrieval index) is the actual point being demonstrated and
  is unaffected by this.
- **Decision receipts run larger than the ~2 KB target for a realistic
  scenario** — the real `issue_refund` BLOCK case (7 tracked claims, 7
  evidence entries, now including the R3 attribute check) is ~3.8 KB
  signed. Two rounds of legitimate trimming already happened before this:
  a claim that was tracked but not yet checked by `decide()` was excluded
  until it was real rather than kept for appearances, and `reasons` lists
  only the checks that actually failed rather than restating every pass
  (`claims`+`evidence` already show what was checked). Further compaction
  would mean shorter field names or dropping evidence entries, which trades
  against the receipt's actual job — being a complete, readable audit trail
  — so it wasn't done. Reporting the real, current number here rather than
  the illustrative one.
- **R3 (entity match) is extended**, per D52: `item_colour`/`item_category`
  are now required structural arguments on the `issue_refund` tool call
  (declared in the tool schema, filled by native function-calling, never
  agent prose — the same mechanism order_id already uses), checked against
  the resolved order's real attributes as a second Zen predicate,
  `attributes_match`. Verified live: for ORD-88461 the model correctly
  supplied `item_colour='blue', item_category='shoes'`, matching the real
  order, and the receipt shows `attributes_match: true` alongside the
  window/authority failures — no false positive on the correct pick.
  `tests/test_predicates.py` also covers the actual D52 distractor case
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
- **S8 grounding (HHEM-2.1-Open) is real, working, and measured** —
  `CP_GROUNDING=off` is still the default (it's a ~600MB+ `torch`+`transformers`
  download the base pipeline never needs; `controlplane/intercept.py` wraps
  the import so the rest of the gate works identically with neither
  installed), but both `tests/test_ground.py` fixtures pass against the
  real downloaded model: an accurate paraphrase of v4.2 scores 0.921, a
  fluent paraphrase asserting a 30-day window scores 0.023. Measured on
  this machine: model load ~13.2s (one-time, at first use), then ~0.1-0.5s
  per scored call. Load dominates tail latency exactly as the roadmap
  predicted — reported here, not hidden.
  A real environment bug surfaced and was fixed along the way:
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
  into the strictly more permissive ESCALATE — exploitable by an agent (or a
  bug) that simply degrades its own evidence quality. Fixed by scoping the
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
  were prepared in `b4ef009`; they are not merged here, and this publication
  branch did not generate replacement numbers. Logger 2 (SEB-1
  extraction-accuracy-under-noise) remains an honest `not_measured` stub.
- **`reports/noise_sweep.png` is not a noise sweep.** No noise-level
  experiment exists in this build. Its Exp 3 comparison is part of the
  retired evidence and must not be presented as a current result.
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
| `manifests/` | Per-use-case policy configuration. Same engine, different behaviour. |
| `bench/` | SEB-1 and the measurement harnesses. |
| `docs/` | Architecture, receipt schema, invariants, limitations, evidence. |
| `tests/` | Unit, golden-file, metamorphic and mutation tests. |

## Reproducibility

Everything is seeded at `CP_SEED=20260814` and the demo clock is frozen at
`CP_DEMO_DATE=2026-08-14`. `python data/build_db.py` produces byte-identical
databases on every run — `tests/test_data.py` asserts it. This reproducibility
statement does not revive the audit-retired figures, and this publication
branch did not rerun or generate replacement experiments.
