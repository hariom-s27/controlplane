# Prior-art matrix v2 — corrected and extended

All sources fetched or re-fetched **2026-08-31**. Retrieval status stated per row. Supersedes `08_prior_art_matrix.md`.

## Source register

| Short name | Identity | Status |
|---|---|---|
| **AEGIS** | *AEGIS: No Tool Call Left Unchecked — A Pre-Execution Firewall and Audit Layer for AI Agents*, Yuan, Su, Zhao (USC) · arXiv:**2603.12621v1** · 2026-03-13 | **VERIFIED** — corrects my earlier mis-citation of 2603.16938 |
| **LedgerAgent** | *LedgerAgent: Structured State for Policy-Adherent Tool-Calling Agents*, Uddin, Saeidi, Blanco, Baral · arXiv:**2606.20529** | **PARTIALLY VERIFIED** — abstract only; PDF did not render; HF page date inconsistent with the identifier |
| **AgentLTL** | arXiv:**2607.02599v1** · 2026-07-01 | **VERIFIED** incl. §8 verbatim |
| **C-Trace** | *Runtime Compliance Verification for AI Agents*, Kahani, Barati, Addae (Carleton) · arXiv:**2606.19242v1** · 2026-06-17 | **VERIFIED** incl. enforcement wording and Table 4 |
| **OAP** | *Before the Tool Call: Deterministic Pre-Action Authorization for Autonomous AI Agents*, Uchibeke · arXiv:**2603.20953** · 2026-03-21 | **VERIFIED** (abstract); spec repo not fetched |
| **Reddy et al.** | *Reason Less, Verify More* · arXiv:**2607.07405** · v1 2026-07-08, v2 07-11 | **VERIFIED** |
| **Policies on Paths** | Kaptein, Khan, Podstavnychy · arXiv:**2603.16586v1** · 2026-03-17 | **VERIFIED** |
| **LEDGER** | *Claim-to-Evidence Trace Graphs for Auditing LLM Agents*, Kim, Miao, Liu · arXiv:**2608.18398** · 2026-08-19 | **VERIFIED** (abstract) |
| **Auditable Agents** | arXiv:**2604.05485** | **VERIFIED** (framework + §§) |
| **Provenance survey** | *From Agent Traces to Trust*, Wang, Zhang, Wu et al. · arXiv:**2606.04990v4** · 2026-06-28 | **VERIFIED** (taxonomy §2.1, §3.2) |
| **Safe-agents survey** | arXiv:**2608.14590** | **VERIFIED** (taxonomy §4) |
| **AgentCore Policy** | AWS official developer guide | **VERIFIED**; *"intercepts all agent traffic … evaluates each request … before allowing tool access"*, *"deterministic enforcement … outside of agent's code"*, decisions logged to CloudWatch. **A named AUDIT-vs-ENFORCE mode pair was NOT found in the pages fetched — do not assert that naming** |
| **Automated Reasoning checks** | AWS official guide | **VERIFIED** — post-generation, SMT over an encoded policy, **explicitly consults no external data** |
| **Aegis (other)** | arXiv:2603.16938, Mazzocchetti | VERIFIED but **not the relevant AEGIS**; colliding name only |

---

## The matrix

