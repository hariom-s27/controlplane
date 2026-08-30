# ControlPlane.ai — Round 2 BUILD SPEC

**Compiled 27 Aug 2026 · Deadline ~6 Sep (10 days) · 2–3 people, full days**
Companion to `controlplane-round2-runbook.md`. Web version: https://claude.ai/code/artifact/5c949be1-5623-41f8-b460-43c8bfc5d8b4
The Runbook's §02 ("Block 0") is captured verbatim in-repo at `docs/round2-runbook-block0.md` — including the OC-curve reformulation P07 Fix 7 needs.
Drop this in the repo as `docs/ROADMAP.md` and tick items off as you go.

---

# §0 — DECISIONS LOCKED TODAY

## 🔴 1. Featherless supports native tool calling on only TWO model families

Featherless is OpenAI-compatible at `https://api.featherless.ai/v1`, but their tool-calling docs are explicit: **native function calling works on `moonshotai/Kimi-K2-Instruct` and the Qwen 3 family only.** Everything else needs `response_format={"type":"json_object"}` + careful prompting.

This splits cleanly onto your two LLM jobs:

- **The agent** (S2) *must* emit a real tool call — that's the whole premise. Run it on a **Qwen 3 instruct model or Kimi-K2**. Pin the exact string in `.env.example` as `CP_MODEL`.
- **The extractor** (S4) only needs valid JSON matching a Pydantic schema. Use **Instructor in `Mode.JSON`, not `Mode.TOOLS`.** If you leave Instructor on its TOOLS default you get silent empty extractions on most models and lose an afternoon.

**Do the provider probe before anything else (S0).** Ten minutes now, or a wasted day on day four.

## 2. Firecrawl has exactly one job

Not research — research is closed. Use it to make the policy corpus **real**: scrape 2–3 public retailer returns/refund policies, build `policy_store.db` from actual published clause text, then hand-author the version pair on top. Cache to `data/seed/policies_raw.json` and **commit it** so the repo builds offline.

"Our policy corpus is scraped from real published returns policies; only the version history is synthetic" is a materially stronger README sentence than "we made up a policy." ~40 minutes, cheapest credibility you can buy.

## 3. The Round 1 deck is recovered — and it's the PRE-FIX version

The uploaded PDF is the submitted deck: cover · instructions · team details · Slide 1 (Problem statement) · Slide 2 (Proposed solution) · blank video slide · Thank you.

**Three fixes from your own final-slides doc never made it in:**
1. Slide 1 still says "Companies have never checked more than 1–5% of interactions" (falsifiable absolute — remove)
2. Slide 1 still says "3% sample → misses it fully" (shorten to "misses it")
3. Slide 2's old "75% of traffic finishes in 1–20 ms" figure was a **design target**, not a measurement — retired. **P09 measured it** (`reports/latency.md`, `summary.json['p09_latency']`): 4 configurations × 1,050 gated calls. Headline: gate end-to-end **median 7.67 ms, p95 12.7 ms, p99 14.5 ms, max 26.5 ms** (C1 — HHEM off, sequential). HHEM-on and concurrency-10 profiles are reported separately (HHEM `ground` stage p50 161 ms dominates every tail metric; concurrency=10 in-process worsens per-call latency ~22× off / ~7× on while roughly halving throughput). Cite the measured number, never the old figure or the n=15/n=24 interims.

**The Team details slide is still placeholder names and stock photos.** The template prints "All fields are mandatory" on it.

✅ Good news: the SEB-1 table on Slide 2 is already the corrected version (0.0% / 97.2% / +97.2pp with the tie row visible). Carry it forward.

## 4. Capacity changes what ships

10 days × full days × 2–3 people ≈ **160–240 person-hours** against a build with a hard core of ~30. That is permission to ship the things the Runbook listed as first-to-cut: the reviewer console, the metamorphic harness, the mutation score, the promotion curve. Those four turn "we built a demo" into "we measured something."

**Three tracks:** **A** = the gate · **B** = proposal/deck/video · **C** = evidence, measurement, QA. With two people, C folds into A in mornings and B in afternoons. **Rule: B never waits on A.** The proposal is written from the design, not the code, so a build slip never becomes a submission slip.

---

# §1 — STATE IN FIVE BUCKETS

## 1. Completed and defensible — do not redo

| Asset | Where | Use it for |
|---|---|---|
| **Conceptual core** — Checkability Ladder C1–C5, Load-Bearing Claim, Evidence Strength Hierarchy 1–7, verification budget as constrained optimisation, Decision Receipt | Round 1 analysis; master log §1–2 | Every design decision in §3. This is the spec the code implements. |
| **Research base** — ~24 monitors taxonomised, patents, EU AI Act clause-level, 20 papers with extraction tables, adjacent fields | Paper set; R3/R4/R5 streams; numbers vault | The business proposal and the README's related-work. Not for more research. |
| **Decision register D1–D54** with reversals logged | master log §5 | Every "why did you build it that way" question. Cite decision numbers in code comments. |
| **SEB-1** — two scripts that run and reproduce exactly (seed 20260814) | `servicing_extraction_bench.py`, `seb1_v2_recoverability.py` | Drop into `bench/` day 1. Real running code you already have. |
| **Corrected headline** — 0% vs 97.2% on the 30% with no date | fixes-completed.md; console screenshot | Slide 2, video, README. Already correct on the Round 1 deck. |
| **Two constructed statistical artifacts** — bias-probe power tables, verification cost model | R3 stream 8 | The bias answer (S14) and the business case. Both original. |
| **Round 1 deck + narration script** | Uploaded PDF + final-slides doc | Round 2's baseline. Same template, same claims, tightened. |
| **Runlayer Condition Field Reference screenshots** | The four mislabelled PNGs | D41's primary evidence. Rename → `docs/evidence/`. |
| **Block 0 closed** — Wix + Reddy et al. read, distinction paragraph written | Runbook §02 (captured verbatim: `docs/round2-runbook-block0.md`) | README positioning + proposal novelty claim. |

## 2. Started but not finished

| Item | Exists | Missing | Step |
|---|---|---|---|
| SEB-1 experiment programme | Exp 0 (noise sweep) + v2 re-scoring | Exp 3 (`order_id` cross-val), exp 5 (confusion matrix), exp 2 (corrupt DB), exp 1 (LLM configs) | S16 |
| Round 1 deck | Built and submitted | 3 unapplied fixes; team slide placeholder | §7 |
| Metamorphic invariants | 3 drafted in prose | 2 more, formal statement, harness | S15 |
| Compensability axis (D49) | Adopted as a decision | The table and its effect on the decision surface | S9 |
| Monitorability paragraph (D50) | Adopted, "text outstanding" | The paragraph | `docs/monitorability.md` |

## 3. Needs improvement or validation before it ships

| Item | Problem | Fix |
|---|---|---|
| **The Deming sentence** | Citations real but paywalled/unread; current phrasing appears to invert the theorem's assumption set (kp rule is proved for a process *in statistical control*) | **P07 Fix 7 — unblocked.** Use the verbatim Runbook §02 reformulation now captured at `docs/round2-runbook-block0.md` ("Safe reformulation, which survives either reading:"): *"Acceptance sampling rests on operating-characteristic curves, and OC curves assume binomial or hypergeometric draws at a constant proportion nonconforming — i.i.d. defects from a process in statistical control. A superseded policy document is a textbook assignable cause: it produces the same error on every retrieval that touches it, which violates the i.i.d. assumption directly rather than merely straining it. And Deming's own inspection criterion says that even in the well-behaved stable case, the cost-optimal policy is zero or everything — never the 1–5% that contact-centre QA actually runs. Sampling theory says sampling is the wrong tool here, and it says so twice, for two different reasons."* Never put "Deming, 1986" as a bare slide attribution; cite Papadakis 1985 only for the 0%/100% criterion. |
| C-Trace citation | arXiv page returned an empty PDF last fetch | Re-pull, screenshot Table 8, store in `docs/evidence/` |
| Superseded figures | `+36 points` · `63.3%/99.2%` as headline · `55.8% whole-record` · `8% on HARD` · `15× swing` · `DBNR 2–3%` · `97–98% order accuracy` · the fabricated Runlayer sentence | Grep every artifact. Put the kill list in `docs/limitations.md` as "figures we retired and why" — a differentiator, not an admission. |
| "75% of traffic finishes in 1–20ms" | Retired: modelled, not measured. | **Replaced by P09's measured profile** (`reports/latency.md`, 4 configs × 1,050 gated calls): gate end-to-end median **7.67 ms**, p95 12.7 ms (HHEM off, sequential). The old figure and the n=15/n=24 interims are superseded; `summary.json['p09_latency']` holds the exact per-stage percentiles. |
| SEB-1's closed vocabulary | Extractor's fallback list contains the exact phrases the generator emits | Name it in `docs/limitations.md`. Optionally fix in S16 with LLM-generated paraphrases. |

## 4. Completely remaining

Everything in §3 onwards. **There is no product code yet.** Gate, registry, receipt, manifests, second use case, responsibility layer, loggers, console, repo, README, video, proposal, deck — all from zero, against a design specified and adversarially tested for seven sessions.

## 5. What the finished project looks like

A public GitHub repo a stranger can clone and run with one command. It starts a servicing agent that, unprompted, proposes a wrong ₹42,999 refund because it retrieved a superseded policy clause. It shows that action executing with the gate off. Then with the gate on: the tool call is intercepted, the agent's claim is extracted into typed events, each claim is classified on the Checkability Ladder, the delivery date is read from the order database rather than the customer's sentence, the current policy clause is fetched fresh rather than trusted from context, the predicate fires, and the action is blocked with a signed receipt (measured median 2,282 bytes, p95 3,763 bytes, n=120) naming the clause, the query, the value, the version and the root cause.

Then the **same engine, same code path, different manifest** runs an internal knowledge assistant where the predicate is entitlement rather than correctness — and blocks a cross-tenant document send that a PII scanner would have waved through, because the leaked data is legitimate PII belonging to someone else.

Alongside it: four measured numbers nobody else will have (claim coverage by tier, extraction accuracy under noise, per-stage p50/p95/p99, rule-promotion cost curve), a metamorphic invariant suite that runs on unlabelled traffic, a mutation score, a confusion matrix by verdict class, a reviewer console that makes the human commit before seeing the verdict, and a README whose limitations section is the most credible thing in the repo.

---

# §2 — THE TEN DAYS

