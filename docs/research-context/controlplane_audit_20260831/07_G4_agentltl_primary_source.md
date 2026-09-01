# F. G4 — AgentLTL primary-source forensic audit

## F.0 Provenance

| Field | Value | How obtained |
|---|---|---|
| Title | *AgentLTL: A Trace-Verification Framework for Measuring, Enforcing, and Training Procedural Compliance in Tool-Using LLM Agents* | arXiv abstract page + full HTML render, fetched 2026-08-30 |
| Authors | Laïla Elkoussy (LRE, EPITA); Julien Perez (LRE) | ibid. |
| Identifier / version | **arXiv:2607.02599v1** | ibid. |
| Date | 2026-07-01 (v1) | ibid. |
| Retrieval status | **PRIMARY SOURCE VERIFIED** — abstract and full HTML v1 retrieved, including formal definitions, benchmark description and the verbatim Limitations section | — |

**§1D compliance note:** the brief asserts an AgentLTL comparison is part of ControlPlane's positioning. No such comparison exists in the repository (`03_premise_reconciliation.md`). This audit performed the primary-source read anyway, because the result **materially constrains what ControlPlane may claim** whether or not the comparison is written down.

## F.1 What the primary source establishes

| Dimension | AgentLTL — what §-level evidence supports |
|---|---|
| Problem definition | Existing evaluation "focus[es] on final-answer correctness or LLM judges. Neither captures how an answer was produced." AgentLTL evaluates **procedural compliance** — did the agent follow the prescribed procedure |
| Specification language | A fragment of **First-Order LTL** over agent traces: atomic propositions (occurrence, ordering, argument matching, result checks), temporal operators `G F X U W R`, and data quantifiers over finite domains **extracted from the trace** |
| Trace model | `τ = ⟨c₀ … cₙ₋₁⟩`, each `cᵢ = (nᵢ, aᵢ, rᵢ, i)` = tool name, argument map, **result**, index |
| Atomic propositions | `Called(t)`, `CalledWith(t,a)`, `CalledWithResult(t,r,a)`, `BranchCalled(t⁺,t⁻)` — all "evaluated globally over τ", explicitly **"with no external data sources"** |
| **Grounding mechanism (the κ the brief asks about)** | `κ_ground ≡ ∀e ∈ ent(a), e ∈ out(τ)` where `ent(·)` extracts referential tokens (identifiers, file paths, numeric literals) and `out(τ)` is "entities observed in tool outputs". Holds iff every entity in the answer was **observed in some tool output** |
| **Witness requirement** | **YES, and it is trace-internal.** A witness must appear explicitly in a prior tool *result* within the same trace |
| Source of truth | **The recorded tool outputs themselves.** No external record is consulted |
| Tool-result assumptions | Tool results are taken as authoritative for grounding purposes. The paper does not assume infallibility so much as it never raises the question; the limitation it *does* raise is vacuity, not untruthfulness |
| Runtime vs post-hoc | **Both.** Offline scores a completed trace; **online mode evaluates prefix `τ^≤i` before each tool execution** with severities `HARD_STOP`, `SOFT_BLOCK`, `BLOCK_AND_WARN`, `TOLERATE` |
| Compliance score | Definition 1: `C(τ, G_P) = 1 − (Σ violated weights / Σ all weights) ∈ [0,1]` |
| Stale state | **Not addressed** |
| Policy handling | Constraints are FO-LTL formulas authored per procedure, before execution |
| Datasets / domains | 12 workflow templates × 5 difficulty levels over **synthetic arithmetic tools**; plus a repository-QA study, 160 (repo, question) pairs over 16 Python repos. 7 models, 26B–1000B |
| Adversarial evaluation | **None reported** |
| Headline results | compliance improvements on 5 of 7 models; accuracy gains of **+38** and **+17.5** percentage points |

### Limitations, verbatim from §8

- **Vacuous grounding:** "The trace-grounding predicate κ_ground is satisfied trivially by refusals, since the universal quantifier holds when the answer contains no entities to verify."
- **Confounded popularity:** "The popularity stratification in the grounding study confounds pretraining exposure with repository size and complexity…"
- **Synthetic environment:** "The benchmark uses synthetic arithmetic tools to keep ground truth deterministic… Whether they transfer quantitatively to noisier real-world environments… remains an open question."
- **Model finetuning:** single base model (Qwen3-4B-Instruct); "have not been replicated across scales or model families."
- **Authoring cost:** "shifts the cost of evaluation from labeling answers to writing FO-LTL constraints… must be authored by domain experts."
- **Constraint expressiveness:** "does not exhaust the space of procedural errors… FO-LTL also cannot express hyperproperties."
- **Single-turn constraints:** "evaluates each trace against a fixed specification written before execution."

## F.2 What the primary source does **not** establish

- It does **not** claim to check an agent's assertion against an external system of record. `out(τ)` is the trace.
- It does **not** address stale, superseded or contradicted authoritative state.
- It does **not** claim any adversarial-robustness property.
- It does **not** evaluate on a business-policy domain — its tools are synthetic arithmetic functions, by deliberate design.
- It does **not** produce a signed or tamper-evident audit artifact.

## F.3 The comparison — AgentLTL vs. ControlPlane as implemented

The brief's arms A1–A5 do not exist. The comparison below therefore uses **the evidence sources ControlPlane actually distinguishes in code**, which are a strict subset of the brief's ladder:

