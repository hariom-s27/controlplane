# S + T. Contribution — safe now, stronger later, and the §28 paper-shaped test

## §28 — the proposed contribution statement, decomposed

> *"ControlPlane studies runtime governance under differing evidence independence. Rather than judging a tool call only from information already produced or exposed to the agent, it can adjudicate against a separately queried current system-of-record state and measure when that additional independence changes the decision."*

| # | Atomic claim | Classification |
|---|---|---|
| 1 | "studies runtime governance" | **REPOSITORY-DERIVED / SUPPORTED NOW.** `intercept.py::dispatch_tool` is a real pre-execution gate |
| 2 | "under **differing** evidence independence" | **NOT ESTABLISHED.** No experiment varies the evidence source. There is exactly one evidence configuration in the repository. This is the load-bearing word in the sentence and it is unsupported |
| 3 | "rather than judging … only from information already produced or exposed to the agent" | **SUPPORTED NOW as a design property**, TEST-DERIVED: `facts_for_predicate()` + `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine`; `registry/policy.py` cannot receive `asserted_value` |
| 4 | "adjudicate against a separately queried current system-of-record state" | **PARTIALLY SUPPORTED.** True and demonstrated for the policy path (`WHERE effective_to IS NULL` vs. the agent's unfiltered stale index). For orders and entitlements the verifier reads the **same file** the agent read; the independence there is *re-derivation*, not source separation (`12` §K.4) |
| 5 | "**and measure** when that additional independence changes the decision" | **NOT ESTABLISHED.** Nothing measures this. The only comparison is gate-ON vs gate-OFF, n=1, which measures *whether checking happens at all*, not the effect of evidence independence |
| 6 | Implied: the measurement is meaningful | **NOT ESTABLISHED.** All committed metrics are tautological (`10`) |

**Verdict on §28's statement as written: two of six atomic claims are supported, one partially, three not.** The words that do the intellectual work — *differing*, *measure* — are the unsupported ones.

---

## S. Current safe contribution

> **ControlPlane is a working prototype of a pre-execution gate for LLM agent tool calls that adjudicates the *content* of a proposed action against a freshly-queried business record, rather than against the agent's own account of that record.**
>
> **Its design commitment is a strict separation between what the agent *claimed* and what the record *says*: agent-derived fields are structurally prevented from reaching the rule engine (`ProposedAction.facts_for_predicate()`), and the clause resolver cannot receive the agent's assertion at all. It couples this with a claim-checkability taxonomy (C1 recompute / C2 look up / C3 entail / C4 consensus / C5 unverifiable) used to keep confidence claims honest — deterministic checks are treated as certain, entailment-based checks as moderate and never blocking — and per-field source-reliability classes intended to model records that are themselves unreliable.**
>
> **We demonstrate the mechanism on one constructed scenario in which a policy clause has been silently superseded: with the gate off the agent issues a refund 26 days past delivery under a 7-day policy; with the gate on the same proposal is blocked, citing the currently-effective clause and the authority ceiling, and a signed decision receipt records the query that established each fact.**
>
> **We report no performance measurement. The benchmarks in this repository are integration and regression checks whose labels are derived from the same generators as their inputs; we state this rather than reporting their accuracy as a result. There is no external validation, no adversarial evaluation and no threat model. The per-field reliability mechanism is modelled but not yet wired into the runtime.**

Every sentence above is anchored to a file this audit read. **Nothing stronger is currently supportable.**

---

## T. Stronger contribution, and exactly what earns it

| Stronger claim | Requires | Cost | Ready? |
|---|---|---|---|
| *"Evaluated on a 150-case gold set whose labels were produced by a second implementation sharing no code with the gate, with per-slice false-positive and false-negative rates and cluster-robust intervals over `source_order_id`."* | Commit `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl`, `test_label_independence.py`, `test_gold_set_holdout_isolation.py`; re-score Exp 5; add a case-cluster bootstrap | **low — `docs/gold-set.md` says all five files are written** | **Nearly. This is the whole game** |
| *"We measure when evidence independence changes the decision: four arms — agent prose, retrieved context, cached snapshot, fresh query — over identical cases, paired and cluster-bootstrapped."* | The above, **plus** the four-arm harness (`12` §K.5). Cannot be done before the gold set, or the arms score themselves | medium | Designed on the branch ("B3 the LLM-judge", "trace-grounded and live-query pipelines"), not built |
| *"Human agreement with our policy interpretation is κ = …"* | 30 labels in `bench/human_label_sample.csv`; `bench/agreement.py` already refuses partial κ | ~2 h of one person's attention | **Yes, and it is the only genuinely external judgment obtainable at this scale** |
| *"Fails safe under record unavailability and corruption."* | Fix D-03, D-04; wire `fail_posture`; build the ROADMAP's chaos test | ~1 day | No |
| *"Robust under adversarial conditions."* | A threat model and a red team. Do **not** attempt while two fail-opens stand | high | No |
| *"Generalises across domains."* | ≥3 domains with independent labels | very high | No |
| *"Externally validated."* | τ²-bench-verified or BFCL | very high | No |

---

## Overclaimed contributions to avoid

| Do not claim | Why |
|---|---|
| First / novel runtime verification of agent tool calls | arXiv 2607.07405, 2603.20953, 2603.16586, 2606.19242, 2607.02599 — all Mar–Jul 2026 |
| Novel pre-execution interception | OAP intercepts synchronously before execution; AgentLTL gates prefixes online; AgentCore Policy evaluates every tool invocation |
| Novel declarative/data-driven policy | Cedar + Dogwood (shipping product); FO-LTL; C-Trace's first-order GDPR predicates. ControlPlane's JDM expression list is the least expressive of these |
| Novel signed audit receipts | OAP: "a cryptographically signed audit record"; Aegis: Immutable Logging Kernel. Both are cryptographically stronger than a shared-secret HMAC with no chaining |
| Lower FPR / better / superior than any named system | **NOT DIRECTLY COMPARABLE** (§12A) — different metrics, denominators, populations, protocols |
| Adversarially robust / sound / secure | No threat model, no red team, two confirmed fail-opens (`09` T-3, T-4) |
| Production-ready | In-process, bypassable, SQLite, no auth, no rate limiting, no fail-posture |
| Externally validated | One external component (HHEM-2.1-Open), off by default |
| Bias tested | The probe cannot detect bias |
| Human validated | Zero human labels exist. `docs/gold-set.md` §6 already forbids this phrase — **keep that discipline** |

---

## The single sentence to lead with

> **"Most AI checkers ask another AI for a second opinion. We ask the company's own systems for the actual answer."**

Keep it. It is accurate about the design, it is the clearest articulation of the position, and it is what distinguishes the work from AgentLTL's `out(τ)` grounding and from Bedrock's Automated Reasoning checks, which explicitly consult no external data.

**Follow it immediately with the scope sentence**, because the strongest version of this project is the one that says what it has not shown:

> *"We demonstrate the mechanism; we do not yet measure how often the answer differs."*