| Day | Focus | Track A (gate) | Track B (proposal/deck/video) | Track C (evidence/QA) |
|---|---|---|---|---|
| **1** | Foundations | S0 scaffold + **provider probe** · S1 data layer (Firecrawl corpus, 3 DBs) | README skeleton; recover + fix Round 1 deck; fill team slide | Re-fetch C-Trace + screenshot Table 8; rename Runlayer evidence; grep the kill list |
| **2** | **Negative control** | S2 agent loop + stale index (**GATE: agent must propose the bad refund on its own**) · S3 interception | Proposal: problem framing + solution design | The 5 design docs: compensability, monitorability, invariants, receipt schema, manifest schema |
| **3** | Extraction & evidence | S4 extraction (Instructor `Mode.JSON`) · S5 ladder · S6 registry | Proposal: target users, business case, phased roadmap | S11 logger scaffolding, wired in as A goes |
| **4** | 🔴 **The gate closes** | S7 predicates · S8 grounding · S9 verdict/intervention · S10 receipt — **MILESTONE: ORD-88461 blocked with a correct receipt** | Proposal: risks + mitigations from the red team's own objections | First unit tests over `decide()` |
| **5** | Instrument & generalise | S11 four loggers wired · S12 manifests (extract every hardcoded threshold) | Round 2 deck on the Accenture template; Slides 1–2 updates | S16 exp 5 (confusion matrix) — the brief asks for FP/FN by name |
| **6** | **Second use case** | S13 knowledge assistant + manifest · S14 responsibility (PII + entitlement) | Deck: architecture, prototype, metrics slides | S16 exp 3 (`order_id` cross-validation) |
| **7** | Measurement | S15 invariants + mutation · S18 report generation | Video storyboard + asset list; record terminal captures | S14 counterfactual twin probe + power tables |
| **8** | Console & polish | S17 reviewer console · a cleanly-ALLOWED second case · the "41st time this week" aggregate | README: approach, architecture, deps, execution, limitations | Full clean-clone test on a second machine |
| **9** | Freeze & record | **Code freeze at midday.** Repo hygiene: LICENSE, no secrets, seeds, one-command run | Record the demo video against the frozen build. Check the exported file, not the editor estimate | Verification pass: every number traced to the run that produced it |
| **10** | Submit | Final deck export · `Team name_Idea Name.pptx` · spell check · Arial · repo public · README renders · video plays logged-out. **Ship nothing built on day 10.** | | |

## The two hard gates

- **End of day 2:** the unmodified agent proposes the wrong refund without being told to. If it doesn't, you have no negative control and the whole demo is a puppet show. **Fix the retrieval index, not the prompt.**
- **End of day 4:** the gate blocks ORD-88461 and prints a correct receipt. If this slips past day 5, execute the cut order in §8 immediately — drop the console, mutation harness and twin probe, and protect the second manifest.

---

# §3 — ARCHITECTURE AND THE CONTRACTS BETWEEN STAGES

```
  CUSTOMER MESSAGE
        │
  [0] AGENT            Featherless / Qwen3 · one tool · stale retrieval index
        │              emits: ToolCall{name,args} + justification + retrieved_chunk
        ▼
  [1] INTERCEPT        dispatch_tool()  ← the single choke point. D2, D27.
        │              everything below happens before _impl_issue_refund() runs
        ▼
  [2] EXTRACT          Instructor + Pydantic, Mode.JSON
        │              ToolCall + prose → ProposedAction + list[Claim]
        │              ⚠ extracts what the agent CLAIMED, never the facts themselves
        ▼
  [3] CLASSIFY         Checkability Ladder → each Claim gets a tier + a resolver
        │              C1 recompute · C2 query record · C3 entail document · C4/C5 none
        ▼
  [4] RESOLVE          Ground Truth Registry → Evidence{value, source, query,
        │              fetched_at, freshness_ms, reliability_class, confidence}
        │              orders.db · policy_store.db (FRESH read) · clock · entitlements.db
        ▼
  [5] PREDICATE        Zen Engine JDM graph → PredicateResult + decision trace
        │              7-day window · ₹25k ceiling · order↔customer · amount ≤ order total
        ▼
  [6] GROUND           HHEM-2.1-Open · C3 claims only · claimed clause vs fresh clause
        ▼
  [7] VERDICT          VERIFIED | CONTRADICTED | UNVERIFIABLE | SOURCE-UNRELIABLE
        ▼
  [8] INTERVENE        severity × confidence × reversibility × compensability
        │              manifest supplies thresholds, fail posture, escalation budget
        │              → ALLOW | MODIFY | BLOCK | ESCALATE | OBSERVE_ONLY
        ▼
  [9] RECEIPT          signed JSON, median 2,282 B / p95 3,763 B (n=120) → decisions.jsonl + HTML
        ▼
  [10] TELEMETRY       coverage · extraction accuracy · per-stage latency · promotion
        ▼
  [11] PROMOTE         offline: which C3 decisions a deterministic rule could have caught
```

## The five type contracts — write these FIRST, in `controlplane/schema.py`

Everything else is a function between two of these. Getting them right on day 1 is what lets three people work in parallel without merge pain.

```
ToolCall          name: str · args: dict · agent_justification: str · retrieved_chunks: list[str]
                  session: SessionContext{customer_id, agent_role, use_case, trace_id}

ProposedAction    tool: str · order_id: str · amount_paise: int · currency: str
                  claimed_policy_version: str | None · claimed_delivered_at: date | None
                  # claimed_* are what the AGENT asserted. Possibly wrong. Possibly absent.

Claim             id: str · kind: ClaimKind · subject: str
                  asserted_value: Any | None · tier: Literal["C1","C2","C3","C4","C5"]
                  load_bearing: bool

Evidence          claim_id: str · value: Any · source: str · query: str
                  fetched_at: datetime · freshness_ms: int
                  reliability_class: Literal["corroborated","inferred","unverified"]
                  confidence: Literal["certain","high","moderate","none"]

Decision          verdict: Verdict · intervention: Intervention · reasons: list[Reason]
                  evidence: list[Evidence] · predicate_trace: dict
                  latency_ms: dict[str,float] · root_cause: str | None
                  compensation: CompensationPlan | None · manifest_id: str
```

## 🔴 THE ONE DESIGN RULE THAT CARRIES THE WHOLE PITCH

**The extractor produces claims. The registry produces facts. They never come from the same place.**

`ProposedAction.claimed_delivered_at` may be `None` and that is fine — it is *not an input to the predicate*. The predicate reads `Evidence` where `source == "orders.db"`. If you ever pass a `claimed_*` field into the predicate engine, you have accidentally rebuilt ARCH-A and the demo now proves the opposite of what you want.

**Enforce it in code:** give `ProposedAction` a method `facts_for_predicate()` returning only `order_id`, `amount_paise`, `currency`, and make the predicate engine accept nothing else from that object. A five-line guard that makes the architecture claim unfalsifiable by your own implementation.

---

# §4 — REPO LAYOUT

Create this on day 1, empty. A stranger reading the tree should understand the architecture before opening a file.

```
controlplane/
├── README.md                  approach · architecture · deps · execution · limitations
├── LICENSE                    Apache-2.0
├── Makefile                   make setup · make demo · make bench · make report · make test
├── pyproject.toml
├── .env.example               FEATHERLESS_API_KEY, FIRECRAWL_API_KEY, CP_MODEL
├── docs/
│   ├── architecture.md
│   ├── decision-receipt.md    the schema + a worked example
│   ├── policy-manifest.md
│   ├── compensability.md      D49 — the classification table
│   ├── monitorability.md      D50 — the scoping paragraph
│   ├── invariants.md          D51 — the five metamorphic relations
│   ├── limitations.md         the honest section + retired figures
│   └── evidence/              Runlayer screenshots, C-Trace Table 8, receipts
├── data/
│   ├── seed/                  committed JSON — repo builds offline
│   │   ├── policies_raw.json  Firecrawl output, cached
│   │   ├── clauses.json       v3.8 / v4.2 pair, hand-authored
│   │   ├── orders.json        ORD-88461 + Faker filler
│   │   └── entitlements.json
│   └── build_db.py            seed → three .db files, deterministic
├── controlplane/              ← THE PRODUCT
│   ├── schema.py              the five contracts
│   ├── intercept.py           dispatch_tool()
│   ├── extract.py             Instructor Mode.JSON
│   ├── ladder.py              Checkability Ladder
│   ├── registry/
│   │   ├── base.py            Resolver protocol
│   │   ├── orders.py  policy.py  clock.py  entitlements.py
│   │   └── freshness.py       per-field reliability → SOURCE-UNRELIABLE
│   ├── predicates/
│   │   ├── engine.py          Zen Engine wrapper
│   │   └── graphs/*.json      JDM decision graphs
│   ├── ground.py              HHEM-2.1-Open, C3 only
│   ├── decide.py              verdict → intervention
│   ├── compensation.py        registry of compensating actions
│   ├── receipt.py             build · sign · persist · render
│   ├── manifest.py            policy manifest loader
│   ├── responsibility/
│   │   ├── pii.py  entitlement.py  bias_probe.py
│   ├── cost.py                effort ratio
│   └── telemetry.py           the four loggers
├── manifests/
│   ├── servicing.yaml
│   └── knowledge_assistant.yaml
├── agents/
│   ├── servicing_agent.py     use case 1 — the refund
│   ├── knowledge_agent.py     use case 2 — the document
│   └── llm.py                 Featherless client + fixture cache
├── bench/
│   ├── servicing_extraction_bench.py   SEB-1 (existing)
│   ├── seb1_v2_recoverability.py       (existing)
│   ├── exp3_orderid.py  exp5_confusion.py
│   ├── metamorphic.py  mutation.py
│   ├── promotion.py  report.py
├── console/                   FastAPI + HTMX, commit-then-reveal
├── reports/                   generated — coverage.md, latency.md, *.png
└── tests/
```

---

# §5 — BUILD STEPS S0 → S18

Each step carries eleven fields. Work them in order; the dependency chain is real. Where a step says **GATE**, do not proceed with a known failure.

---

## S0 — Scaffold and provider probe · 2h · Day 1 · Track A

**What.** Create the repo tree from §4 (empty files fine), set up the Python env, and **prove your Featherless model actually emits a tool call and returns valid JSON under `response_format`** before anything depends on it.

**Why.** Featherless supports native function calling on only two model families. Discovering on day 4 that your model silently ignores `tools=[...]` costs the day and probably the second use case.

**How.** Write `agents/llm.py` with one function `chat(messages, tools=None, json_schema=None)` against `https://api.featherless.ai/v1` using the `openai` client with `base_url` overridden. Then `scripts/probe.py`:

```
1. plain completion returns text
2. tools=[issue_refund] returns a tool_calls block          ← must pass
3. response_format={"type":"json_object"} returns JSON      ← must pass
```

Run against a `Qwen/Qwen3-…-Instruct` model first, `moonshotai/Kimi-K2-Instruct` as fallback. Pin whichever passes both to `CP_MODEL`.

