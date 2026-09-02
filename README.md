# ControlPlane

**A runtime verification layer for enterprise AI agents.** When an agent
proposes an action, we intercept the tool call *before it executes*, check the
claims inside it against the enterprise's own live systems of record, and
decide whether to allow, modify, block or escalate — emitting a signed
evidence receipt for every decision.

> Most AI checkers ask another AI for a second opinion.
> We ask the company's own systems for the actual answer.

Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2

`round2-final` is the current Round-2 release candidate branch for this
repository — the state described below, not yet the published submission.

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
.\make.ps1 judge-demo # six-scenario judge-facing walkthrough (offline, all fixtures)
python -m demo.web    # one-screen judge dashboard — open http://127.0.0.1:8000/
```

**macOS / Linux** — same, with `make setup`, `make probe`, and so on
(`make judge-demo` and `python -m demo.web` are identical on every platform).

You do **not** need an API key to run any of the above: LLM responses for the
demo scenarios are cached as committed fixtures (`CP_MODE=fixture`). Set
`CP_MODE=live` in `.env` to call the provider for real.

---

## The problem

An agent proposing `issue_refund(order_id, amount, ...)` only knows what is
in its own context: the conversation, whatever it retrieved, whatever it
remembers. None of that is guaranteed current — a retrieved policy clause
can have been superseded since it was indexed; an account's status can have
changed since the agent last looked. Nothing in a typical agent stack stops
the tool call from executing anyway. ControlPlane sits at the one choke
point every tool call already passes through and answers a narrower
question than "is this text safe": *does the claim inside this specific
proposed action match what the company's own systems say right now?*

## The ₹42,999 scenario

A customer writes "these blue running shoes don't fit, I want a refund" —
no order ID, no amount, no date. `agents/servicing_agent.py` (Qwen3-8B)
resolves it anyway: `issue_refund(order_id='ORD-88461', amount_paise=4299900,
currency='INR', item_colour='blue', item_category='shoes')` — a ₹42,999
refund, proposed unprompted. Five independently-worded phrasings of the same
request produce the same unprompted proposal 5/5 times
(`docs/evidence/negative_control.txt`) — this is not a single staged run.

With the gate **off**, `impl()` runs directly and the refund goes through
(`docs/evidence/negative_control.txt` is that negative control). With the
gate **on**, `controlplane/intercept.py::dispatch_tool()` resolves the order
from `orders.db` — independent of anything the agent retrieved — and finds
it was delivered **2026-07-19**; the decision clock is frozen at
**2026-08-14**, 26 days later. The active manifest's refund window is 7
days. Verdict: **BLOCK**, root cause `outside_window`, and a signed Decision
Receipt is appended to `decisions.jsonl`. Reproduce it: `.\make.ps1 negative`
(gate off, money moves) then `.\make.ps1 demo` (gate on, BLOCK). See "Judge-
facing product layer" below for the same class of result driven from the
dashboard instead of the CLI agent.

## Claims vs. company facts

Every proposed action carries claims the agent believes to be true;
ControlPlane replaces "believes" with a fresh read of whatever record that
claim is actually about.

| Claim (in the agent's context) | Company fact (queried live) | Source |
|---|---|---|
| The refund looks like it should be within policy | `orders.db`: ORD-88461 delivered 2026-07-19 — 26 days before the decision clock, outside the 7-day window | the scenario above |
| Retrieved policy clause says a 30-day window (v3.8) | `policy_store.db`: v3.8 was superseded by v4.2 (7-day window) before the retrieval index was built | `reports/baselines.md`, `stale_policy_context` slice (20/20 cases) |
| A requested document looks like an ordinary internal document | `entitlements.db`: the requesting employee is entitled to a different customer's case, not this one | "Implementation approach" below, use case 2 |

We ask the system of record, not another model, because the failure mode
above is a stale or incomplete **fact**, not unsafe **text** — a second LLM
reading the same stale context has no way to know it's stale either.

## Use cases

All three use cases run the identical `controlplane/` engine — only the
manifest changes (`manifests/*.yaml`), which changes *what* is checked and
*how*, never how it is enforced.

- **1 — Refund servicing** (`agents/servicing_agent.py`): the scenario
  above. Checks the refund window, order/customer/attribute match, and the
  agent's authority ceiling.
- **2 — Knowledge-assistant document access** (`agents/knowledge_assistant.py`):
  checks document *entitlement*, not just classification — a
  technically-internal document can still be blocked for going to the wrong
  customer's case. This is also the judge dashboard's own hero scenario —
  see below.
- **3 — Discount / store-credit approval** (`agents/discount_agent.py`):
  added as **one manifest + one predicate graph + zero lines under
  `controlplane/`** (`docs/architecture.md`) — the proof that the engine is
  genuinely use-case-agnostic, not a demo restricted to refunds.
  **Engineering-validated** (`tests/test_third_use_case.py`, `make demo3`)
  — it is not one of the judge dashboard's two profiles; see "Judge-facing
  product layer" below.

## Judge-facing product layer

Everything above is the governance engine. This layer was built specifically
so a judge can see it work without reading Python.

| Layer | What it is | Entry point |
|---|---|---|
| **Product-01** | Six scripted, offline scenarios run over the real pipeline: NORMAL ALLOW, SOURCE UNRELIABLE, RELIABLE CONTRADICTION, INVALID MODIFY / SAFETY REFUSAL, VALID MODIFY, DUPLICATE / REPLAY | `scripts/judge_demo.py` — `.\make.ps1 judge-demo` |
| **Product-02** | Evidence Passport + Decision Inspector: both read off one shared, real `PresentationModel` — neither re-derives evidence, claims, policy or the verdict | `product/judge_presentation.py`, `product/judge_views.py` — `python -m product.judge_cli --scenario 3` |
| **Product-03** | One-screen FastAPI dashboard: profile switcher, scenario picker, RUN, RESET | `demo/web.py` — `python -m demo.web`, then open `http://127.0.0.1:8000/` |
| **Product-04A** | Dashboard hardening: no autorun on page load, query params, or refresh; a second RUN or RESET arriving while one is in flight is **rejected** (HTTP 409), never queued or silently serialized; a fixed-message error firewall (no raw exception text ever reaches the UI); RESET clears only demo-local state | same files as Product-03 — `tests/test_product04a_hardening.py` |

The dashboard exposes exactly **two** of the three governed use cases as
profiles — **Customer Support** (`servicing-v1`) and **Internal Knowledge
Assistant** (`knowledge_assistant-v1`). Each of the six scenarios is gated
by a real, server-side applicability matrix (`demo/web.py::_is_supported`):
requesting a scenario under a profile it wasn't built for returns `NOT
APPLICABLE FOR PROFILE` rather than a stale or fabricated result — verified
live for this reconciliation (e.g. `NORMAL ALLOW` only runs under
`knowledge_assistant-v1`).

The dashboard's own flagged hero is scenario 3, **RELIABLE CONTRADICTION**,
under the Internal Knowledge Assistant profile — the same DOC-2277 /
EMP-4410 cross-tenant case narrated under "Implementation approach" below,
now runnable end to end from a browser. Verified live for this
reconciliation: the agent proposes `send_document(recipient_id='EMP-4410',
doc_id='DOC-2277')`; `entitlements.db` returns
`doc_classification_permitted=true` but `recipient_entitled_to_doc=false` —
verdict **CONTRADICTED**, intervention **BLOCK**, root cause
`recipient_entitled`, execution **PREVENTED** (0 implementation calls),
receipt **VERIFIED**.

![ControlPlane judge dashboard — RELIABLE CONTRADICTION hero scenario](docs/screenshot-dashboard.png)

*(screenshot captured from an earlier render of this same commit's UI; the
page now also has a RESET control in the header that isn't visible in this
image — RESET itself is real, wired, and covered by
`tests/test_product04a_hardening.py`.)*

**Receipt vs. runtime, kept visibly separate** (see `docs/limitations.md`):
the dashboard's RECEIPT panel shows `VERIFICATION: VERIFIED` — the signed
receipt's HMAC-SHA256 signature checks out, and its stored verdict/
intervention agree with the call that just produced it. The EXECUTION panel
separately shows `STATUS: PREVENTED` / `EXECUTED` / `REPLAYED` — the real
try/except outcome of whether the tool actually ran. These are two
different fields (`receipt_verification`, `execution_state`) computed two
different ways on purpose: a verified signature is evidence about the
decision record, not about what happened afterward.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request — Python 3.11
and 3.12, `contents: read` only, `CP_MODE=fixture`, a non-production
`CP_RECEIPT_SECRET`: the Product-01/02/03/04A test suites, the P02
use-case-agnostic engine regression gate
(`tests/test_engine_is_use_case_agnostic.py`), a deterministic offline demo
smoke test (`python -m scripts.judge_demo`), and a dashboard import / `GET
/` smoke test. It deliberately does not run the full `pytest tests/ -q` —
see the workflow's own header comment for the documented pre-existing
failures (outside these product layers) that scope excludes. This
reconciliation re-ran that same scope locally against this exact tree and
every suite passed; **remote GitHub Actions have not yet been executed on
this branch as of this reconciliation** — "CI configuration validated
locally" is not the same claim as "remote CI passed."

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

Built: S0-S18, plus the judge-facing product layer above (Product-01 through
04A) and the CI workflow that exercises it. `make bench` runs SEB-1 Exp 3
(D52 cross-validation); Exp 5 (confusion matrix) is **BLOCKED** pending a
held-out gold set (task P03) — its previous version was circular and has
been retired, see `docs/experiment-audit.md`. `make review` runs a terminal
human-in-the-loop console for ESCALATE decisions (needs an interactive
human — see "Honest limitations"); the one-screen FastAPI dashboard
described above is the actual judge-facing web UI, and is a separate,
presentation-only layer over the same pipeline. `make report` regenerates
`reports/` and `summary.json` from whatever's actually in
`decisions.jsonl`, never from hand-typed numbers.

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
measurement. `make demo3` runs it; it is engineering-validated
(`tests/test_third_use_case.py`) and is not exposed as a dashboard profile
— see "Judge-facing product layer" above.

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
`bench/mutation.py` mutates scenario inputs against a genuinely
ALLOW-worthy baseline, with operators derived from the **specification**
(the `issue_refund` tool JSON schema and `manifests/servicing.yaml`) rather
than from the checks `decide()` implements — so the score is **below 1.0
by design**: it includes spec elements the gate has no mechanism to
enforce, and names which ones per operator. The earlier version derived its
operators from the six existing checks, so every mutant was caught and the
score was 1.000 by construction — retired, see `docs/experiment-audit.md`.

## Demo scenarios

| Command | What it shows |
|---|---|
| `.\make.ps1 negative` | Gate OFF — the negative control. The refund executes unchecked. |
| `.\make.ps1 demo` | Gate ON, use case 1 — the ₹42,999 scenario above. BLOCK, signed receipt. |
| `.\make.ps1 demo2` | Use case 2 — the cross-tenant document block. |
| `.\make.ps1 demo3` | Use case 3 — discount approval, added as manifest + graph data only. |
| `.\make.ps1 judge-demo` | All six Product-01 scenarios, offline, over the real pipeline. |
| `python -m demo.web` | The one-screen judge dashboard (Product-03) — open `http://127.0.0.1:8000/`. |
| `.\make.ps1 review` | Human-in-the-loop console for ESCALATE decisions (needs an interactive human — see Limitations). |

All demo scenarios run against committed, seeded LLM fixtures by default —
no API key needed (`CP_MODE=live` in `.env` switches to a real provider
call). This is an engineering demonstration of the pipeline above, over
deterministic seeded data — it is not external validation and not a live
production deployment; see "External validation" below for what has and has
not been validated outside this repository.

## Measured results

Full methodology, caveats and raw sources for every number below:
`reports/README.md`. Three headline results, each reproducible from a
committed source file at this repository state:

**1. Record-grounded evidence beats agent-trace-grounded evidence, on our
gold set.** B5 (ControlPlane: live registry queries) vs. B4 (identical
pipeline, evidence taken from the agent's own retrieved trace instead):
**100.0% vs. 87.9%** direction-accuracy on 140 non-ambiguous gold cases
(`bench/gold_set.jsonl`, P03), a **12.1-point** difference, McNemar exact
two-sided **p = 1.53e-05**, 95% CI on the difference (cluster bootstrap over
source-order clusters) **[6.6%, 19.7%]**. Of the 17 discordant cases, **16
are `stale_policy_context`** cases — B4 grounds the decision in a
superseded retrieved clause, B5 in the live one — and one is a distractor
case. *Scope: this is evidence about the evaluated failure mode (retrieval
staleness) on this gold set, not a universal claim that record-grounded
verification beats trace-grounded verification in general.* Source:
`reports/baselines.md`.

**2. There is a point past which the record's own errors dominate.**
Corrupting a growing share of `orders.db`'s delivery-date field,
ControlPlane's accuracy stays at/above the frozen B4 baseline (87.9%) only
below a **≈10.6%** record-error rate (cluster bootstrap 95% CI **[10.6%,
44.7%]**); above it, no verifier architecture helps — the record itself
needs fixing. Source: `reports/robustness.md`,
`reports/summary.json['p08_robustness']`.

**3. Gate overhead.** End-to-end median **7.67 ms** per gated call with
grounding off (1,050 calls, config C1). With optional HHEM grounding on,
the entailment call alone adds a further **~161 ms** median (p95 228 ms)
and a one-time **~9.2 s** cold model load; `CP_GROUNDING=off` is the
default for this reason. Source: `reports/latency.md`.

## External validation — tau²-bench post-mortem

We also attempted validation on `sierra-research/tau2-bench` (external,
third-party, retail domain, pinned tag `v1.0.1`) — deliberately outside our
own gold set. **Status: partial, not a completed external validation.**

- **C1 (vanilla baseline, no ControlPlane): COMPLETE.** Run under
  `Kimi-K2-Instruct` after a disclosed mid-experiment model change
  (`Qwen3-8B` stalled repeatedly and was swapped, logged as a genuine
  protocol deviation, not reward-motivated — both models scored
  `reward=0.0` on the shared task IDs). Diagnostic pass^1 (judge/infra
  failures excluded): **2/27 ≈ 7.4%** — a near-null result, consistent with
  an untuned mid-size open-weight model on a hard multi-step benchmark. This
  establishes a governance-free floor; it is not a claim about ControlPlane,
  which was not yet in the loop for C1.
- **C2 (ControlPlane + fresh policy) and C3 (ControlPlane + stale policy) —
  the comparison this experiment exists to produce — are PENDING**, not yet
  built or run.

**So: tau2-bench does not currently provide external validation of the
B4/B5 result above.** That result is our own internal, gold-set-based
evidence only. Full deviation log and methodology: `reports/tau2-bench.md`.

## Future work

Not implemented; not claimed as current capability.

- **tau2-bench C2/C3** — the external, third-party validation of the
  record-vs-trace-grounding gap. Designed, not yet run (see above).
- **Exp 5 confusion matrix** — `bench/seb1_exp5_confusion_matrix.py`
  deliberately raises `SystemExit` rather than report a number; it needs a
  held-out gold set labeled independently of `decide()`, which does not yet
  exist.
- **Logger 2 (SEB-1 extraction-accuracy-under-noise)** — reports
  `"status": "not_measured"`; needs the date-extraction harness from
  `phase 1/` ported and re-run against the live extractor.
- **Idempotency ledger durability** — the at-most-once retry guarantee (P08
  scenario 8) is in-process only; a crash between execution and receipt
  persistence is not covered.
- **Reviewer-console agreement rate** — `make review` requires an
  interactive human; no automated agreement measurement exists yet.
- **discount_approval as a dashboard profile** — currently engineering-
  validated only (agent, manifest, tests); not wired into the Product-03
  dashboard's profile switcher.

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
- **The judge dashboard is a single-process, fixture-mode demonstration**
  — no authentication, no per-browser session identity, one governed
  operation in flight at a time by design. See `docs/limitations.md` for
  the full scope boundary.

Deeper limitations — the bias-measurement framing, retired figures, the
P08 robustness findings, and the judge dashboard's own scope boundaries —
are in `docs/limitations.md`.

## Demo / video

[PENDING] — no walkthrough video is committed to this repository at this
state. If/when one is published, it will be linked here.

## Submission information

- **Event**: Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2
- **Repository**: https://github.com/hariom-s27/controlplane
- **License**: see `LICENSE`
- **Reproducibility**: `CP_SEED=20260814`, demo clock frozen at
  `CP_DEMO_DATE=2026-08-14` — see "Reproducibility" below.

---

## Repository map

| Path | What it is |
|---|---|
| `controlplane/` | The product — use-case agnostic. The gate, the registry, `bindings.py`, the receipt. |
| `agents/` | Three demo agents — servicing, knowledge assistant, discount approval. |
| `scripts/` | `judge_demo.py` (Product-01, six scripted scenarios), `probe.py`, `scrape_policies.py`. |
| `product/` | Presentation layers over the real pipeline — Product-02's Evidence Passport / Decision Inspector (`judge_presentation.py`, `judge_views.py`, `judge_cli.py`) and an earlier per-case CLI view (`views.py`/`cli.py`, `make product-demo`). |
| `demo/` | Product-03/04A — the one-screen FastAPI judge dashboard (`web.py`, `templates/`, `static/`) over Product-01/02. |
| `data/` | Committed JSON seeds + a deterministic database builder. |
| `manifests/` | Per-use-case config: thresholds, compensability, evidence bindings, and `graphs/` (the Zen JDM predicate graphs). Same engine, different behaviour. |
| `bench/` | SEB-1, the mutation harness, and the measurement scripts. |
| `docs/` | `architecture.md`, `policy-manifest.md`, receipt schema, invariants, limitations, the experiment audit, evidence. |
| `tests/` | Unit, golden-file, metamorphic, mutation, and product-layer tests. |

## Reproducibility

Everything is seeded at `CP_SEED=20260814` and the demo clock is frozen at
`CP_DEMO_DATE=2026-08-14`. `python data/build_db.py` produces byte-identical
databases on every run — `tests/test_data.py` asserts it. If you run this
code you should get the numbers we published; if you do not, that is a bug and
we want to hear about it.
