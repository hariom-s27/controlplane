# Corrections to my own audit

You asked me to check your work. Two of your corrections land on mine. Both are yours, both are right, and one of them makes ControlPlane's position materially weaker than I reported.

---

## 1. AEGIS — I cited the wrong paper. You are correct.

**What I wrote** (`08_prior_art_matrix.md`, Aegis row): arXiv:**2603.16938**, *"Cryptographic Runtime Governance for Autonomous AI Systems: The Aegis Architecture for Verifiable Policy Enforcement"*, Mazzocchetti, 2026-03-15.

**What is actually the relevant AEGIS** (verified 2026-08-31):

> **AEGIS: No Tool Call Left Unchecked — A Pre-Execution Firewall and Audit Layer for AI Agents**
> Aojie Yuan, Zhiyuan Su, Yue Zhao (USC) · arXiv:**2603.12621v1** · 2026-03-13

Both papers exist and both are named Aegis. **The one that matters for ControlPlane is 2603.12621, and it is far closer prior art than the one I cited.** My search matched on "runtime governance" and surfaced the wrong Aegis; I did not adversarially re-search on "pre-execution firewall". That is the §8A failure mode my own audit warned about, committed by the audit.

### What 2603.12621 actually reports

| Dimension | AEGIS (2603.12621) |
|---|---|
| Enforcement point | **Pre-execution firewall — "interposes on the tool-execution path"**, blocks dangerous calls before they take effect |
| Pipeline | deep string extraction → risk scanning → **composable policy validation** |
| Human in the loop | approval path for high-risk operations |
| **Audit integrity** | **Ed25519 signatures + SHA-256 hash chaining**, tamper-evident |
| Adversarial result | **48/48 attack instances blocked** |
| False positives | **1.2% on 500 benign tool calls** |
| Latency | **8.3 ms median overhead over 1,000 interceptions** |
| Generality | **14 agent frameworks**, Python / JavaScript / Go |

### What changes as a result

1. **The signed-receipt claim is weaker than I said.** I wrote that ControlPlane's HMAC "must not be claimed as a strong integrity property" because of the shared secret, absence of chaining, and unsigned telemetry. AEGIS ships **exactly the two mechanisms ControlPlane lacks** — asymmetric signatures and a hash chain — five months earlier, with numbers. Receipt integrity is now not merely un-novel; ControlPlane's version is **strictly weaker than published prior art**. Either adopt hash-chaining (~2 h, `R04` Phase 3) or drop integrity from the contribution list entirely.
2. **"Pre-execution firewall" is a claimed and measured category.** Three of the four architectural pillars — interception, composable declarative policy, signed audit — are AEGIS's abstract.
3. **AEGIS has the adversarial evaluation ControlPlane does not.** 48/48, 1.2% FPR, 8.3 ms. Any reviewer who knows this paper will ask why ControlPlane has none.
4. **AEGIS has generality evidence ControlPlane does not.** 14 frameworks vs. two hand-built demo agents.
5. **§12A still binds:** do **not** put AEGIS's 1.2% next to any ControlPlane number. Different populations, different denominators, different protocol. `NOT DIRECTLY COMPARABLE`.

**Action:** use `arXiv:2603.12621` in every literature artifact. Delete `2603.16938` unless you separately want the cryptographic-governance paper, in which case cite it as a distinct system with a colliding name.

---

## 2. LedgerAgent — I reported PRIMARY SOURCE NOT VERIFIED. It exists, and it is your nearest competitor.

**What I wrote:** *"No system by that exact name was located. Nearest verified match: AgentLedger (SSRN 6417378)."* Wrong. I searched on "tamper-evident ledger / audit" and the paper is about **structured state for policy adherence**, so my query missed it.

**What it actually is** (verified 2026-08-31):

> **LedgerAgent: Structured State for Policy-Adherent Tool-Calling Agents**
> Md Nayem Uddin, Amir Saeidi, Eduardo Blanco, Chitta Baral · arXiv:**2606.20529**
> *(Date discipline: the arXiv identifier places this in June 2026. The Hugging Face paper page displays "June 18, 2024", which is inconsistent with the identifier. I could not render the PDF — abstract-level verification only. Resolve the date from the arXiv listing before citing.)*

### Why this is the most dangerous paper on your list

Its abstract, near-verbatim:

- policy-adherent tool-calling agents in **customer-service domains** must maintain task state across turns while calling tools and obeying **domain policies**;
- standard agents embed state implicitly in the prompt, so they reconstruct context repeatedly and **"risk grounding decisions in outdated or incorrect information"**;
- LedgerAgent keeps observed task state in a **separate ledger** and renders it into the prompt;
- **"the ledger is also used to check state-dependent policy constraints *before environment-changing tool calls are executed*"**;
- evaluated across **four customer-service domains**, open- and closed-weight models, improving **average pass^k**, largest gains under stricter multi-trial consistency.

Line by line, that is: your problem statement (stale context), your enforcement point (pre-execution, before environment-changing calls), your domain family (customer service; four domains), and your metric family (pass^k). Published before your C1.

### The distinction that survives — and it is now a single clause

LedgerAgent's ledger is assembled from **"facts, identifiers, constraints and conditions extracted from user interactions and tool returns."** That is *trace-derived* state — the same class as AgentLTL's `out(τ)`. It is a better-organised memory of what the agent has already seen. It is **not an independent re-query of the authoritative store at the decision boundary**.

So the surviving ControlPlane claim is:

> *Prior systems that check policy before a tool call — LedgerAgent (2606.20529), AEGIS (2603.12621), AgentLTL (2607.02599), C-Trace (2606.19242), OAP (2603.20953) — evaluate against state derived from the agent's own execution context: the trace, the tool returns, the request, the identity. ControlPlane asks what changes when the evidence for that decision is instead **re-queried from the current system of record at the moment of adjudication**, including when that record has silently changed since the agent read it.*