**Tools.** python 3.11 · uv/venv · `openai` (as OpenAI-compatible client) · `pydantic>=2` · `python-dotenv`. Concepts: OpenAI-compatible chat completions; native tool calling vs JSON-mode prompting.

**Inputs.** Featherless API key. The model catalogue to pick an exact model string.

**Output.** Repo tree, working `.env`, a probe printing three PASS lines. Commit it — it doubles as the README's setup check.

**Connects to.** S2 uses assertion 2. S4 uses assertion 3.

**Verify.** `python scripts/probe.py` prints three PASS lines with model name and observed latency. Paste that output into the README.

**Problems.** Rate limits on a shared key with three people. Model-string typos returning 404 rather than a useful error. Cold-started models where the *first* call takes tens of seconds — measure the second call.

**Alternatives.** If neither family passes assertion 2: keep the agent's tool call as a **JSON-mode emission** your loop parses into a `ToolCall`. The demo is unaffected — ControlPlane intercepts at `dispatch_tool`, a Python function boundary, not a provider feature. Say so in the README; it's a strength. Last resort: a scripted agent with a fixture file, clearly labelled.

---

## S1 — The data layer: three stores and a stale index · 4h · Day 1 · Track A

**What.** Build `orders.db`, `policy_store.db`, `entitlements.db` deterministically from committed JSON seeds, plus the deliberately stale retrieval index that makes the agent fail honestly.

**Why.** These are the "systems of record" the whole pitch turns on. The liveness that matters is **procedural, not infrastructural**: two independent reads of the same store, one from the agent's stale context and one a fresh query at decision time. SQLite delivers that; Postgres and Docker buy nothing. Say this in the README before a reviewer says it for you.

**How.**

*Policy corpus (Firecrawl, ~40 min).* Scrape 2–3 public retailer returns policies. Cache to `data/seed/policies_raw.json` and **commit it** so the repo builds offline. Then hand-author the version pair:

```yaml
clauses:
  - policy_id: refund_window   version: v3.8
    text: "...full refund within 30 days of delivery..."
    effective_from: 2025-11-01  effective_to: 2026-08-01
    superseded_by: v4.2
  - policy_id: refund_window   version: v4.2      # ← current
    text: "...full refund within 7 days of delivery..."
    effective_from: 2026-08-01  effective_to: null
```

*Orders.* Hand-author the demo row precisely — do not generate it. `ORD-88461`, `customer_id=CUST-2291`, `delivered_at=2026-07-19`, `amount_paise=4299900`, `order_status='delivered'`, item "blue running shoes". Then Faker/Mimesis for 80–120 filler rows. Add a second cleanly-allowable row (delivered 3 days ago, ₹8,499) for the ALLOW demo.

*Reliability columns.* Every field gets a `reliability_class` in a metadata table: `delivered_at`/`amount_paise`/`customer_id` = `corroborated`; `order_status` = `inferred`. This is where SOURCE-UNRELIABLE comes from, grounded in the USPS OIG finding that 32.6% of packages were marked "Out for Delivery" while still at the origin office.

*The stale index.* A keyword or TF-IDF index over chunked clause text containing **both** v3.8 and v4.2, unfiltered by `effective_to`. That is the whole bug, and it's a real one — VersionRAG measured naive RAG at 0–10% on silent supersession.

**Tools.** `sqlite3` (stdlib) · `faker`/`mimesis` (MIT) · `firecrawl-py` · `rank_bm25` or sklearn TF-IDF. **Not SDV** — BUSL-1.1 since 2023, and over-powered for hand-specified rows. Concepts: versioned records with `effective_from`/`effective_to`; temporal validity; per-field data reliability.

**Inputs.** Firecrawl key (optional after the first cached run). Demo numbers fixed by the Round 1 deck: ORD-88461, ₹42,999, delivered 2026-07-19, 7-day window, ₹25,000 ceiling.

**Output.** Three `.db` files rebuilt identically by `python data/build_db.py`, plus `data/stale_index/`. DBs and index gitignored; seeds committed.

**Connects to.** S2 retrieves from the stale index. S6's resolvers query the DBs. S12's manifests reference the reliability classes.

**Verify.** Three assertions in `tests/test_data.py`: (1) querying the current clause returns v4.2 and only v4.2; (2) the stale index returns v3.8 in its top 3 for "refund window after delivery"; (3) `build_db.py` run twice produces byte-identical files. That third one makes the whole demo reproducible.

**Problems.** Firecrawl returning JS-rendered nothing on some retail sites — try two or three, fall back to hand-authored with a note. Store dates as ISO strings and parse explicitly; never let SQLite's loose typing decide. Don't let Faker generate a filler row colliding with the demo scenario — seed it and assert uniqueness.

**Alternatives.** Skip Firecrawl entirely if it fights you. For retrieval, plain substring match over chunks is enough — the point is that the wrong version is reachable, not that retrieval is sophisticated.

---

## S2 — The agent loop and the negative control · 5h · Day 2 · Track A · 🔴 GATE

**What.** A minimal servicing agent: customer message → retrieve from the stale index → propose `issue_refund(order_id, amount_paise, currency)`. Then run it **with the gate off** and watch the money move.

**Why.** This is the negative control and the single most persuasive thirty seconds of the demo video. A demo that only shows the fix is a demo nobody believes. It also proves the failure is real rather than staged.

**How.** Loop: neutral system prompt describing the process (not the answer) → retrieve top-3 chunks → call the model with `tools=[issue_refund_schema]` → parse `tool_calls` → `dispatch_tool(...)`. The headline customer message:

```
"hi, the blue running shoes I ordered arrived a while back
 but they don't fit at all — can I get a full refund?"
```

Notice what is *not* in that sentence: a date, an order ID, or an amount. The agent has to resolve them — the SEB-1 result made visible.

Add `--gate on|off`. With `off`, `dispatch_tool` calls the impl directly and prints `REFUND ISSUED ₹42,999 · order ORD-88461`. That line is your money shot.

**Fixture caching.** Wrap every LLM call so responses cache to `data/fixtures/<hash>.json`. Commit the fixtures for demo scenarios. The repo then runs end-to-end with no API key — what a judge cloning it at 11pm needs.

**Tools.** `agents/llm.py` from S0. Concepts: the agentic tool-calling loop; RAG retrieval; VersionRAG (naive RAG 58% on version-sensitive questions, 0–10% on silent supersession); *Moffatt v. Air Canada* as legal precedent for liability over a chatbot's invented policy.

**Inputs.** S0's probe passing. S1's stale index and DBs.

**Output.** A terminal transcript of the agent reasoning from v3.8 and proposing ₹42,999, then executing. Save as `docs/evidence/negative_control.txt`.

**Connects to.** Everything. S3 wraps this. The video opens with it.

**Verify.** 🔴 **THE GATE CONDITION:** run five times with different phrasings and confirm the agent proposes the refund in the majority of runs *without* the prompt telling it to. If it refuses or asks a clarifying question, **fix the index, not the instruction.** Never add "you should approve this refund" to the prompt — that's the puppet show and a mentor will spot it.

**Problems.** An over-cautious model asking for the order number — give the session context a `customer_id` and let the agent look up that customer's recent orders as a second tool. A model hallucinating an order ID — that's fine and interesting; it's exactly what S7's `order_id` cross-validation catches, so keep the transcript.

**Alternatives.** If the model won't cooperate, script the tool call from a fixture and label it plainly in the README as a replayed trace. You lose some credibility on the agent and **none** on the gate, which is the actual product. Do not fake it silently.

---

## S3 — The interception boundary · 2h · Day 2 · Track A

**What.** `controlplane/intercept.py::dispatch_tool(name, args, session)` — the single function every governed action passes through, and the only place the real implementation is called.

**Why.** D2 and D27. Portkey exposes only LLM-request lifecycle hooks and evaluates text on "the last message"; LiteLLM's `async_pre_call_hook` is documented not to fire for MCP tool dispatch. Neither can gate a structured tool call. **A Python function boundary is a legitimate interception point** — and it's what LangGraph's `interrupt()`-in-tool pattern reduces to underneath.

**How.** A registry mapping tool name → `(impl, action_spec)`, where `action_spec` carries risk tier, compensability class, and the claim template.

```python
def dispatch_tool(name, args, session):
    spec = REGISTRY[name]
    if not gate_enabled(session):          # the negative control
        return spec.impl(**args)
    decision = gate.evaluate(ToolCall(name, args, ...), session)
    emit_receipt(decision)
    if decision.intervention is ALLOW:    return spec.impl(**args)
    if decision.intervention is MODIFY:   return spec.impl(**decision.modified_args)
    if decision.intervention is BLOCK:    raise Blocked(decision)
    if decision.intervention is ESCALATE: return queue_for_review(decision)
```

Instrument it as the timing choke point: one `time.perf_counter()` at entry, one per stage, one at exit. Every latency number in the submission comes from here.

**Tools.** Plain Python. `contextvars` for the trace ID. Concepts: the reference-monitor pattern; PoE's **separate who plans, who authorises, who mutates, who records** — the gate authorises, the impl mutates, the receipt records, the agent plans, and none is the same object.

**Inputs.** S2's agent emitting a `ToolCall`.

**Output.** A working wrapper that currently just passes through, plus a stage-timing harness. Ship it before the gate logic exists so S4–S10 drop in one at a time.

**Connects to.** Calls S4–S10 in sequence. Emits to S11.

**Verify.** A test registering a fake tool, dispatching with the gate off and on, asserting the impl is called exactly once in ALLOW and exactly zero times in BLOCK. **That second assertion is the product's core guarantee** — test it explicitly.

**Problems.** Exceptions from the gate itself leaking through and letting the action run. Wrap `gate.evaluate` in try/except applying the manifest's **fail posture**: fail-open Tier 0, fail-closed Tier 2. Not a detail — it's the design finding from Copilot Studio's default, which proceeds on timeout.

**Alternatives.** Optional credibility layer on day 8: re-platform the identical `gate.evaluate` as a LangGraph `interrupt()` callback inside the tool. The gate logic doesn't change, which is the point — it answers "is this a mock?" for about an hour of work.

---

## S4 — Claim extraction: free-form to typed events · 4h · Day 3 · Track A

**What.** Turn the tool call plus the agent's justification and retrieved chunk into a `ProposedAction` and a list of typed `Claim` objects.

**Why.** C-Trace's most important finding, from two directions: its monitor hits 0% attack success with perfect extraction and degrades to ≤12% at 10% per-category noise; the out-of-band defence literature independently names provenance assignment as the under-specified TCB. **The policy engine is easy. Extraction is hard, and it's also the moat** — the Ground Truth Registry is not "connections to systems," it's the schema mapping this enterprise's language onto typed checkable events.