- *message/prose* → `ProposedAction.claimed_*`, excluded from predicates by `facts_for_predicate()`
- *retrieved context* → `retrieved_chunks`, `data/stale_index/chunks.json` (**gitignored**, generated)
- *structural tool-call arguments* → `order_id`, `amount_paise`, `item_colour`, `item_category`
- *fresh system-of-record read* → `controlplane/registry/*.py`

| Dimension | AgentLTL (2607.02599) | ControlPlane (`42143cf`) | Primary-source evidence | Conclusion |
|---|---|---|---|---|
| Verification moment | offline **and** online prefix gating | online only, `intercept.py::dispatch_tool` | κ definitions + online-mode §; `intercept.py` | **NOT ESTABLISHED as a distinction.** AgentLTL gates pre-execution too |
| Enforcement vocabulary | HARD_STOP / SOFT_BLOCK / BLOCK_AND_WARN / TOLERATE | BLOCK / ESCALATE / MODIFY / ALLOW / OBSERVE_ONLY | both explicit | **NOT ESTABLISHED as a distinction** — near-isomorphic |
| **Grounding source** | `out(τ)` — entities seen in prior tool outputs, "no external data sources" | a **fresh query issued at decision time** to a store the agent did not have to route through: `PolicyResolver` returns `WHERE effective_to IS NULL` and never receives `asserted_value` | κ_ground definition; `registry/policy.py` | **SUPPORTED.** This is the one clean, primary-source-backed distinction |
| Handling of *stale but present* authoritative state | not addressed | the v3.8/v4.2 supersession scenario is the project's core demo | AgentLTL §8 is silent; `data/seed/clauses.json`, `docs/evidence/negative_control.txt` | **SUPPORTED** — as a demonstrated scenario, n=1 |
| Freshness / reliability of the record | not modelled | `Reliability{corroborated, inferred, unverified}`, per-**field** not per-system | `registry/freshness.py`; `data/build_db.py` `field_reliability` table | **PARTIALLY SUPPORTED.** The model exists; the rule that fires it (`escalation_for`) is **dead code**, and the only `inferred` field is read by no servicing claim |
| Policy representation | FO-LTL formulas, expert-authored | JDM expression graph + YAML manifest + Python precedence | both explicit | **PARTIALLY SUPPORTED as a distinction** — a difference in kind (temporal vs. state predicates), but ControlPlane's is *less* expressive, not more. AgentLTL can express ordering and iteration; ControlPlane cannot express anything temporal |
| Audit artifact | none | HMAC-signed PROV-shaped receipt | `receipt.py` | **SUPPORTED as a distinction from AgentLTL** — but **NOT ESTABLISHED as novel**, see `08` (OAP, Aegis) |
| Adversarial evaluation | none | none | both | **No distinction. Neither has one** |
| Domain realism | synthetic arithmetic tools (self-declared limitation) | synthetic retail DB (self-declared limitation) | AgentLTL §8; `docs/gold-set.md` §5 | **No distinction.** Both are synthetic and both say so |
| Empirical rigour | 7 models, 12×5 templates, 160 repo-QA pairs, ablations | 1 model (replayed), 2 tools, tautological metrics | ibid.; `10_benchmark_construct_validity.md` | **AgentLTL is materially stronger.** Any comparison must concede this |
| Temporal / procedural properties | core capability (`G F X U W R`) | **absent.** `decide()` is stateless per call; `docs/invariants.md` M4 is idempotence, not a temporal property | — | **AgentLTL strictly dominates on this axis** |

## F.4 Classification of every proposed distinction

| Proposed distinction | Classification |
|---|---|
| Adjudicates against a separately-queried current system-of-record state rather than trace-internal tool outputs | **SUPPORTED** by primary source, for the *policy* path. See the caveat in `12_causal_identification.md` — for the *orders* path both the agent and the resolver read `data/orders.db` |
| Handles silently-superseded authoritative records | **SUPPORTED** as a distinction; **PARTIALLY ESTABLISHED** as a result (one scenario, replayed fixture) |
| Models per-field source reliability | **PARTIALLY SUPPORTED** — modelled, not wired |
| Runtime interception before execution | **NOT ESTABLISHED BY PRIMARY SOURCE** as a distinction — AgentLTL's online mode does this |
| Declarative policy | **NOT ESTABLISHED** — AgentLTL's FO-LTL is more declarative and more expressive |
| Signed audit receipts | **NOT ESTABLISHED** as novel (see `08`: OAP arXiv 2603.20953 produces "a cryptographically signed audit record") |
| More general | **NOT ESTABLISHED.** AgentLTL runs 7 models and 12 templates; ControlPlane runs 1 replayed model and 2 tools |
| Superior / lower error rate | **NOT DIRECTLY COMPARABLE** (§12A). Different metrics, denominators, populations and protocols. No numeric comparison may be drawn |

## F.5 The claim that survives, worded for a hostile reviewer

> "AgentLTL grounds an agent's answer in `out(τ)` — the entities observed in the trace's own tool outputs (κ_ground, §Definitions) — and its benchmark uses synthetic tools with deterministic ground truth (§8). It therefore does not address the case where the authoritative record has silently changed since the agent retrieved it. ControlPlane targets that case: at decision time it re-queries the clause store for the currently-effective clause and adjudicates against that, independent of what the agent's retrieval surfaced. We demonstrate the mechanism on one constructed supersession scenario; we do not claim a comparative evaluation against AgentLTL, whose empirical scope is substantially broader than ours."

Everything in that paragraph is backed by a cited definition or a named file. **Nothing stronger is currently supportable.**
