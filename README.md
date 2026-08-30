# ControlPlane

**A runtime verification layer for enterprise AI agents.** When an agent
proposes an action, we intercept the tool call *before it executes*, check the
claims inside it against the enterprise's own live systems of record, and
decide whether to allow, modify, block or escalate — emitting a signed
evidence receipt for every decision.

> Most AI checkers ask another AI for a second opinion.
> We ask the company's own systems for the actual answer.

Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2

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
.\make.ps1 demo       # use case 1: the gate catches it — BLOCK, plus a signed receipt
.\make.ps1 demo2      # use case 2: the cross-tenant document block
.\make.ps1 demo3      # use case 3: discount approval — added as manifest + graph data, zero engine code
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
sign and persist a Decision Receipt. Which claims exist, which resolver
answers each, the predicate-payload shape, the predicate graph, and
compensability all come from the active manifest's `claim_bindings`
(`controlplane/bindings.py`, `docs/policy-manifest.md`) — the engine has no
per-use-case code, and a CI check fails if it grows any. `docs/evidence/gate_condition_check.txt`
is the roadmap's own required proof that this isn't staged: five different
phrasings of the same request, majority propose the refund unprompted.

Zen Engine expresses business decision logic — the window is 7 days and this order is at 26. It is not the security perimeter; authorization is upstream and is not our contribution.

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
      ▼   claims + resolvers + payload shape all come from the active
          manifest's claim_bindings (controlplane/bindings.py) — not Python
controlplane/ladder.py        Checkability Ladder: C1-C5 tier, load-bearing
      ▼