That is one clause wide. It is defensible. It is **not** defensible without naming LedgerAgent, because a reviewer who knows it will assume you did not.

**Action:** LedgerAgent becomes a top-three related-work entry with its own paragraph, not a list item. And your A1–A5 ladder maps onto it directly: LedgerAgent is a **strong A4 (CachedRead)** — a structured, curated cache of prior observations. Your claim is about **A5 vs A4**, and that is a much sharper framing than "runtime governance."

---

## 3. C-Trace — I understated it. You are right that it blocks.

I described C-Trace as intercepting and evaluating incrementally. It also **enforces**. Verified today:

> *"an interceptor around the tool-calling loop evaluates the predicates incrementally over the live trace, **blocks non-compliant events**"* — with three decisions: **forward / redact / block**.

And its evaluation is closer to your setting than I said: **four domains including retail and airline**, GPT-4o-mini as the tool-calling agent, four attack families, DSPy-generated variants plus HarmBench/AdvBench/DAN prompts, 400/400 traces validated across Python, Rego and MFOTL implementations. Table 4: **0% ASR under perfect extraction; ASR ≤ 12% and FPR ≤ 16% under 10% per-category extractor noise**; baselines include no-monitor, random-50%-blocking, regex PII filters and Presidio.

**Consequence:** C-Trace is not just an architectural template you borrowed from — it is a *runtime enforcement* system evaluated on retail and airline with an adversarial suite and baselines. The `forward / redact / block` triple is also close to your `ALLOW / MODIFY / BLOCK`.

---

## 4. Three papers neither of us had

Found today while checking your list.

| Paper | Why it matters |
|---|---|
| **LEDGER: Claim-to-Evidence Trace Graphs for Auditing LLM Agents** — Kim, Miao, Liu · arXiv:**2608.18398** · 2026-08-19 | Uses **"claim-to-evidence"** as its organising vocabulary, with typed semantic edges binding claims to supporting actions, artifacts and checks. **Post-hoc, trace-only, no external queries** — so it does not threaten your mechanism, but it does mean *claim/evidence binding* is now published vocabulary. Cite it; do not present the framing as new. |
| **From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in LLM Agents** — Wang, Zhang, Wu et al. · arXiv:**2606.04990v4** · 2026-06-28 | This is your "June 2026 provenance survey", verified. ~50+ systems, six dimensions (trace sources; evidence/execution units; **provenance relations incl. Support, Derive, Contradict, Invalidate**; granularity and **timing: pre-execution / runtime / post-hoc / continuous**; representation; trust functions). **It is also your best positioning asset — see below.** |
| **Auditable Agents** · arXiv:**2604.05485** | Position paper. Five dimensions of agent auditability — action recoverability, lifecycle coverage, **policy checkability**, responsibility attribution, **evidence integrity** (append-only / hash-chained / signed). Mechanism classes **Detect / Enforce / Recover**. Evaluates AEGIS as its runtime example (§4.2), and argues in Table 5 that no prior system covers all five jointly. **This is a ready-made evaluation rubric — score ControlPlane on it honestly and you get a defensible related-work table for free.** |

### The survey is the single best positioning asset you have

Fetched today, of that ~50-system, six-dimension survey:

> **The survey does not discuss verifying agent claims against external databases or systems of record.** Its evidence-attribution treatment (§3.2) concerns whether claims align with *retrieved documents and cited sources* in RAG contexts — not cross-referencing agent outputs against canonical data systems.

That is a **documented absence in a named, dated, comprehensive secondary source** — categorically different from "we searched and found nothing", which §27 forbids you from converting into a novelty claim. You can write:

> *"A June 2026 survey of evidence tracing and execution provenance across ~50 systems organises the field along six dimensions including provenance relations and pre-execution/runtime/post-hoc timing (arXiv:2606.04990v4, §2.1). Verification of agent claims against an authoritative external system of record is not among the categories it enumerates; its evidence-attribution dimension concerns alignment with retrieved documents and cited sources (§3.2)."*

Then stop. Do not add "therefore we are first." The sentence is stronger without it.

---

## 5. Corrections to apply to the earlier audit files

| File | Change |
|---|---|
| `08_prior_art_matrix.md` | Replace the Aegis row (2603.16938) with **AEGIS 2603.12621** and its four numbers; add **LedgerAgent 2606.20529**, **LEDGER 2608.18398**, **Auditable Agents 2604.05485**, **survey 2606.04990**; correct the C-Trace row to say it **blocks**, and add retail/airline/GPT-4o-mini/Table-4 |
| §8A adversarial challenge | *Signed audit receipt* moves from SUBSTANTIALLY OVERLAPPING to **SUBSTANTIALLY OVERLAPPING AND STRICTLY WEAKER** (AEGIS: Ed25519 + SHA-256 chain). *Adjudicating against the versioned record* stays **CLEARLY DISTINGUISHED**, but the counterexample to beat is now **LedgerAgent**, not AgentLTL |
| `09_G5_threat_model.md` T-7 | Add: AEGIS demonstrates hash-chained + asymmetrically-signed receipts, so the gap is a design choice, not a state-of-the-art limit |
| `20_contribution_statement.md` | "Do not claim novel signed audit receipts" → strengthen to **"do not claim receipt integrity as a contribution at all until chaining exists"** |
| `07_G4_agentltl_primary_source.md` | Still correct as written. Add that the A4/A5 distinction now runs primarily against LedgerAgent |

`R02_PRIOR_ART_V2.md` is the corrected matrix.