**How.** Instructor patched onto the Featherless client in **`Mode.JSON`**. Extract in two passes:

```
Pass 1 — structural, no LLM. order_id, amount_paise, currency come
  straight from the tool call args. Zero ambiguity, zero cost.

Pass 2 — semantic, LLM. From justification + retrieved chunk:
  claimed_policy_version, claimed_delivered_at, claimed_clause_text,
  and the list of load-bearing claims the customer will act on.
```

Then generate `Claim` objects from an `action_spec` template. For `issue_refund`:

- `within_refund_window` — subject `ORD-88461`, asserted `None`
- `amount_within_authority` — asserted `4299900`
- `order_belongs_to_customer` — asserted `CUST-2291`
- `policy_clause_current` — asserted `v3.8` ← **this is the one that breaks**
- `amount_not_exceeding_order` — asserted `4299900`

Mark `load_bearing=True` on the 1–3 the customer will act on. That's the Load-Bearing Claim principle and your biggest latency lever — you verify three claims, not twenty sentences.

**Tools.** `instructor` (MIT) · `pydantic` v2 · the S0 client. **Not Outlines** — needs logits access, which a hosted endpoint doesn't expose. Concepts: constrained/structured generation; retry-on-validation-failure; why *reason-then-constrain* beats token-level constraint here.

**Inputs.** S0 assertion 3 passing. S3's `ToolCall`.

**Output.** A `ProposedAction` and 3–6 `Claim` objects per action, plus extraction latency and a per-field success flag for the noise sweep.

**Connects to.** S5 classifies the claims. S11's extraction-accuracy logger reads the flags.

**Verify.** Golden-file tests: five fixed tool calls with hand-written expected `ProposedAction` JSON. Exact match on structural fields, schema validity on semantic. Then the important negative test: **assert that `claimed_delivered_at` being `None` does not raise and does not block** — absence is a normal expected state, not an error.

**Problems.** 🔴 Instructor defaulting to `Mode.TOOLS` and returning empty objects on models without native tool calling — the single most likely time-sink in this build. Set the mode explicitly. Also: models returning JSON wrapped in markdown fences; log the raw response on validation failure.

**Alternatives.** If structured extraction proves flaky, fall back to a rule-based extractor for semantic fields — you already have one in SEB-1 scoring 83.8% on recoverable cases. The pitch doesn't weaken, because **the verifier never reads a date anyway**; the semantic pass only recovers what the agent *claimed*, which then gets contradicted by the registry.

---

## S5 — The Checkability Ladder · 2h · Day 3 · Track A

**What.** `ladder.py` maps each `Claim` to a tier C1–C5 and selects the strongest available resolver.

**Why.** D3's operating rule: **never use a weaker method when a stronger one applies.** The direct answer to the brief's instruction not to assume an LLM can judge an LLM, and it produces UNVERIFIABLE as a first-class output instead of a fabricated confidence score. It's also where O1 — the coverage number, named in Session 1 as "the most persuasive single number in the entire submission" — becomes measurable.

**How.** A declarative table, not an if-chain, so it's inspectable and the README can print it:

```
ClaimKind                     Tier  Resolver            Confidence
within_refund_window          C1    derive(orders,      certain
                                    policy, clock)
amount_within_authority       C1    recompute           certain
order_belongs_to_customer     C2    orders.db           high
amount_not_exceeding_order    C2    orders.db           high
policy_clause_current         C2    policy_store.db     high
clause_semantics_match        C3    HHEM entailment     moderate
customer_intent               C5    —                   none  → UNVERIFIABLE
```

Note `within_refund_window` is **C1**, not C2: it's a subtraction over two values that are themselves C2. Deriving rather than asking is the whole hierarchy in one row — worth a sentence on the slide.

**Tools.** Plain Python, a dataclass table. Concepts: the Checkability Ladder; the Evidence Strength Hierarchy; C3 entailment as the honest bottleneck — SOTA on LLM-AggreFact is 77.4%, not certainty.

**Inputs.** S4's claims. **Output.** `[(claim, tier, resolver_name)]` and the first coverage line in `decisions.jsonl`.

**Connects to.** S6 executes the resolvers. S11 computes `coverage = (c1+c2+c3)/claims_total`, reported *per tier* so it's visible C1/C2 are exact and C3 is probabilistic.

**Verify.** A test asserting every `ClaimKind` in the enum has a row — a missing row must fail loudly, not silently default to C5. And a test that C5 claims produce UNVERIFIABLE rather than an exception.

**Problems.** The temptation to route everything to C3 because it's easy. Resist: the coverage number is only impressive if C1/C2 dominate, and only honest if you didn't cheat the classification.

**Alternatives.** None needed — this is a table, not an algorithm.

---

## S6 — The Ground Truth Registry · 5h · Day 3 · Track A

**What.** One resolver per source behind a single `Resolver` protocol, each returning a fully-attributed `Evidence` object. Plus the per-field freshness layer producing SOURCE-UNRELIABLE.

**Why.** This is the wedge made executable. Every other runtime monitor asks the enterprise's systems *who the actor is and what they're allowed to do*. This asks *what is actually true*. It needs its own module rather than inline queries because of the receipt: every value must carry its query, source, freshness and reliability class, or the receipt is a claim rather than evidence.

**How.**

```python
class Resolver(Protocol):
    name: str
    def resolve(self, claim: Claim, ctx: SessionContext) -> Evidence: ...
```

- **`orders.py`** — one parameterised SELECT per claim kind. Record the exact SQL in `Evidence.query`; it goes on the receipt verbatim and it's what makes the demo feel real.
- **`policy.py`** — the critical one. Query `WHERE policy_id=? AND effective_to IS NULL`, **completely independently of what the agent retrieved.** This is the procedural liveness. Return the version string so the receipt can say "claimed v3.8, current v4.2, superseded 2026-08-01."
- **`clock.py`** — injectable so tests can freeze time. Never `datetime.now()` inline.
- **`freshness.py`** — looks up each field's `reliability_class` and compares to the manifest's minimum. `inferred` fields (like `order_status`) used for a high-severity decision yield SOURCE-UNRELIABLE, which escalates rather than blocks.

**Tools.** `sqlite3` · `typing.Protocol`. Concepts: system of record vs cache; consistency tokens (Zanzibar — 99.999% availability, <10ms p95) as the answer to 15× read amplification across a 15-step trajectory; per-field rather than per-system freshness policy.

**Inputs.** S1's DBs. S5's tier assignments. **Output.** A list of `Evidence` objects with real query strings and measured `freshness_ms`.

**Connects to.** S7 evaluates predicates over this. S10 puts it on the receipt.

**Verify.** Three tests: (1) the policy resolver returns v4.2 even when the agent's retrieved chunk is v3.8 — this is the whole demo, test it directly; (2) a missing `order_id` returns `Evidence` with `confidence="none"`, not an exception; (3) an `inferred`-class field on a high-severity claim yields SOURCE-UNRELIABLE.

**Problems.** Timezone drift between the clock, stored dates, and `effective_from`. Pick UTC, store ISO-8601, parse explicitly, put the timezone on the receipt. A one-day off-by-one produces a 26/27-day discrepancy someone will spot on the video.

**Alternatives.** To show the CDC-vs-live-query design (O9) without building it: add `freshness_mode: live|cached` to the manifest, implement `cached` as a deliberately 200ms-stale read, and demonstrate that a stale read on a corroborated field is fine while a stale read on an in-flight field trips SOURCE-UNRELIABLE. Two hours, makes the per-field argument concrete.

---

## S7 — The predicate engine · 4h · Day 4 · Track A

**What.** Evaluate business rules over resolved evidence, and emit an inspectable trace of which rule fired.

**Why.** The rules must be data, not code, or the "configurable policy layer" the brief asks for by name is a lie. A renderable decision graph is also the best artifact for "how is this auditable" — you show the graph, not the source.

**How.** `pip install zen-engine` (MIT, in-process, no sidecar — a real risk with OPA during a live demo). One JDM graph per use case in `predicates/graphs/`:

```
R1  days_elapsed = clock − evidence.delivered_at
    days_elapsed <= policy.window_days                    → within_window
R2  amount_paise <= authority[role].ceiling_paise         → within_authority
R3  evidence.order.customer_id == session.customer_id     → entity_match   [D52]
R4  amount_paise <= evidence.order.amount_paise           → amount_sane
R5  claimed_version == current_version                    → clause_current
```

**R3 is the highest-value check in the pipeline** and the project's own measurement says so. Tool-call interception concentrates the entire verification burden onto `order_id`: resolve it wrong and everything downstream is confidently wrong about the wrong order. Extend beyond identity — also match described attributes ("blue", "shoes") against the order's item description, and the amount band.

Guard the input: the engine receives `{evidence: {...}, action: proposed.facts_for_predicate(), manifest: {...}}` and nothing else. **No `claimed_*` field crosses this boundary.**

**Tools.** `zen-engine` (MIT). Concepts: DMN decision tables as the business-owned policy layer; separating the rate of change of policy from the rate of change of the engine.

**Inputs.** S6's evidence. S12's manifest (hardcoded defaults initially, extracted day 5).

**Output.** `PredicateResult` with per-rule pass/fail and the JDM trace as a dict.

**Connects to.** S9 turns results into a verdict. S10 puts the trace on the receipt. S12 swaps the graph per manifest.

**Verify.** A table-driven test with eight cases: within window / outside / **exactly at the boundary** / amount at ceiling / over ceiling / customer mismatch / amount exceeding order / clause version mismatch. Is day 7 inside or outside? Decide, document it in `docs/policy-manifest.md`, test it.

**Problems.** JDM authoring being slower than expected. Timebox to three hours; if it fights you, implement R1–R5 as plain Python predicates behind the same interface and **say so in the README rather than calling it a rules engine.** Honesty costs nothing; the theatrical alternative costs credibility. Also: **integer paise everywhere. Never floats for money.**

**Alternatives.** `json-logic-py` (MIT) as a middle ground — declarative and serialisable but looks like a toy. OPA/Rego is most enterprise-credible and has no official Python SDK, meaning a sidecar that can die mid-demo. Zen Engine is right precisely because it's in-process.

---

## S8 — Grounding, the C3 tier · 3h · Day 4 · Track A

**What.** Compare the clause text the agent *relied on* against the clause text *currently in force*, and detect contradiction.

**Why.** R5 already catches the version mismatch by metadata, which is cheaper and more reliable. So why build this? Two reasons: it handles the case where the version *matches* but the agent paraphrased the clause into something it doesn't say — the ordinary hallucination case the brief names; and it gives you a real C3 tier to measure, which is what makes the coverage number honest. Without it you'd be claiming 100% deterministic coverage, which nobody will believe.

