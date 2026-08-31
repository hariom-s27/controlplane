# B. Evidence ledger summary

Evidence type: **EXPLICIT** (stated by the source) · **INFERRED** (derived by this audit) · **NOT ESTABLISHED**.
Status: **ESTABLISHED** · **PARTIALLY ESTABLISHED** · **NOT ESTABLISHED** · **CONTRADICTED** · **NOT EXECUTABLE** (the brief's `REQUIRES P06` class, renamed because P06 was absent from the audited state).
Numeric labels: **MEASURED** (observed by running) · **DERIVED** (computed analytically here) · **REPORTED** (asserted by the repo) · **INFERRED**.

All commits are on `github.com/hariom-s27/controlplane`. Unless noted, files are as of `main` @ `42143cf`; branch items are as of `8a48bf7`.

> **Historical-state qualifier:** This audit was performed at `main` @
> `42143cf55fd7e314a735f5e05807519b8e6efb44`. That commit is now an ancestor
> of public `main` @ `6ec4261d374904f55bf5dff1a9855854f1b94819`.
> The later public commit reconciled the README and audit disclosures but did
> not change the core code paths analyzed here, so the relevant findings remain
> applicable unless explicitly superseded. Branch observations, including
> `8a48bf7`, describe refs visible at audit time; they do not establish that
> later or off-release work is merged, current, or public.

---

## B.1 Architecture and mechanism claims

| ID | Claim | Source | Exact location | Observation | Interpretation | Type | Conf. | Status |
|---|---|---|---|---|---|---|---|---|
| A-01 | Tool calls are intercepted before execution | source | `controlplane/intercept.py::dispatch_tool` | `impl(**args)` is reached only after `_run_gate` unless `session.gate_enabled` is false | Interception is real at the Python function boundary | EXPLICIT | high | **ESTABLISHED** |
| A-02 | The choke point is non-bypassable | README §Implementation ("the single choke point"), `CLAUDE.md` | `intercept.py:165` | `if not session.gate_enabled: return impl(**args)`; `SessionContext` is caller-constructed; `REGISTRY[name]` and `_issue_refund_impl` are ordinary module-level Python objects | Bypass requires only constructing a `SessionContext` with `gate_enabled=False`, or importing the impl. There is no enforcement boundary | INFERRED | high | **CONTRADICTED** (as a security property) / ESTABLISHED (as a code-discipline property) |
| A-03 | Agent-asserted values never reach the rule engine | `schema.py` module docstring; `predicates/__init__.py::evaluate` | `ProposedAction.facts_for_predicate()` | Returns exactly `tool, order_id, amount_paise, currency, recipient_id, doc_id, item_colour, item_category`; `evaluate()` passes only that | The R1 architectural rule is genuinely enforced in code, and `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine` guards it | EXPLICIT | high | **ESTABLISHED** — the strongest single implementation claim in the repo |
| A-04 | The policy resolver cannot see the agent's assertion | `controlplane/registry/policy.py::PolicyResolver.resolve` | `WHERE policy_id = ? AND effective_to IS NULL` | The resolver's signature does not receive `asserted_value`; the SQL has no reachable path to it | Structurally true, not merely disciplined | EXPLICIT | high | **ESTABLISHED** |
| A-05 | Evidence values are raw facts, never verdicts | `controlplane/registry/orders.py` docstring: "never a verdict" | `registry/entitlements.py` returns `value=class_ok` and `value=customer_ok` — booleans that *are* the verdict | Use case 2 violates the stated architecture; the entitlement decision is computed in Python inside the resolver, and the JDM graph merely renames it (`knowledge_assistant.json`: `"classification_permitted": "evidence.classification_permitted"`) | INFERRED | high | **CONTRADICTED** for use case 2; ESTABLISHED for use case 1 |
| A-06 | Business rules are data, not code | README ("a Zen Engine JDM graph, not Python `if` statements") | `predicates/graphs/servicing.json` | One `expressionNode` with 6 scalar expressions; no decision table, no branching. Verdict precedence, intervention selection, reliability floor and compensability are all Python in `decide.py` | The *predicates* are data; the *policy* is code | INFERRED | high | **PARTIALLY ESTABLISHED** |
| A-07 | "Same engine, different behaviour" via manifest | README; `manifests/*.yaml` | grep of every manifest key across `--include=*.py --include=*.json` | Read by code: `window_days`, `authority.<role>.ceiling_paise`, `reliability_floor`, `verdict_handling`. **Never read anywhere:** `latency_budget_ms`, `escalation_budget_pct`, `fail_posture`, `evidence_retention_days`, `risk_tier_default` | 4 of 9 manifest fields are functional; 5 are declarative decoration. For the knowledge-assistant graph neither `window_days` nor the ceiling is referenced at all | INFERRED | high | **PARTIALLY ESTABLISHED** |
| A-08 | Receipts are signed and tamper-evident | `controlplane/receipt.py` | `hmac.new(_secret(), _canonical(receipt), sha256)` | HMAC-SHA256 with a shared secret from `.env`. No hash chain, no sequence number, no asymmetric signature | Detects modification by a party without the key. Provides **no** non-repudiation, **no** append-only property, and **no** detection of line deletion | INFERRED | high | **PARTIALLY ESTABLISHED** |
| A-09 | Telemetry is covered by the signature | `controlplane/telemetry.py::record` | `persist({"receipt": receipt, "telemetry": {...}})` | `sig` is computed over `receipt` only; the four telemetry blocks are outside it | Coverage / latency / promotion figures on the operational trail are unsigned | INFERRED | high | **NOT ESTABLISHED** (unclaimed by the repo, but load-bearing if telemetry is ever cited as evidence) |
| A-10 | `decide()` is pure | `CLAUDE.md` hard constraint #4 | `controlplane/decide.py` | No I/O, no clock, no logging; `_idempotency_key` is a hash of its inputs | Purity holds by inspection | EXPLICIT | high | **ESTABLISHED** |

## B.2 Empirical / numeric claims

Rows N-01 through N-04 are independent findings of this forensic audit. The
current public release independently records retirement of the same four
headline figures, for the same structural reason, in
`docs/retired-figures.md`; neither record is presented as having generated
the other.

| ID | Claim | Source | Location | Observation | Type | Label | Status |
|---|---|---|---|---|---|---|---|
| N-01 | "100% verdict accuracy with the R3 `attributes_match` check … 75% without" | README Honest limitations; `c653b7f` commit message | `bench/seb1_exp3_cross_validation.py::run` | `gold_verdict` and `predicate_result["attributes_match"]` are both functions of the single generator variable `resolves_to_distractor`; accuracy-with is 1.0 identically, accuracy-without is `1 − P(wrong resolution)` = `1 − 0.5×0.5` = 0.75 | INFERRED | **DERIVED** (not measured) | **NOT ESTABLISHED as a result** — see `10`, `13` |
| N-02 | Exp 5 4×4 confusion matrix / accuracy | `bench/seb1_exp5_confusion_matrix.py` | `_generate()` | Each gold class is produced by setting exactly the input that `decide()` deterministically maps to that class. Accuracy is 1.000 unless `decide()` is broken | INFERRED | **DERIVED** | **NOT ESTABLISHED as a result** (valid as a unit test) |
| N-03 | Mutation score | `controlplane/mutation.py`; `docs/invariants.md` | `MUTATORS` + `_decide_for` | All 6 operators are analytically guaranteed to leave ALLOW: confidence→NONE ⇒ UNVERIFIABLE; amount>ceiling ⇒ BLOCK; days=8 ⇒ BLOCK; version v3.8≠v4.2 ⇒ BLOCK; customer mismatch ⇒ BLOCK; reliability INFERRED < floor ⇒ SOURCE_UNRELIABLE. Score = 1.000 | INFERRED | **DERIVED** | **NOT ESTABLISHED as a result**. The repo's own framing ("a lower bound and a regression signal") is the correct one and should be the only one used |
| N-04 | Bias probe: "no detectable difference", MDE 0.17 at n=200 | `controlplane/bias_probe.py`; README | `run_probe()` | The group label is drawn *after* the scenario, by an independent coin flip, and is never passed to `decide()`. There is no code path by which it could influence the outcome | INFERRED | **DERIVED (null is structural)** | **NOT ESTABLISHED as a bias result.** Valid as an RNG-independence sanity check only |
| N-05 | HHEM grounding scores 0.921 / 0.023; load ~13.2 s; ~0.1–0.5 s per call | README S8 paragraph | `tests/test_ground.py` (gated by `pytest.importorskip("transformers")`); `bench/report.py:41-43` | Two fixtures, n=1 each; latency constants hard-coded into the report generator | EXPLICIT | **REPORTED**, n=1, no artifact committed | **PARTIALLY ESTABLISHED** (plausible, unreproducible from the repo) |
| N-06 | Gate condition: "3/5 proposed a refund unprompted — PASS" | `docs/evidence/gate_condition_check.txt` | produced by `scripts/gate_check.py` | `gate_check.py:42` unpacks **3** values from `agents.servicing_agent.propose()`, which returns **4** (`tuple[dict\|None, dict, str, list[str]]`). The script raises `ValueError` as committed | INFERRED | **REPORTED**, not reproducible | **CONTRADICTED** as reproducible evidence; the transcript predates the current `propose()` signature |
| N-07 | Receipt "~1 KB" target / test asserts <2 KB | `receipt.py` docstring; `tests/test_receipt.py` | test builds a 1-claim, 1-evidence decision | README concedes the real BLOCK receipt is **~3.8 KB**. The test's fixture is a strawman that cannot fail | INFERRED | **REPORTED** | **CONTRADICTED** (the test does not test the claim it names) |

## B.3 Literature claims made *inside the shipped artifact*

| ID | Claim | Where in repo | Primary source | Status |
|---|---|---|---|---|
| L-01 | "published NLI SOTA (77.4%)" bounds C3 | `controlplane/ladder.py` docstring; `ground.py` | LLM-AggreFact leaderboard, top entry **Bespoke-MiniCheck-7B = 77.4** (fetched 2026-08-30) | **ESTABLISHED as a number**, but see L-02 |
| L-02 | That bound applies to the deployed checker | `ground.py` uses **HHEM-2.1-Open** | HHEM-2.1-Open **does not appear** on the LLM-AggreFact leaderboard. Bespoke-MiniCheck-7B is CC BY-NC and was *deliberately excluded* per `requirements.txt` | **NOT ESTABLISHED.** The honest-coverage argument is anchored to the accuracy of a model the project does not run |
| L-03 | USPS OIG: 163 of 500 packages (32.6%) marked "Out for Delivery" while still at the origin office | `schema.py`, `registry/freshness.py`, `docs/ROADMAP.md:327` | USPS OIG report **22-159-R23**, 2023-05-11: 500 packages, **163** displayed "Out for Delivery" while **still at the post office** | **ESTABLISHED numerically** (163/500 = 32.6%). **Minor accuracy defect:** the report says "still at the post office", not "origin office" |
| L-04 | "USPS OIG found `delivered_at` scans problematic at 2.45%" | `controlplane/schema.py::Reliability` docstring | Report 22-159-R23 reports 64% inaccurate messages, 163 OFD, 46 missing, 497 nondescriptive. **2.45% does not appear** | **PRIMARY SOURCE NOT VERIFIED** — may come from a different OIG report; as cited it is unsupported |
| L-05 | Two-tier receipt driven by the *Mobley v. Workday* privilege ruling | `receipt.py` docstring; `docs/decision-receipt.md` | 2026 N.D. Cal. rulings on privilege over AI bias-testing data are widely reported in legal commentary | **CONTEXT ESTABLISHED, PRIMARY SOURCE NOT VERIFIED** (court order text not retrieved). The design decision is defensible; the citation should name the order and date |
| L-06 | Just & Ernst, FSE'14 caveat on mutation testing | `docs/invariants.md`; `mutation.py` | Not fetched in this audit | **PRIMARY SOURCE NOT VERIFIED.** The caveat as stated is standard and unlikely to be wrong, but it is uncited to a retrievable identifier |
| L-07 | EU AI Act Art. 26(6) six-month log minimum | `manifests/servicing.yaml` comment | Not fetched | **PRIMARY SOURCE NOT VERIFIED** |

## B.4 The brief's own premise

| ID | Brief statement | Repository evidence | Status |
|---|---|---|---|
| P-01 | τ² integration exists | 0 hits for `tau2`/`tau-bench` in any blob on any branch | **EXPLICITLY ABSENT** |
| P-02 | Evidence-source arms A1–A5 exist | 0 hits for any arm name | **EXPLICITLY ABSENT** |
| P-03 | P06 C1 is COMPLETED and FROZEN | 0 hits for `P06`; `reports/` and `decisions.jsonl` are gitignored; no frozen artifact of any kind is committed | **NOT EXECUTABLE** |
| P-04 | "A5 can be 100% accurate by construction" is the G3 question | No A5. **However, the isomorphic defect is real and present**: Exp 3, Exp 5, mutation and bias probe are each 100%-by-construction | **RESTATED AND ESTABLISHED against the artifact that does exist** — see `06_G3_falsifiability.md` |
| P-05 | An AgentLTL comparison exists in the repo | 0 hits | **EXPLICITLY ABSENT.** The primary-source audit of AgentLTL was performed anyway (`07`) because it is repo-independent and materially changes the defensible claim |