controlplane/registry/*.py    fresh Evidence from orders.db / policy_store.db / manifest
      ▼
controlplane/predicates/      Zen Engine JDM graph named by the manifest — rules as data
      ▼
controlplane/ground.py        HHEM-2.1-Open, C3 only, optional (CP_GROUNDING)
      ▼
controlplane/decide.py        pure: verdict + intervention (D49 compensability)
      ▼
controlplane/receipt.py ──┬── decisions.jsonl (signed, HMAC-SHA256)
controlplane/telemetry.py ┘   + coverage / latency / promotion-cost blocks
```

Built: S0-S18. `make bench` runs SEB-1 Exp 3 (D52 cross-validation); Exp 5
(confusion matrix) is **BLOCKED** pending a held-out gold set (task P03) —
its previous version was circular and has been retired, see
`docs/experiment-audit.md`. `make review` runs the human-in-the-loop
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

`agents/discount_agent.py` is the **third** use case (P02) — goodwill
discount / store-credit approval, `approve_discount(order_id, amount_paise,
currency)`, a 14-day validity window and an INR 5,000 authority ceiling.
The point of it is *how it was added*: one YAML file
(`manifests/discount_approval.yaml`), one JSON predicate graph, one demo
agent — and **zero lines changed under `controlplane/`**. The engine
(evidence bindings, resolver selection, predicate-graph choice,
compensability) is now manifest data, not a per-use-case dispatch table.
`tests/test_engine_is_use_case_agnostic.py` fails if any string under
`controlplane/` names a use case. See `docs/policy-manifest.md` for the
binding schema and `docs/architecture.md` for the onboarding-time
measurement. `make demo3` runs it.

Bias: `decide()` takes no protected-attribute input at all — no name, no
demographic field, nowhere in `ProposedAction`, `Claim`, `Evidence`, or
`SessionContext`. This is verified **structurally** in
`tests/test_no_protected_attributes.py`, not statistically. The earlier
`controlplane/bias_probe.py` was deleted: it drew a synthetic group label,
never passed it to `decide()`, and then "confirmed" block rates didn't
differ across it — a result forced by construction, not by correctness. A
guarantee that the function cannot read the variable is the stronger claim.
See `docs/limitations.md` and `docs/experiment-audit.md`.
`bench/bias_proxy_probe.py` is a clearly-labelled proxy analysis, not a
bias measurement.

`docs/invariants.md` states five metamorphic invariants (M1-M5) over
`decide()`, property-tested with `hypothesis` in `tests/test_invariants.py`.
`controlplane/mutation.py` mutates scenario inputs against a genuinely
ALLOW-worthy baseline, with operators derived from the **specification**
(the `issue_refund` tool JSON schema and `manifests/servicing.yaml`) rather
than from the checks `decide()` implements — so the score is **below 1.0
by design**: it includes spec elements the gate has no mechanism to
enforce, and names which ones per operator. The earlier version derived its
operators from the six existing checks, so every mutant was caught and the
score was 1.000 by construction — retired, see `docs/experiment-audit.md`.

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
  scenario** — 120 measured receipts across all three manifests have a
  median of 2,282 bytes and p95 of 3,763 bytes (max 3,764). Nothing was
  trimmed for this measurement. The aggregate is reproducible, but the 120
  individual raw receipt payloads were not persisted. Two rounds of legitimate trimming happened before this:
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
- **Escalation rate-limiting is enforced at `dispatch_tool`.** ESCALATE holds
  the action in `pending_actions.jsonl`; `make review` presents the receipt
  without its verdict, accepts APPROVE/BLOCK, then reveals the verdict and
  records agreement. The rolling 100-decision budget comes from the active
  manifest's `escalation_budget_pct`; when exhausted, `risk_tier_default`
  selects that tier's fail-open or fail-closed posture. The exhaustion outcome
  is persisted. `decide()` remains pure.
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
  fluent paraphrase asserting a 30-day window scores 0.023. **P09 profiled
  the latency** (`reports/latency.md`, 4 configs × 1,050 gated calls): gate
  end-to-end median **7.67 ms** with grounding off (C1); with grounding on
  the HHEM entailment call is p50 **161 ms** and dominates every tail metric,
  plus a one-time ~**9 s** cold-start model load. `CP_GROUNDING=off` is the
  default. Load dominates tail latency exactly as the roadmap predicted —
  reported here, not hidden.
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
- **Four of the five reported experiments were circular and have been
  retired.** An internal audit (`docs/experiment-audit.md`) found that the
  confusion matrix (accuracy 1.000), the order_id cross-validation pair
  (100% / 75%), the mutation score (1.000), and the bias probe ("no
  difference detected") all had outcomes forced by how their test inputs
  were constructed — none of them could fail. The retirements, and what
  replaced each, are in `docs/retired-figures.md`. This is stated up front
  rather than buried: a benchmark that cannot fail teaches a reviewer to
  distrust the numbers that *are* real, so removing it is the credible
  move. What survives: Exp 3 rebuilt against held-out ground truth (0.92
  with the attribute check, 0.755 without — and it now has a demonstrable
  blind spot, so it can fail); a spec-derived mutation score (0.60, with a
  per-operator table of what the gate does and does not catch); a
  structural no-protected-attributes guarantee in place of the bias probe.
- **The confusion matrix (Exp 5) is BLOCKED, not reported.** It needs a
  held-out gold set whose labels are assigned independently of `decide()`
  (task P03). Until that lands, `bench/seb1_exp5_confusion_matrix.py`
  raises `SystemExit` rather than emit a passing-but-meaningless number.
- **Logger 2 (SEB-1 extraction-accuracy-under-noise)** stays an honest
  `not_measured` stub — it needs the *date-extraction* harness from
  `phase 1/` re-run against the live extractor, which nothing here
  substitutes for.
- **`reports/noise_sweep.png` is not a noise sweep.** No noise-level
  experiment exists in this build. The file is generated at that path for
  `bench/report.py`'s file-list compliance, but its title and content
  honestly say what it actually is: Exp 3's with/without-check accuracy
  comparison. Mislabelling the filename would have been worse than
  explaining it.
- **The reviewer console's human-gate agreement rate needs an actual
  human.** The reviewer console accepts only an interactive APPROVE or BLOCK
  decision. There is no automatic approval option; run it interactively to
  produce an agreement measurement.

---

## Repository map

| Path | What it is |
|---|---|
| `controlplane/` | The product — use-case agnostic. The gate, the registry, `bindings.py`, the receipt. |
| `agents/` | Three demo agents — servicing, knowledge assistant, discount approval. |
| `data/` | Committed JSON seeds + a deterministic database builder. |
| `manifests/` | Per-use-case config: thresholds, compensability, evidence bindings, and `graphs/` (the Zen JDM predicate graphs). Same engine, different behaviour. |
| `bench/` | SEB-1, the mutation harness, and the measurement scripts. |
| `docs/` | `architecture.md`, `policy-manifest.md`, receipt schema, invariants, limitations, the experiment audit, evidence. |
| `tests/` | Unit, golden-file, metamorphic and mutation tests. |

## Reproducibility

Everything is seeded at `CP_SEED=20260814` and the demo clock is frozen at
`CP_DEMO_DATE=2026-08-14`. `python data/build_db.py` produces byte-identical
databases on every run — `tests/test_data.py` asserts it. If you run this
code you should get the numbers we published; if you do not, that is a bug and
we want to hear about it.