| System | Enforcement point | Evidence the decision uses | Policy form | Audit integrity | Adversarial eval | Overlap with ControlPlane | Safe ControlPlane claim |
|---|---|---|---|---|---|---|---|
| **LedgerAgent** 2606.20529 | **pre-execution — "before environment-changing tool calls are executed"** | **structured ledger built from user interactions and tool returns** (trace-derived, curated) | state-dependent policy constraints | not reported | not reported | **HIGHEST. Same problem statement ("outdated or incorrect information"), same enforcement point, same domain family (4 customer-service domains), pass^k** | Distinguish **by evidence source only**: LedgerAgent curates what the agent has seen; ControlPlane re-queries the record. In A1–A5 terms LedgerAgent is a strong **A4 (CachedRead)**; ControlPlane's claim is **A5 vs A4** |
| **AEGIS** 2603.12621 | **pre-execution firewall**, interposes on the tool-execution path; human approval for high-risk | request content — deep string extraction, risk scanning | **composable policy validation** | **Ed25519 + SHA-256 hash chain** | **48/48 blocked; 1.2% FPR / 500 benign; 8.3 ms median / 1,000 interceptions; 14 frameworks** | Interception + declarative policy + signed audit, **all three, with numbers** | ControlPlane's receipt is **strictly weaker** (shared-secret HMAC, no chain, telemetry unsigned). Do not list receipt integrity as a contribution |
| **C-Trace** 2606.19242 | interceptor around the tool-calling loop; **forward / redact / block** | typed event trace annotated with data categories and purposes | 4 first-order GDPR predicates, evaluated incrementally | not reported | **yes — 4 domains incl. retail & airline, GPT-4o-mini, 4 attack families, HarmBench/AdvBench/DAN; Table 4: 0% ASR perfect extraction, ≤12% ASR and ≤16% FPR at 10% extractor noise; baselines incl. Presidio** | Interception, typed extraction, incremental predicates, **and blocking** | Different predicate class (GDPR lawfulness vs record correctness) and trace-derived evidence. Your `ALLOW/MODIFY/BLOCK` ≈ their `forward/redact/block` — do not present it as new |
| **AgentLTL** 2607.02599 | offline scoring **and** online prefix gating (HARD_STOP / SOFT_BLOCK / BLOCK_AND_WARN / TOLERATE) | **κ_ground ≡ ∀e ∈ ent(a), e ∈ out(τ)** — entities observed in tool outputs; "no external data sources" | FO-LTL over traces | none | none | Online pre-execution gating | **Evidence source is the clean distinction** (`07_G4`) |
| **OAP** 2603.20953 | synchronous interception before execution | identity / authorization | declarative policy | **cryptographically signed audit record** | **4,437 decisions, 1,151 sessions, $5,000 bounty; 74.6% → 0% over 879 attempts** | Interception + declarative policy + signed audit; **median 53 ms, N=1,000** | ControlPlane validates argument *content* against a record; OAP authorizes the *principal* |
| **Reddy et al.** 2607.07405 | deterministic read-only pre-execution gates inspecting "the proposed call **and current state**" | simulated τ²-bench DB state | 4-gate suite | none | negative controls (retail, BFCL) | **Nearest on mechanism + benchmark**; +12.4pp gpt-4o-mini (P=0.0012), +10.4pp gpt-5.2 (n=5) | Cite as validating the mechanism. **Never compare numbers** |
| **Policies on Paths** 2603.16586 | prospective (runtime) vs retrospective | agent identity, partial path, proposed action, **shared governance state Σ** | deterministic fn → [0,1] | — | — | Consulting external state at decision time is already claimed | Σ is a governance ledger, not the transactional record the claim asserts |
| **LEDGER** 2608.18398 | **post-hoc** | trace records → evidence nodes → workflow nodes, typed semantic edges | — | evidence anchors | — | **Vocabulary**: "claim-to-evidence" is published | Do not present claim/evidence binding as new framing |
| **Auditable Agents** 2604.05485 | framework: Detect / Enforce / Recover | — | — | **"evidence integrity" is one of its five dimensions** | — | Provides the rubric | **Score ControlPlane on its five dimensions honestly — free related-work table** |
| **AgentCore Policy** (AWS) | *"intercepts all agent traffic … evaluates each request … before allowing tool access"*; *"deterministic enforcement … outside of agent's code"* | identity, tool schema, session events, guardrail signals | **Cedar / Dogwood**, NL→Cedar authoring | CloudWatch logs | — | Shipping commercial product at the same enforcement point | Querying a business DB to validate argument values is **not documented**. Cedar is more analysable than a JDM expression list |
| **Automated Reasoning checks** (AWS) | **post-generation** | encoded policy only — **explicitly no external data** | SMT-LIB formal rules | — | — | Formal deterministic checking | **Strongest support for your niche**: an industrial formal checker that deliberately does not consult live data |
| **Provenance survey** 2606.04990v4 | — | six dimensions incl. provenance relations and pre-exec/runtime/post-hoc timing | — | — | — | ~50+ systems | **"Verification of agent claims against an authoritative external system of record is not among the categories it enumerates" — a documented absence in a named source.** Cite; do not convert to "first" |