**How.** `vectara/hallucination_evaluation_model` (HHEM-2.1-Open, Apache-2.0, ~0.1B params, <600MB RAM, CPU-viable). Premise = the freshly-queried clause. Hypothesis = the agent's paraphrase. Score below the manifest threshold → CONTRADICTED at *moderate* confidence.

Load the model once at process start, not per call. Time it separately — it will dominate tail latency, and **that's a finding to report, not a bug to hide.** The vendor figure is ~1.5s for 2k tokens; your clause comparisons are an order of magnitude shorter, so measure yours.

Optionally add `lytang/MiniCheck-Flan-T5-Large` (770M, MIT) as a second checker and report checker **agreement**. Disagreement between two checkers on the same input is genuinely interesting and nobody in the guardrail market reports it.

**Tools.** `transformers` · `torch` (CPU) · HHEM-2.1-Open. Concepts: NLI/entailment for groundedness; why 77.4% SOTA on LLM-AggreFact means C3 is probabilistic; MiniCheck reaching GPT-4 grounding accuracy at 770M params and ~400× lower cost — the answer to "why not just use GPT-4 as the checker."

**Inputs.** S6's fresh clause. S4's `claimed_clause_text`. **Output.** An entailment score, a boolean, a measured latency.

**Connects to.** S9 folds it in at *moderate* confidence — and per D3, low confidence never blocks on its own.

**Verify.** Three fixtures: identical text (high score), the v3.8/v4.2 pair (low score), and **a faithful paraphrase of v4.2 (high score)**. That third is the false-positive check and it's the one people skip.

**Problems.** A ~500MB model download in the clone path. Make it optional: `CP_GROUNDING=off` skips C3 and the demo still runs, with the README saying which claims are then unverifiable. Torch install size on Windows — pin the CPU-only wheel index.

**Alternatives.** Skip C3 entirely and report coverage as C1/C2 only, with C3 listed as designed-not-built. Defensible, costs three hours. **Do not substitute an LLM judge here** — it contradicts the project's own central argument and a mentor will use it against you.

---

## S9 — Verdict and intervention, including compensability · 4h · Day 4 · Track A

**What.** Turn predicate results and evidence into one of four verdicts, then choose an intervention over **four independent dimensions plus compensability**.

**Why.** The brief's "decision logic" answered with more rigour than a confidence threshold. And D49 closes the real hole: **"block" is not always available.** A high-risk fully-compensable action (a refund — reversible by a chargeback) is a completely different design problem from a low-risk non-compensable one (an email already sent). Risk tier and compensability are different axes, and the model had only the first.

**How.**

*Verdict.* Any load-bearing predicate fails → CONTRADICTED. Any load-bearing claim unresolvable → UNVERIFIABLE. Any evidence below the manifest's reliability floor → SOURCE-UNRELIABLE. Otherwise VERIFIED.
**Precedence: SOURCE-UNRELIABLE > CONTRADICTED > UNVERIFIABLE > VERIFIED** — you cannot trust a contradiction derived from a source you don't trust.

*Compensation registry* (`compensation.py`), built from the D49 table:

```
issue_refund        → reverse_refund        FULLY compensable
update_entitlement  → restore_entitlement   PARTIALLY (window-bounded)
send_customer_email → —                     NOT compensable
send_document       → revoke_access         PARTIALLY (it was read)
```

*Intervention rules*, in order, each traceable to a decision:

- **Not compensable + verdict ≠ VERIFIED → BLOCK.** Block is mandatory for this class; there is no undo.
- **Irreversibility dominates severity.** Only 0.8% of agent actions appear irreversible (Anthropic telemetry) — the strict path is narrow by construction.
- **Low confidence never blocks** (D3). A C3-only contradiction escalates.
- **MODIFY is subtractive or additive only** — redact, caveat, constrain. **Never substitutive.** If you could reliably rewrite a wrong conclusion into a right one, you'd have a better model than the one you're checking.
- Responsibility failures escalate one level.
- Escalation is rate-limited by the manifest's budget and prioritised by expected value of review.

Mint an **idempotency key** per action and put it on the receipt. If the gate times out and the caller retries, the action must not double-execute. Straight from the saga literature; a one-line addition that reads as production thinking.

**Tools.** Plain Python. Concepts: the saga pattern and compensating transactions (Garcia-Molina & Salem); ASTM F3269-21 / Simplex — certify the monitor and the switch, not the agent; Learning to Defer (Madras et al.; Mozannar & Sontag) on why confidence-based deferral is suboptimal when it ignores the downstream human.

**Inputs.** S7's predicate results, S8's grounding score, S6's evidence, S12's manifest.

**Output.** A `Decision` with an ordered list of `Reason` objects, each naming the rule, the evidence and the threshold. **The reasons *are* the receipt's body.**

**Connects to.** S3 acts on the intervention. S10 renders the reasons. S15's invariants are assertions over exactly this function — which is why it must be a **pure function** of its inputs.

**Verify.** Write `docs/compensability.md` first, then a test per row. Then the demonstration that earns the slide: **construct a high-risk fully-compensable case and a low-risk non-compensable case, and show the intervention differs.** That single test is the proof D49 is real and not a paragraph.

**Problems.** Rule interactions producing surprises at boundaries. Keep `decide()` pure — no I/O, no clock, no logging inside it — so it's exhaustively testable and S15 can hammer it with thousands of generated cases.

**Alternatives.** None. Do not collapse this into a scalar risk score. An enterprise cannot defend "risk = 0.82" to a regulator; it can defend "this contradicted Policy v4.2 §3.1."

---

## S10 — The Decision Receipt · 4h · Day 4 · Track A · 🎯 MILESTONE

**What.** A signed JSON artifact per governed decision, plus an HTML rendering, appended to `decisions.jsonl`. Current measurement: median 2,282 bytes, p95 3,763 bytes over 120 receipts.

**Why.** The brief's "clear audit trail behind every decision" under Governance, and what makes the product defensible to a regulator rather than merely useful to an engineer. **Evidence, not scores.** It's also the most demoable artifact — the thing that goes on screen and makes a judge understand the whole pitch in four seconds.

**How.** Shape it with W3C PROV vocabulary — Entity/Activity/Agent, `wasDerivedFrom`, `wasAttributedTo` — so you inherit a decade of prior art instead of inventing a schema. PoE measured its object at ≈1.1 KB; our richer receipt is measured separately at median 2,282 bytes and p95 3,763 bytes (n=120), without claiming a match.

```json
{ "receipt_id","trace_id","idempotency_key","ts","manifest_id",
  "action": {"tool","args","risk_tier","compensability"},
  "claims": [{"kind","tier","asserted","load_bearing"}],
  "evidence":[{"claim_id","value","source","query","fetched_at",
               "freshness_ms","reliability_class","confidence"}],
  "predicate_trace": {...},
  "verdict","intervention",
  "reasons":[{"rule","expected","observed","policy_version"}],
  "root_cause":"stale_clause_v3.8",
  "latency_ms":{"extract","classify","resolve","predicate","ground","decide"},
  "compensation":{"action","class"},
  "sig":"hmac-sha256:..." }
```

**Two tiers (D11).** The operational trail is discoverable and holds everything above. The privileged testing trail — bias probes, counterfactual twins, red-team results — writes to a separate store. Driven by the *Mobley v. Workday* privilege ruling; a real legal design decision, not a flourish. Implement as two files and one paragraph in `docs/decision-receipt.md`.

Sign with HMAC-SHA256 over canonical JSON. Not a PKI — say plainly in the README that production would use asymmetric signing with a KMS-held key and the demo shows the mechanism.

**Tools.** `json`, `hmac`, `hashlib` (stdlib) · `jinja2` for HTML. Concepts: W3C PROV; canonical JSON (sorted keys, no whitespace) so signatures are stable; EU AI Act Art. 12 automatic logging and Art. 18's ten-year retention.

**Inputs.** S9's `Decision`.

**Output.** `decisions.jsonl`, one HTML receipt per decision, a measured average size. **🎯 MILESTONE: `make demo` blocks ORD-88461 and prints a correct receipt.**

**Connects to.** S11 reads the log. S17 renders receipts. S18 aggregates them.

**Verify.** (1) Signature verifies and a one-byte tamper breaks it — five minutes to write, great line in the video. (2) Average size reported honestly; if yours is 1.8 KB, say 1.8 KB. (3) Every `reason` names a rule that exists in the JDM graph — no orphan reasons.

**Problems.** Receipt bloat from dumping full clause text. Store a hash plus the first 200 characters and a pointer. The size number matters because "about a kilobyte per governed action" is a much better answer to "doesn't logging everything get expensive?" than a hand-wave.

**Alternatives.** Skip signing if time is tight; the schema and evidence trail are the substance. **Do not skip the query string** — `"SELECT delivered_at FROM orders WHERE id='ORD-88461'" → 2026-07-19 [live · 4ms]` is the line that makes the demo real.

---

## S11 — The four loggers · 4h · Day 5 · Track C

**What.** Claim coverage by tier · extraction accuracy under injected noise · per-stage p50/p95/p99 · rule-promotion cost.

**Why.** These four numbers are the prototype's actual value. **No other team will have them**, because they only exist once code is running. They close O1, O3 and O5 — three P0 open items four rounds of research couldn't touch — and they turn "we built a demo" into "we measured something."

**How.** 🔴 **Write them AS S4–S10 are written, not after.** Retrofitting is how measurement gets skipped. Everything writes one JSON line per decision to `decisions.jsonl`; S18's reports compute from that file.

- **Coverage.** Per run: `claims_total, c1_n, c2_n, c3_n, unverifiable_n` and the ratio. Report per tier so C1/C2-exact vs C3-probabilistic is visible.
- **Extraction under noise.** Perturb *inputs* at 0/5/10/20/35/50%: character typos, sentence truncation, an injected contradictory clause fragment appended to the retrieved chunk. ≥30 runs per level. Plot per-field accuracy against noise. This is the local **analogue** of C-Trace's Table 8 — call it an analogue, not a replication: C-Trace measures attack success under adversarial conditions; you measure verdict accuracy under random corruption.
- **Latency.** Timer around each of six stages plus end-to-end. ≥50 runs mixing BLOCK and ALLOW (ALLOW short-circuits some stages). Report which stage dominates the tail — almost certainly HHEM — as a finding.
- **Promotion.** For every C3-path decision, record whether a deterministic rule could have settled it. The clause-version case is the worked example: comparing `retrieved.version` to `current.version` is a pure metadata check and is *both cheaper and more reliable* than semantic grounding. Track `cost_if_c3` vs `cost_if_promoted` and plot cumulative cost-per-decision as decision types are promoted most-frequent-first.