---

## §8A adversarial challenge — updated verdicts

| Proposed distinction | Verdict now | Change |
|---|---|---|
| Pre-execution interception of tool calls | **SUBSTANTIALLY OVERLAPPING** | unchanged (6+ systems) |
| Deterministic non-LLM adjudication | **SUBSTANTIALLY OVERLAPPING** | unchanged |
| Declarative / data-driven policy | **SUBSTANTIALLY OVERLAPPING** | unchanged |
| Signed audit receipt | **SUBSTANTIALLY OVERLAPPING — AND STRICTLY WEAKER** | ⬇ **downgraded**: AEGIS ships Ed25519 + SHA-256 chaining with numbers |
| Blocking / intervention vocabulary | **SUBSTANTIALLY OVERLAPPING** | ⬇ **new**: C-Trace's forward/redact/block ≈ ALLOW/MODIFY/BLOCK |
| Claim → evidence binding as a framing | **PARTIALLY OVERLAPPING** | ⬇ **new**: LEDGER 2608.18398 |
| Pre-execution policy check using maintained state, stale-context motivation, customer-service domain | **SUBSTANTIALLY OVERLAPPING** | ⬇ **new and serious**: LedgerAgent |
| Per-field source-reliability classes feeding a verdict floor | **NOT ESTABLISHED** | unchanged — no counterexample found, but unwired in ControlPlane (`escalation_for()` dead code) |
| **Adjudicating the claim against a re-queried, versioned system-of-record at the decision boundary, incl. silent supersession** | **CLEARLY DISTINGUISHED** | **survives** — but the paper to beat is now LedgerAgent, and the supporting citation is survey 2606.04990 §2.1/§3.2 |

## §12A

**No numeric comparison to any row above.** AEGIS 1.2% FPR / 8.3 ms, OAP 53 ms / 0% over 879, C-Trace ≤12% ASR / ≤16% FPR, Reddy +12.4pp, LedgerAgent pass^k — all different metrics, denominators, populations and protocols. `NOT DIRECTLY COMPARABLE`, every time, in writing.

## The one-paragraph positioning that survives all of this

> Pre-execution governance of agent tool calls is an active, crowded area: AEGIS (2603.12621) firewalls the tool-execution path with composable policy and hash-chained signed audit; OAP (2603.20953) authorizes the principal synchronously; C-Trace (2606.19242) blocks GDPR-non-compliant events from a typed live trace; AgentLTL (2607.02599) gates prefixes against FO-LTL constraints grounded in `out(τ)`; LedgerAgent (2606.20529) checks state-dependent policy constraints before environment-changing calls using a curated ledger of prior observations; Reddy et al. (2607.07405) show deterministic read-only gates recover a silent policy-violation failure mode on τ²-bench. **What these share is that the evidence for the decision is derived from the agent's own execution context — its trace, its tool returns, its request, its identity.** ControlPlane asks a narrower question: what changes when that evidence is instead re-queried from the current system of record at the moment of adjudication, particularly when the record has silently changed since the agent read it. A June 2026 survey of evidence tracing and execution provenance across ~50 systems (2606.04990v4, §2.1) does not enumerate verification against an authoritative external system of record among its categories; its evidence-attribution dimension concerns alignment with retrieved documents and cited sources (§3.2).

Nothing in that paragraph claims first, novel, or unique. It does not need to.