**Tools.** `time.perf_counter` · `statistics.quantiles`/`numpy.percentile` · `matplotlib`. Concepts: p50/p95/p99 and why the mean is useless for latency; noise-sweep methodology; the ~2,000× machine-vs-human cost ratio and ~1.7M× per decision moved.

**Inputs.** S3's timing hooks. S5's tiers. S4's per-field flags. S10's log.

**Output.** Four artifacts in `reports/`: coverage table, noise-sweep curve, latency table, promotion curve.

**Connects to.** S18 renders them. The deck's metrics slide and the video's measurement beat both come from here.

**Verify.** Run the pipeline 50 times and confirm every decision produced exactly one log line with all four logger fields populated. A missing field is a silently broken metric.

**Problems.** Latency dominated by cold-start on the first call — discard the first N runs and say you did. LLM-call latency swamping everything — report the gate's latency **excluding** the agent's own model call, and say so, because the gate is what you're measuring.

**Alternatives.** If the promotion curve proves fiddly, ship a two-point comparison: cost per decision with C3 in the path vs with the version check promoted. Same argument, a tenth of the work.

---

## S12 — Policy manifests · 4h · Day 5 · Track A · ⛔ NEVER CUT

**What.** Extract every threshold, budget, posture and policy choice out of the code and into a per-use-case manifest file.

**Why.** **The brief asks for this by name**, under Governance: *"a configurable policy layer so behavior can vary by use case, geography, or risk appetite, with a clear audit trail behind every decision."* It's the largest gap in the project and the second of the two things that must ship. It also makes the reference parameters — "multiple AI use cases at once, each with different latency and risk tolerance" — a demonstration rather than a claim.

**How.**

```yaml
# manifests/servicing.yaml
id: servicing_v1
use_case: customer_support_assistant
risk_tier_default: 2
latency_budget_ms: {p95: 400}
escalation_budget_pct: 2.0
fail_posture: {tier_0: open, tier_1: degrade, tier_2: closed}
verdicts: {source_unreliable: escalate, unverifiable: escalate}
min_reliability_for_block: corroborated
predicate_graph: graphs/servicing.json
evidence_retention_days: 3650        # EU AI Act Art. 18
geography: IN
authority_ceiling_paise: 2500000

# manifests/knowledge_assistant.yaml
id: knowledge_v1
use_case: internal_knowledge_assistant
risk_tier_default: 0
latency_budget_ms: {p95: 200}
escalation_budget_pct: 5.0
fail_posture: {tier_0: open, tier_1: open, tier_2: closed}
verdicts: {source_unreliable: allow_with_caveat, unverifiable: allow_with_caveat}
min_reliability_for_block: inferred
predicate_graph: graphs/knowledge.json
evidence_retention_days: 90
geography: EU
```

Load with `manifest.py`, validate against a Pydantic model, and **fail loudly on an unknown key** — a typo that silently disables a check is the worst possible bug in this system. Put the manifest id and hash on every receipt.

**The demonstration that earns the slide:** take one input class, run it under both manifests, show the behaviour differ. Same engine, same code path, same receipt format, different manifest.

**Tools.** `pyyaml` · `pydantic`. Concepts: policy-as-data vs policy-as-code; the DMN principle that policy and engine change at different rates; the NCCI precedent — CMS has run automated prepayment edits on every Medicare Part B claim since 1996, updated **quarterly**, which is your published maintenance cadence.

**Inputs.** S7–S9 working with hardcoded values. Grep for every magic number and move it.

**Output.** Two manifests, a loader, a validation test, and a diff showing the same input producing different interventions.

**Connects to.** S13 uses the second manifest. Every prior step reads from it.

**Verify.** Grep `controlplane/` for numeric literals. Every one that's a policy choice rather than a unit conversion must be gone. Then the differential test: identical input, two manifests, assert the interventions differ and both receipts name their manifest id.

**Problems.** Manifest sprawl — the temptation to make everything configurable. Keep it to the fields above. A manifest with forty knobs is a framework, and building a framework instead of two manifests is the R4 spec's named **single biggest schedule risk**.

**Alternatives.** JSON instead of YAML if you prefer — and if you author the predicate graph as JDM, the manifest can literally reference it, giving you an inspectable "the rule that fired" artifact for free.

---

## S13 — Use case 2: the internal knowledge assistant · 5h · Day 6 · Track A · ⛔ NEVER CUT

**What.** A second agent with a different tool, a different predicate class, and a different manifest — running through the identical gate.

**Why.** Three of the brief's requirements at once: multiple use cases with different risk/latency profiles, the configurable policy layer, and privacy as a named risk category. And it's the cheapest way to stop looking like a single-scenario demo.

**How.** Tool: `send_document(recipient_id, doc_id, excerpt)`. An employee asks the assistant for information; it retrieves a document and proposes sending an excerpt.

**The predicate class shifts from correctness to entitlement.** Claims become: does `recipient_id` hold entitlement to `doc_id`'s classification? Is the excerpt's content derived from a record the recipient is entitled to? Does the outbound text carry PII belonging to a third party?

**The demo moment.** The assistant retrieves a support ticket to answer a policy question, and the excerpt contains another customer's name, order and address. **A PII scanner passes it** — the data is legitimate PII, correctly formatted, not a leak of anything *secret*. The entitlement check blocks it, because it's not *this* recipient's record. That distinction — detection vs authorisation — is the sharpest thing in the privacy pillar and it demos in fifteen seconds.

Manifest contrast to show explicitly: Tier 0/1 default, fail-open, 200ms budget, 5% escalation, 90-day retention, UNVERIFIABLE as allow-with-caveat rather than escalate. **Same code path. Different behaviour. Different receipt contents. Same receipt format.**

**Tools.** The existing gate. A small `entitlements.db`: `(subject_id, resource_class, granted_at, expires_at)`. Concepts: entitlement checking vs pattern-based PII detection; C-Trace's four GDPR predicates (consent, purpose limitation, data minimisation, erasure) as the closest published implementation.

**Inputs.** S12's manifest loader. S1's entitlements table. **Output.** A second working demo path and a side-by-side receipt comparison for the deck.

**Connects to.** S14 supplies the PII recogniser. The deck's Governance slide is this, screenshotted.

**Verify.** The cross-tenant test: an excerpt containing customer B's data, sent to an employee entitled to customer A only. **Assert the PII recogniser passes it AND the entitlement check blocks it.** Both halves matter — the PII pass is what proves the point.

**Problems.** Scope creep into a full RBAC model. You need one table and one lookup. Two hours, not a day.

**Alternatives.** If a second agent is too much, keep one agent with a second tool under a second manifest. You lose a little "different use case" framing and keep all of the governance demonstration.

---

## S14 — The responsibility layer: privacy and bias · 5h · Days 6–7 · Tracks A + C

**What.** PII recognition on outbound content, the entitlement check that catches what PII detection misses, and an offline counterfactual twin probe for bias.

**Why.** The brief names bias, hallucination and privacy as the three risks. The project's whole wedge is that none of those three is the load-bearing failure — but **judges score against their own headings.** The move is not to abandon the wedge; it's to make bias/hallucination/privacy the visible **breadth** layer and business correctness the **depth** layer. This step is the breadth layer, and it can be honest rather than decorative.

**How.**

- **PII** — `presidio-analyzer` (MIT) or a small regex/entity set for names, emails, phones, order IDs, addresses. Runs on the outbound excerpt only, Tier 1. Report precision honestly: recogniser-based detection is moderate at best.
- **Entitlement** — the strong layer, from S13. Frame the two together in one sentence: *detection asks whether this looks like personal data; authorisation asks whether this person may see this record. The second catches the cross-tenant leak the first waves through.*
- **Bias** — `bias_probe.py`, offline, off the critical path. Take N servicing cases, hold every fact constant, vary only a protected-attribute proxy in the customer profile, run through `decide()`, compare verdict distributions. Score it the way a production canary judge does: **Mann-Whitney U per signal, explicit NODATA handling, transparent N-of-M rollup** — the Kayenta pattern, copied deliberately rather than reinvented.

**Then attach the power analysis, which is the actually novel part.** Your own constructed tables show the four-fifths rule **falsely fails 56.0%** of the time at n=30 with a 30% base rate and zero true bias, and **misses a real 10-point gap 84.4%** of the time at n=1,000 with a 50% base rate — because it's a ratio test being used as a difference test. Most bias monitoring in the market is statistically underpowered and nobody says so. That's a slide of its own.

Write the impossibility framing into `docs/limitations.md`: bias is a population property. Asking "is this response biased?" is a category error in the same way as asking "is this coin flip unfair?" Anyone claiming real-time single-response bias detection is doing toxicity scanning.

**Tools.** `presidio-analyzer` · `scipy.stats.mannwhitneyu` · `numpy`. Concepts: the fairness impossibility theorems (Kleinberg et al.; Chouldechova) — calibration and error-rate balance are incompatible whenever base rates differ; statistical power; the four-fifths rule's misuse.

**Inputs.** S9's **pure** `decide()` — the probe calls it thousands of times, only possible because it's pure.

**Output.** A PII+entitlement check in the Tier 1 path, and `reports/bias_probe.md` with the test result and the power tables.

**Connects to.** The deck's responsibility slide. The video's honest-limits beat. The **privileged** half of D11's two-tier evidence architecture — probe results go to the separate store.

**Verify.** The probe on a decision function with no protected-attribute input must return "no detectable difference" — **and you must be able to say what effect size you were powered to detect.** A null result you can quantify is a real result; a null result you cannot is nothing.

**Problems.** Presidio's model downloads. Keep the regex fallback behind `CP_PII=regex`. Resist making the bias probe run inline — it's a population property and putting it on the critical path would contradict your own argument.

**Alternatives.** Ship the probe as a script and the power tables as analysis without wiring it into the pipeline. That's the honest architecture anyway.

---

## S15 — Metamorphic invariants and mutation testing · 5h · Day 7 · Track A

**What.** Five label-free invariants over the decision function, plus a mutation corpus that gives the detector a defensible recall number.

**Why.** ControlPlane has no ground truth for most production traffic. Metamorphic relations solve the *oracle problem* — they let the system test itself on unlabelled live traffic, continuously. **Nobody in the guardrail market does this.** And mutation testing answers "how do you know your checker actually works?" with a number instead of an assurance.

**How.** The five invariants (write them formally in `docs/invariants.md` first):

- **M1 Strictness monotonicity.** Make any evidence strictly less favourable (later delivery date, higher amount, lower authority) → the intervention must not become more permissive.
- **M2 Amount monotonicity.** Lower the refund amount with all else equal → the decision must not become stricter.
- **M3 Policy equivalence.** Two claims the policy treats identically must receive identical verdicts.
- **M4 Idempotence.** The same action re-submitted unchanged gets the same verdict and the same receipt modulo timestamp and id.
- **M5 Source-degradation monotonicity.** Replace an evidence source with a staler or lower-reliability one → the verdict must never become more permissive. It may become SOURCE-UNRELIABLE or ESCALATE, never ALLOW where it was BLOCK.

Implement with `hypothesis`: generate evidence sets, apply the transformation, assert the relation. Order the intervention enum so "more permissive" is a comparison, not a lookup.

**Mutation testing** — mutate the **inputs**, not the code. Operators: `order_id` → nonexistent; amount → above ceiling; `delivered_at` → outside window; clause version → superseded; `customer_id` → mismatched; `order_status` → inconsistent with `delivered_at`. Generate ~200, run them, report **mutation score = fraction caught.**

State the caveat the literature itself states (Just & Ernst, FSE'14): mutants correlate with but don't perfectly represent real faults. **Report the score as a rigorous lower bound and a regression signal, not as a real-world catch rate.** Saying that is worth more than the number.

**Tools.** `hypothesis` · `pytest`. Concepts: metamorphic relations and the oracle problem (Chen et al.; ACM CSUR 51(1)); mutation score; the crucial limit — both techniques validate that the implementation faithfully executes the policy you specified, **not that the policy is right.** Say that wherever you present them.

**Inputs.** S9's pure `decide()`. **Output.** A passing invariant suite in CI, and `reports/mutation.md` with the score and a per-operator breakdown.

**Connects to.** The metrics slide. The README's "how do you know it works" section.

**Verify.** Deliberately break a rule — flip R1's comparison operator — and confirm at least one invariant fails and the mutation score drops. **An invariant suite that never fails is not testing anything**, and this five-minute exercise is the only way to know yours is live.

**Problems.** Hypothesis finding real bugs at boundaries you hadn't thought about. That's the tool working. Budget time to fix what it finds, and put the interesting ones in the README — "the invariant suite found this and we fixed it" is a strong sentence.

**Alternatives.** If time is short, ship three invariants and a 50-mutant corpus. The idea is the differentiator; the sample size is not.

---

## S16 — SEB-1 experiments 3 and 5 · 4h · Days 5–6 · Track C

**What.** Exp 3: `order_id` cross-validation against customer identity and described attributes. Exp 5: a per-verdict confusion matrix.

**Why.** D52 — the project's own measurement says `order_id` cross-validation is the highest-value unbuilt check, because tool-call interception concentrates the entire verification burden onto that one field. And the brief asks for **false positive and false negative rates explicitly** under Metrics & monitoring; a single accuracy number doesn't answer it, because a false ALLOW and a false BLOCK have completely different costs.

**How.**

*Exp 3.* Extend SEB-1's generator to emit distractors: same customer with two similar orders, or described attributes ("blue", "shoes") matching a different order than the one resolved. Measure verdict accuracy with and without the cross-validation check. Report how many HARD cases actually had distractors — the existing generator only creates them when a same-item order exists, so distractor density is currently uncontrolled and that's worth reporting.

*Exp 5.* A 4×4 matrix, gold verdict vs predicted, across ALLOW / BLOCK / ESCALATE / SOURCE-UNRELIABLE. Then per-class precision and recall, and a **cost-weighted error rate** using the cost model: a false ALLOW costs the refund; a false BLOCK costs a human review at ₹-per-review. **The cost-weighted number is the one for the slide** — it's the one a business person can act on.

Keep the framing ready: *the synthetic setup is what makes the comparison valid — both architectures see the identical corrupted extraction, so the gap is attributable to architecture alone.*

**Tools.** The existing SEB-1 code. `sklearn.metrics.confusion_matrix` or a hand-rolled 4×4.

**Inputs.** The two existing SEB-1 scripts, dropped into `bench/` unchanged. Same seed, 20260814.

**Output.** `reports/confusion.md` and an updated SEB-1 write-up with the exp-3 delta.

**Connects to.** The deck's metrics slide. S7's R3 rule is exp 3 made production code.

**Verify.** Same seed, same numbers, every time. **Print the seed in the console output.** If a judge runs your published code and gets different output than your published numbers, that's an unforced error — and it has already happened once in this project's history.

**Problems.** Distractor generation too easy or too hard, producing a ceiling or floor effect. Tune to ~50% distractor density in the HARD tier and report the density.

**Alternatives.** Exp 5 alone if time is short — one hour, and the brief asks for it by name.

---

## S17 — The reviewer console · 6h · Day 8 · Track A · ✂️ FIRST TO CUT

**What.** A two-route web app implementing the cognitive forcing function: the reviewer sees the case and **commits to a decision before the system's verdict is revealed.**

**Why.** Escalation failure is the largest single enterprise AI failure category, and the human layer is the most likely thing in any such product to be decorative theatre. Radiologists drop 82% → 45.5% when the AI is wrong. Clinicians override 90% of drug-interaction alerts. **Knight Capital lost $440M in 45 minutes and the warnings fired — nobody acted.** A detection success and an escalation failure. This is also one of very few places the prototype can generate a genuinely novel number: the human override rate, which four research passes confirmed does not exist anywhere in published form.

**How.**

```
GET  /review/{id}   → the case ONLY: customer message, proposed action,
                      retrieved clause, order record.
                      No verdict. No highlight. No derivation.
                      + a form with hx-post

POST /review/{id}   → record judgement + time-to-decision, then return
                      the SECOND fragment via hx-swap: the full receipt,
                      and whether the human agreed with the system.
```

FastAPI + HTMX, **not Streamlit**. Streamlit's rerun-on-every-interaction model has no natural "submit then reveal a different view" primitive and can leak the verdict into the session. HTMX's `hx-swap` maps onto commit-then-reveal directly, and HTMX is one script tag — no npm, no bundler, no build step.

Log `{reviewer_id, decision_id, human_verdict, system_verdict, agreed, seconds_to_decision}`. Run on 15–20 cases with your own team; report agreement rate and median time-to-decision.

**Tools.** `fastapi` · `uvicorn` · `jinja2` · HTMX via CDN. Concepts: cognitive forcing functions (Buçinca et al. 2021); automation bias; Learning to Defer — Madras et al.'s finding that confidence-based deferral is suboptimal because it ignores the downstream human, so sometimes you should escalate a *high*-confidence case.

**Inputs.** S10's receipts. An ESCALATE queue from S9. **Output.** A running console, a `reviews` table, `reports/reviewer.md`.

**Verify.** 🔴 **Open dev tools on the `GET` route and confirm the verdict is NOT in the HTML source.** If it's present but hidden with CSS, the forcing function is fake and the experiment is void. This is the only test that matters here.

**Problems.** Time. Six hours for a "persuade" artifact rather than a "prove" one — correctly first on the cut list. If day 8 arrives and the second manifest or the reports aren't done, cut this and put a description plus a static mock in the proposal.

**Alternatives.** A terminal version: print the case, `input()` the reviewer's call, then print the receipt. Thirty minutes, same experiment, less pretty, still produces the number.

---

## S18 — Report generation · 3h · Day 7 · Track C

**What.** One command that reads `decisions.jsonl` and regenerates every number and chart in the submission.

**Why.** The alternative is copying numbers by hand into a deck, and that's exactly how a stale figure survives into a submission. This project has already caught four fabricated figures; do not add a fifth through a transcription error.

**How.** `make report` → `bench/report.py` reads the log and writes `reports/`: `coverage.md`, `latency.md`, `confusion.md`, `noise_sweep.png`, `promotion_curve.png`, plus **`summary.json` holding every headline number as a key.**

Then have the deck and README pull from `summary.json` — or at minimum, run a checker that greps the deck's text for numbers and warns on any not in `summary.json`. Cheap, and it makes drift impossible.

Every chart gets the discipline the SEB-1 chart already has: labelled axes, direct series labels, tabular numerals, a **"synthetic benchmark"** qualifier in the subtitle rather than buried in a source note, and the seed and run count stated.

**Tools.** `matplotlib` · `pandas` (optional) · `jinja2`.

**Inputs.** S11's log. **Output.** `reports/`, regenerable from scratch.

**Connects to.** Deck, README, video, proposal — all four read from the same place.

**Verify.** Delete `reports/`, run `make demo && make report`, confirm every number in the deck still appears in the regenerated `summary.json`.

**Problems.** Charts that look like default matplotlib. Spend twenty minutes on a shared style: one accent colour, no chartjunk, direct labels instead of a legend where there are ≤3 series.

**Alternatives.** Hand-written reports with a strict rule that every number is copied from a run in the same sitting. Worse, but workable.

---

# §6 — TESTING STRATEGY

| Layer | Answers | How | When |
|---|---|---|---|
| **Unit** | Does each component do what its contract says? | `pytest` per module. Resolvers against fixture DBs, predicates table-driven, `decide()` exhaustively over its enum space. | As each step lands |
| **Golden file** | Does the pipeline produce the same receipt for the same input? | Five fixed scenarios with committed expected receipts, compared modulo timestamp/id/signature. | Day 4 onward |
| **Metamorphic** | Is the decision function *coherent*, with no labels? | S15's five invariants under `hypothesis`. | Day 7 |
| **Mutation** | What fraction of injected violations does the detector catch? | S15's ~200-mutant corpus → mutation score, reported as a lower bound. | Day 7 |
| **Adversarial / chaos** | Does it fail to a *safe* state? | Kill the DB mid-decision, return stale evidence, time out the grounding model, corrupt a receipt. Assert the manifest's fail posture is honoured every time. | Day 8 |

**The one test worth naming in the README:** chaos-test the verifier itself. Take the demo scenario, kill the policy store mid-decision, assert the system escalates or blocks rather than allowing. That's Simplex's design rule — **the fallback must always be available and safe** — applied to your own control plane, and it's the test that separates a demo from a system.

---

# §7 — THE PAPERS AS REFERENCE: ADAPT, DON'T COPY

| Paper | Take this | Do NOT copy this |
|---|---|---|
| **C-Trace** (2606.19242) | The interceptor wrapping the tool-calling loop (S3). Extraction accuracy as a first-class *reported* metric (S11). The noise-sweep design at p∈{0,10,25,50}%. "Compliance is a property of an event stream, not a single message." | Its predicate class — GDPR lawfulness. And don't call your sweep a *replication*: C-Trace measures attack success under adversarial conditions; yours measures verdict accuracy under random corruption. It's an **analogue**, and calling it one is the honest and stronger move. |
| **Proof of Execution** (2607.05397) | The receipt as a single runtime-checkable object binding authorisation, effect, history, replay (S10). The ≈1.1 KB anchor. And verbatim: **separate who plans, who authorises, who mutates, who records** — which forecloses "why not just prompt the agent to check itself?" | Its scope. PoE proves an action was *authorised*. Your receipt additionally claims it was *correct* — the clause, the derivation, the source version. Don't blur them; the difference is your contribution. |
| **Reddy et al.** (2607.07405) | Direct validation that deterministic read-only pre-execution gates recover the dominant silent-failure mode: **+12.4pp on gpt-4o-mini, +10.4pp on gpt-5.2** — the failure persists at the frontier. Cite it generously and unprompted; it's evidence your mechanism works. | Their evaluation setup. They run against a *simulated* τ²-bench airline DB. You query a store live and model it as fallible. Say what's different rather than implying nobody did this. |
| **Wix** (2608.01050) | Production proof that live business-state gating works at scale — 756,641 messages, 59.4% of skill-message pairs removed, 7.8% of replayed conversations selecting a production-blocked skill without the gate. | Its position in the loop. **Wix gates the *menu* before the model chooses. You gate the *order* after it's placed** — the only point at which the agent's own claim exists to be falsified. Worth a sentence in the README. |
| **MiniCheck / HHEM** | A 770M-parameter checker reaching GPT-4 grounding accuracy at ~400× lower cost (S8). A small specialist beats a large generalist for entailment. | Treating 77.4% LLM-AggreFact SOTA as certainty. Label C3 as *moderate* confidence everywhere; let low confidence escalate rather than block. |
| **CostBench** (ACL 2026) | The two-number proof that success and efficiency are different properties: GPT-4o completes 90.29% of tasks and finds the cost-optimal plan 13.65% of the time. Every dashboard shows that agent as green. Your cost pillar's whole evidence base. | Its offline pre-deployment framing. Yours measures effort ratio at runtime against a learned per-task-class baseline. |
| **Adjacent fields** | **Sagas** → compensating-action registry + idempotency keys (S9). **ASTM F3269-21 / Simplex** → certify the monitor and the switch, not the agent; the fallback must always be available. **SEC 15c3-5** → regulatory precedent for non-bypassable pre-execution control, and "chase and cancel does not satisfy the requirement." **Metamorphic & mutation testing** → S15. **Kayenta** → the statistical judge for twin probes (S14). | Don't claim Simplex's formal reachability guarantees — your envelope is discrete and policy-defined, not a differential-equation-derived region of state space. Don't claim SEC 15c3-5 mandates a latency figure; the SEC's own FAQ has none. Don't frame anything as a "decentralised oracle network" — wrong trust model, and it invites a category error with anyone who knows DeFi. |

---

# §8 — THE THREE DELIVERABLES

## The repo and README

The brief names four sections: **implementation approach, solution architecture, dependencies, execution instructions.** Write those four first, in that order, then add a fifth the brief doesn't ask for.

| Section | Contents |
|---|---|
| Implementation approach | The one-paragraph product statement, the four-layer gap, the design decisions with their numbers (D2, D3, D8, D49). Cite Reddy et al. and Wix here. |
| Solution architecture | The §3 pipeline diagram, the five type contracts, the repo tree annotated. |
| Dependencies | Every package with its licence. All MIT or Apache-2.0. Name the two deliberate exclusions — Bespoke-MiniCheck (CC BY-NC) and SDV (BUSL-1.1) — and say they were excluded for licence reasons **before** you knew a public repo was required. That paragraph reads as engineering maturity. |
| Execution | `git clone` → `make setup` → `make demo`. Three commands, no API key needed thanks to committed fixtures. Then optional paths: `make demo MODE=live`, `make bench`, `make report`, `make console`. |
| **Honest limitations** | Synthetic benchmark, single seed, closed extractor vocabulary. SQLite is not a distributed system of record and why that doesn't matter for what's being demonstrated. C3 is probabilistic at 77.4% SOTA. Bias is offline because it's a population property. The verifier is itself an attack surface (D30). Monitorability: safety and co-safety properties are decidable from a finite prefix, liveness properties are not — here's what we can never guarantee. **And a "figures we retired" table.** Four fabrications caught in your own work is not an embarrassment; it's the reason the remaining numbers can be trusted. |

## The business proposal — assemble, don't write

| Brief's section | Where it already exists |
|---|---|
| Problem framing | Round 1 Slide 1 + the correlated-failure argument, **using the verbatim Runbook §02 reformulation** (`docs/round2-runbook-block0.md`) rather than the current Deming sentence. |
| Solution design | §3's pipeline + the evidence ladder + the tier model + the four verdicts. |
| Target users | The market/buyers brief, and the honest answer from the cheat sheet: this is for the enterprise running four models across three clouds, where the policy has to mean the same thing everywhere. **Naming a smaller real market beats claiming a large imaginary one.** |
| Business case & impact | The cost model: $0.016 vs $34.18 per 1,000, ~2,000×; rule promotion at ~1.7M× per decision moved; the automation-ceiling metric; TM Forum's 51% recovery as the prevention-beats-detection anchor. |
| Phased roadmap | Shadow mode → enforcement (D7). NCCI's quarterly edit-library cadence (D53) as the published maintenance model. Adapter library per system of record at 3–6 engineer-weeks each. |
| Key risks + mitigations | The red team's six objections, **stated as your own**, with D45 first: adoption friction, not statistical skepticism, is the primary risk. Then D30 (the verifier is an attack surface), the platform-timing risk, and the monitorability ceiling. |

## The deck

Same Accenture template. Four housekeeping rules from the template's own instructions slide: **remove the instructions slide, name the file `Team name_Idea Name.pptx`, spell-check, use Arial.** Fill the team slide — it's still placeholder names and stock photos, and "All fields are mandatory" is printed on it.

Carry Slides 1 and 2 forward. The old "75% in 1–20 ms" figure is retired; **use P09's measured number** (`reports/latency.md`): gate end-to-end median **7.67 ms** (HHEM off, sequential, n=1,050) — at AEGIS's 8.3 ms and well under OAP's 53 ms, and our figure additionally includes a live system-of-record query neither of theirs performs (which biases ours *upward*). Then add:

- **Architecture** — the §3 pipeline, annotated with what's built
- **The prototype** — a real receipt screenshot and the negative-control transcript side by side
- **Governance** — the two manifests, same input, different behaviour. The brief's named ask; give it a whole slide.
- **Metrics** — coverage by tier, measured latency, confusion matrix, promotion curve
- **Business case & roadmap** — the 2,000× and the shadow-to-enforcement phases
- **Risks & honest limits** — conceding before you're challenged is what distinguishes a researched entry from a confident one

## The demo video

| Time | Beat | Screen |
|---|---|---|
| 0:00–0:30 | The agent fails. Unprompted. On a real retrieval bug. | Terminal: `make demo GATE=off` → `REFUND ISSUED ₹42,999` |
| 0:30–1:15 | The gate catches it. Walk the pipeline as it runs. | Terminal: `make demo` → stage-by-stage → BLOCK |
| 1:15–1:45 | The receipt. Hold on the query line and the version line. | The rendered HTML receipt, full screen |
| 1:45–2:15 | Same engine, different manifest. The cross-tenant block a PII scanner passes. | Split: two manifests → two receipts |
| 2:15–2:45 | What we measured. Four numbers nobody else has. | `reports/` — coverage, latency, confusion, promotion |
| 2:45–3:00 | Honest limits, then the line. | *"Most AI checkers ask another AI for a second opinion. We ask the company's own systems for the actual answer."* |

Record on day 9 against a frozen build. Check the **exported file's** duration, not the editor's estimate. End on the line and cut — no thank-you slide.

---

# §9 — OPEN DECISIONS: SETTLE THESE BEFORE DAY 2

| # | Decision | Recommendation |
|---|---|---|
| 1 | **Which Featherless model** for the agent, and which for extraction? | Qwen 3 family for the agent (native tool calling), same model for extraction via Instructor `Mode.JSON`. One model, one bill, one thing that can break. Pin the exact string in `.env.example`. |
| 2 | **Is day 7 inside or outside** the refund window? | Inclusive: `days_elapsed <= 7`. Document it in the manifest and test the boundary. Whichever you pick, pick it once. |
| 3 | **Currency and units.** | Integer paise everywhere. Never floats for money. Format only at the render boundary. |
| 4 | **Does ESCALATE block or hold?** | It holds the action and returns a pending state. The manifest's escalation budget rate-limits it; if the budget is exhausted the tier's fail posture decides. Say this explicitly — "escalate" is weaker risk coverage than "block" and you should concede that rather than blur it. |
| 5 | **Repo name and licence.** | Apache-2.0 (patent grant, consistent with the dependency set). A neutral repo name; don't use the team name. |
| 6 | **Does the demo need an API key to run?** | No. Commit the fixtures so `make demo` works offline; gate the live path behind `MODE=live`. This is the difference between a judge running it and a judge reading about it. |
| 7 | **Who owns which track** for the ten days? | Decide on day 1 and don't swap. **Track A must be one person start to finish** — the gate doesn't parallelise well below the component level. |
| 8 | **Second use case: entitlement or a second correctness case?** | Entitlement. It answers privacy *and* multi-use-case with one build, and the cross-tenant demo is sharper than a second refund variant. |
| 9 | **The Deming sentence.** | Use the verbatim Runbook §02 reformulation everywhere — slide, video, proposal, README. It is captured in-repo at `docs/round2-runbook-block0.md` (P07 Fix 7 is unblocked). Don't put "Deming, 1986" as a bare attribution on a slide; cite Papadakis 1985 only for the 0%/100% criterion. |

## Ship no matter what
- The gate that blocks ORD-88461 with a correct receipt (S3–S10)
- The second manifest and the second use case (S12–S13)
- The four loggers and the reports they produce (S11, S18)
- The negative control on video (S2)
- The README with the honest-limitations section

## Cut in this order
1. The reviewer console (S17) — describe it instead
2. The counterfactual twin probe (S14) — the power tables already carry the argument
3. The mutation corpus (S15) — keep three invariants, drop the 200 mutants
4. SEB-1 experiment 3 (S16) — keep exp 5, the brief asks for FP/FN by name
5. The C3 grounding tier (S8) — report coverage as C1/C2 and say C3 is designed-not-built

---

> You have ten days, three tracks, and a design that has survived seven rounds of adversarial checking. The hard core of this build is about thirty hours; everything else turns a working demo into a measured one. **The two things that must be true on day 10 are that the gate blocks the wrong refund with a real receipt, and that the same engine behaves differently under a second manifest.** Protect those two and everything else is upside.

*Appended to the project record 27 August 2026. Next artifact: S0, the provider probe.*
