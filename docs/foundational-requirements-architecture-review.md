# Foundational-requirements architecture review (P3-D)

> **Historical record (last changed 2026-11-13).** This file records work as of that date and is not maintained. Numbers, file paths and status statements in it are not current claims; current numbers are in `docs/claims.yaml` (checked by `tests/test_claims.py`) and corrections to frozen reports are in `docs/errata.md`.

**Status:** design / architecture review only. No production code, manifest,
predicate graph, benchmark result, or frozen corpus is modified by this task.

**Question this document answers:** P3-C found that every governed
`issue_refund` action carries a load-bearing check — *"the order record this
action is about could actually be resolved"* (`order_record_resolves`) — that
the `ClaimKind` vocabulary cannot represent. Should foundational requirements
of that shape live **inside** the claim / verification model (a new
`ClaimKind`), or in a **separate architectural layer** in front of it?

**Recommendation (short form):** a separate layer — Option B — introduced
**descriptively first**, exactly as P1 verification coverage was. The evidence
for this is in §§5–17; the reasons are in §19. This recommendation does **not**
change any submitted behaviour; Option A would (§14, §20).

---

## Evidence legend

Every non-trivial claim below is tagged:

| tag | meaning |
|---|---|
| `[R]` | **repository evidence** — a fact read directly from a file in this tree (path cited) |
| `[B]` | **benchmark finding** — a result in a P3-A / P3-B / P3-C artifact |
| `[I]` | **architectural inference** — reasoning from the code; not asserted anywhere in the repo |
| `[REC]` | **recommendation** — a judgement this review is making |

---

## 1. Executive summary

1. `order_record_resolves` is **not a claim** in the sense this architecture
   defines a claim. A `Claim` is an agent-attributable assertion carrying an
   `asserted_value`, checked by comparing that value to authoritative evidence
   `[R: controlplane/schema.py:8-22, 264-272]`. `order_record_resolves` has no
   asserted value, is not something the agent asserts, and is not checked by a
   value comparison — it is the **precondition** that resolution produced any
   evidence at all (`Confidence.NONE` ⇒ the record was absent)
   `[R: controlplane/registry/orders.py:60-71]`. It is a *common precondition
   of a set of claims*, not a peer of them `[I]`.

2. The current architecture already contains **three** requirements of this
   shape, and they are **scattered across two artifacts with no runtime home**:
   `currency_integrity` and `independent_user_authentication` in P3-A's
   `bench/extraction_reference.py::UNREPRESENTABLE_REQUIRED`
   `[R: bench/extraction_reference.py:321-358]`, and `order_record_resolves`
   (plus `currency_integrity` again) in P3-B's per-case
   `foundational_requirements[]` `[R: bench/extraction_gold_v1.schema.json:61-77;
   B: reports/extraction-completeness-v1.md §15]`. P3-A's list does **not**
   contain `order_record_resolves` — it was discovered later, by P3-B
   `[R: grep — order_record_resolves appears in bench/, reports/, tests/, and
   docs/extraction-gold-annotation.md only; in zero controlplane/ files, zero
   manifests, zero predicate graphs]`. A concept found incrementally in three
   places, with no single definition, is a missing abstraction `[I]`.

3. **Option A (make it a `ClaimKind`)** injects a precondition into a
   denominator built specifically to exclude "claims that should have existed"
   `[R: controlplane/schema.py:356-369]`, creates a 1-contradiction-plus-N-
   unavailable double-count for a single root failure `[I]`, and — done
   meaningfully — changes the submitted intervention on `gs-129/130/133/134`
   from `ESCALATE` to `BLOCK` `[I, see §14]`. That last point is close to a
   stop condition for this task (§20).

4. **Option B (separate precondition layer)** keeps P1's denominator exactly as
   it is, gives the auditor a first-class "precondition X: VIOLATED" line
   instead of an inference from four `UNAVAILABLE` claims, generalises in one
   shape to all three known cases and to tau2, and can be **descriptive-only**
   at first so that it changes nothing the gate enforces — the same discipline
   P1 followed `[R: docs/verification-coverage.md:114-128]`.

5. The P3-C finding is **structural, not a demonstrated live failure**. In the
   4 missing-record cases the unrepresentable check *is* violated, but P1
   reports ≈28.6% coverage and the gate `ESCALATE`s — the gap does not hide
   behind a high score in this corpus `[B: reports/extraction-completeness-v1.md
   §0, §16]`. This review does not claim otherwise. It does, however, find a
   **secondary observability defect**: the missing-record receipt is labelled
   `verdict: SOURCE_UNRELIABLE`, `root_cause: evidence_below_reliability_floor`
   — both of which describe *"the source returned low-quality data"*, not
   *"the record you asked about does not exist"* `[verified this session by
   deterministic recompute of gs-129; see §6 row 11, §13]`.

6. **Disposition: COMPLETE.** A recommendation is made with evidence. No policy
   ambiguity is resolved. The frozen gold hash is unchanged
   (`79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d`
   `[R: verified this session]`). No production code is touched.

---

## 2. P1 → P3-C context

| phase | what it established | denominator |
|---|---|---|
| **P1** | `verification_coverage = verified load-bearing eligible claims / load-bearing eligible claims`. A **runtime outcome**: a claim counts only if authoritative evidence actually supported it on this decision. `RESOLVED ≠ VERIFIED`. Descriptive only — does not feed verdict or intervention. `[R: docs/verification-coverage.md:67-128; controlplane/decide.py:182-233]` | the claims the manifest's `claim_bindings` actually modelled — **explicitly not** "every claim that should have existed" `[R: controlplane/schema.py:356-369]` |
| **P3-A** | `manifest claim-coverage (kind level) = bound required load-bearing kinds / independently required load-bearing kinds`, from an independent per-tool reference (`bench/extraction_reference.py`) that imports nothing from `controlplane/`. Surfaces *unbound* required kinds and an advisory `UNREPRESENTABLE_REQUIRED` list. `[R: docs/extraction-reliability.md:40-110]` | the reference's required-kind set per tool |
| **P3-B** | an independently authored per-action gold corpus: 30 `issue_refund` actions × 7 `ClaimKind`s = 210 gold claims, plus per-case `foundational_requirements[]` for load-bearing checks with **no `ClaimKind`**. Frozen, sha-pinned. `[R: docs/extraction-gold-annotation.md; bench/extraction_gold_v1.meta.json]` | n/a — a corpus, not a metric |
| **P3-C** | ran the **actual** `controlplane.extract.build_claims` + `classify_claims` over the 30 frozen actions and compared to gold. `[R: bench/extraction_completeness_bench.py; B: reports/extraction-completeness-v1.md]` | 210 representable gold claims |

The through-line: **P1 measures how much of the modelled claim set was
verified; it cannot see a load-bearing check that was never modelled.** P3-A
gave that gap a kind-level number. P3-C gave it an instance-level number and
found the recurring instance is not a *missed* claim but an *unrepresentable*
one.

---

## 3. The exact P3-C finding

From `reports/extraction-completeness-v1.md` and
`reports/extraction-completeness-v1.json` `[B]`:

**Claim-set recovery (the representable layer):**

| metric | value |
|---|---|
| claim recall | 100.0% (210/210) |
| claim precision | 100.0% (210/210) |
| decomposition accuracy | 100.0% (210/210) |
| wrong-kind / wrong-subject / merged / split / spurious | 0 / 0 / 0 / 0 / 0 |

The manifest-driven extractor recovers **every representable required claim**,
with the right kind and subject, atomically decomposed.

**The gap:**

- **`unmodelled_required` rate over cases: 100.0% (30/30).** Every case carries
  `order_record_resolves` as a load-bearing `foundational_requirement` with
  `representable_as_claimkind: false`. No `ClaimKind` can carry it, so it is
  never in the extracted claim universe — and, by construction, never in the
  P1 denominator.
- **Silent-pass: 4 structural gaps, 0 realized.** In `gs-129`, `gs-130`,
  `gs-133`, `gs-134` (`record_lookup_status = NO_MATCH`) the requirement is
  actually `VIOLATED`, but P1 reports ≈28.6% coverage (2/7 verified) and the
  intervention is `ESCALATE`. "High score AND permissive intervention" (the
  silent-pass condition) is met by **none** of them.
- **Assertion-value layer not exercised** — 0/30 offline fixtures; the LLM
  `extract_action` path is not measured. The 100% figure is *structural claim-
  set recovery*, not end-to-end extraction accuracy.

**The finding is therefore not** *"the extractor missed `order_record_resolves`"*.
**It is** *"`order_record_resolves` is required and load-bearing but sits
structurally outside the `ClaimKind` representation, so no completeness or
coverage metric that is defined over `ClaimKind`s can ever show it"*.

---

## 4. Definition of a foundational requirement

**Working definition `[REC]`:** a *foundational requirement* is a condition
that must hold for an action's **claim-level verification to be meaningful or
possible at all** — and that is **not itself an agent-attributable, value-
checkable assertion**.

Contrast with a claim, using the architecture's own definitions:

| property | **factual / policy claim** (A, B in task §8) | **foundational requirement** (D, F, G in task §8) |
|---|---|---|
| origin | the extractor, from agent prose / structural args `[R: controlplane/schema.py:1-23]` | the verification process itself (did resolution succeed? is the actor established?) `[I]` |
| carries an `asserted_value`? | yes (may be `None`) `[R: schema.py:264-272]` | no — there is nothing the agent asserted |
| checked how? | compare `asserted_value` (or a structural fact) to authoritative `Evidence` via a predicate `[R: controlplane/decide.py:86-114]` | inspect whether verification is *possible*: `Evidence.confidence == NONE` ⇒ record absent `[R: orders.py:60-71]` |
| relationship to other claims | independent — its own evidence, its own verdict contribution `[R: decide.py:298-390, per-claim precedence]` | **presuppositional** — one failure makes a *set* of claims unevaluable at once `[B: gs-129 — 4 order-scoped claims all resolve to `UNAVAILABLE`]` |
| cardinality | 1 claim : 1 check | 1 requirement : N claims |
| already handled operationally? | — | yes: missing-row evidence (`Confidence.NONE`, `reliability = UNVERIFIED`) → verdict `SOURCE_UNRELIABLE` → `ESCALATE` `[R: decide.py:311-329, 400-409, 426-427; servicing.yaml:33-36]` |

### The ten abstractions in task §8 are **not** one abstraction `[REC]`

| task §8 item | what it actually is | same as a claim? |
|---|---|---|
| A. factual claim | agent hypothesis about a record value | — (this is the reference) |
| B. policy claim | agent hypothesis that a rule is satisfied; decomposes to A + a rule application | yes — a claim (`WITHIN_REFUND_WINDOW` etc.) |
| C. verification-eligible claim | a **property of a claim** — its tier is C1/C2/C3 `[R: ladder.py:84-98]` | it is an attribute *of* a claim, not a separate thing |
| D. foundational precondition | condition on whether verification is *possible/meaningful* | **no** — presuppositional, not truth-functional |
| E. tool/action validity check | "is this action allowed for this tool in this state" — e.g. `ORDER_STATUS_SUPPORTS_ACTION` ("order is pending") | **partly** — this one *is* a factual claim about a record field and is modelled as a `ClaimKind` `[R: schema.py:170]`; it shades toward D but is representable |
| F. record-resolution check | `order_record_resolves` — a *sub-type of D* specific to "the lookup returned a row" | **no** |
| G. authorization / identity precondition | "the session actor is authentic / may act for this customer" — `independent_user_authentication` | **no** — a sub-type of D about the *actor*, not the *object*. ControlPlane explicitly does not authenticate the caller `[R: docs/threat-model.md:7, 99, 107]` |
| H. intervention gate | verdict → intervention mapping (compensability, `verdict_handling`) `[R: decide.py:414-438]` | **no** — a response policy, not an assertion |
| I. extraction / modelling requirement | "a correct verifier must *represent* this check" — the `required: true` axis `[R: bench/extraction_gold_v1.schema.json:113]` | **no** — a statement about verifier *completeness* |
| J. verification requirement | "this check must actually *run and pass*" — the P1 axis | **no** — a runtime outcome |

They all influence "should the action proceed", which is exactly why the task
warns against collapsing them. The load-bearing distinction for this review:
**A/B/E are truth-functional assertions (claims); D/F/G are presuppositional
gates (preconditions); C is an attribute of a claim; I and J are orthogonal
completeness/outcome axes; H is the response function.**

---

## 5. Current architecture (traced)

Pipeline `[R: docs/architecture.md:13-24; controlplane/intercept.py:173-295]`:

```
tool call ─▶ intercept._run_gate
   ├─ extract_action(tool, args, justification, retrieved)   → ProposedAction   (structural fields + claimed_* )
   ├─ load_manifest(CP_MANIFEST)                             → validated manifest
   ├─ build_claims(action, manifest)                         → one Claim per claim_binding      [extract.py:210-240]
   ├─ classify_claims                                        → tier + load_bearing per Claim    [ladder.py:108-114]
   ├─ resolve_bindings(claims, specs, session, manifest)     → one Evidence per Claim           [registry/__init__.py:89-103]
   ├─ build_predicate_payload → evaluate (Zen JDM graph)     → predicate_result{}               [predicates/__init__.py:43-114]
   ├─ decide(...)  (pure)                                    → Decision {verdict, intervention, verification_ledger}  [decide.py:267-470]
   └─ record(...)                                            → signed receipt + telemetry       [receipt.py:116-178]
```

Key structural facts:

- **The claim set is entirely manifest-driven.** `build_claims` iterates
  *only* `manifest["claim_bindings"]`; free-form agent text cannot add a claim;
  `ModellingState.UNMODELLED` is structurally `0` in production
  `[R: extract.py:210-240; schema.py:119-135; docs/verification-coverage.md:30-36]`.
- **`ClaimKind` is a closed enum of 15 members** `[R: schema.py:153-178]`.
  `ladder.py` must have a `_TIER` and `_LOAD_BEARING` row for every member or
  it raises at import `[R: ladder.py:117-123]`.
- **The one rule:** the extractor produces *claims* (hypotheses), the registry
  produces *facts*; `claimed_*` fields never reach a predicate
  `[R: schema.py:7-22, 241-256; bindings.py:30-48]`.
- **A missing DB *file*** raises a typed `SourceUnavailable` → the operational-
  failure path builds a `Decision` directly, no ledger; `resolved_verification_
  ledger` reconstructs an all-`UNAVAILABLE` ledger later
  `[R: registry/sqlite_source.py:43-58; intercept.py:75-170; decide.py:236-256]`.
- **A missing *row*** is **not** an exception. `OrdersResolver.resolve` returns
  `Evidence(value=None, confidence=Confidence.NONE,
  reliability_class=Reliability.UNVERIFIED, note="no order found for
  order_id=…")` and the **normal** `decide()` path runs, producing a real
  ledger `[R: orders.py:60-71; decide.py:117-179]`. This is the
  `order_record_resolves` case. Because that evidence is **both** below the
  `corroborated` reliability floor **and** `Confidence.NONE`, `decide()` sets
  **both** `source_unreliable` and `unverifiable`; `SOURCE_UNRELIABLE` has
  verdict precedence, so the verdict is **`SOURCE_UNRELIABLE`** (not
  `UNVERIFIABLE`), routed by `verdict_handling.SOURCE_UNRELIABLE: escalate` to
  **`ESCALATE`** `[R: decide.py:311-329, 400-409, 426-427; servicing.yaml:33-36;
  verified this session by deterministic recompute of gs-129]`.
- **P1 coverage is descriptive.** `decide()` computes the ledger from the same
  facts it used for the verdict and attaches it; it does not feed back into
  verdict or intervention `[R: decide.py:440-451; docs/verification-coverage.md:114-128]`.
  Metamorphic invariants M1–M5 are properties of `decide()` and are unaffected
  by the ledger `[R: docs/invariants.md:20-31]`.

---

## 6. `order_record_resolves` lifecycle

For a proposed `issue_refund` whose `order_id` resolves to **no row**
(`gs-129`, `OR-10283`):

| # | stage | is `order_record_resolves` present / represented? | evidence |
|---|---|---|---|
| 1 | **origin** | The *behaviour* exists: `OrdersResolver` returns `Confidence.NONE` evidence with `note="no order found for order_id='OR-10283'"`. The *named requirement* originates only in P3-B gold. | `[R: orders.py:60-71]` · `[B: bench/extraction_gold_v1.jsonl gs-129]` |
| 2 | **explicit in policy?** | **No.** No clause, no manifest field, no predicate-graph expression refers to record existence. | `[R: manifests/servicing.yaml; manifests/graphs/servicing.json; grep]` |
| 3 | **in tool / action input?** | **Partially.** `order_id` is a structural field of `ProposedAction`; "the id *resolves*" is not an input — it is an outcome of resolution. | `[R: schema.py:225-256]` |
| 4 | **in a manifest?** | **No.** `servicing.yaml` has 7 `claim_bindings`; none is a record-resolution check. | `[R: manifests/servicing.yaml:45-76]` |
| 5 | **has a `ClaimKind`?** | **No.** Not among the 15 enum members. | `[R: schema.py:153-178]` |
| 6 | **enters extraction?** | **No.** `build_claims` iterates `claim_bindings`; no binding ⇒ no `Claim`. | `[R: extract.py:210-240]` |
| 7 | **enters classification?** | **No.** `classify_claims` iterates the claim list; there is no claim to classify. | `[R: ladder.py:108-114]` |
| 8 | **enters P1 verification eligibility?** | **No.** `build_verification_ledger` builds one row per `Claim`; a non-claim is never a row, never load-bearing-eligible, never in the denominator. | `[R: decide.py:196-233]` |
| 9 | **enters the receipt?** | **Indirectly only** (all values below verified this session by deterministic recompute of `gs-129`): (a) 4 `evidence[]` entries with `value: null`, `confidence: "none"`, `reliability_class: "unverified"`, `note: "no order found for order_id='OR-10283'"`; (b) 4 `claims[].verification` rows = `{"status":"unavailable","reason":"authoritative_lookup_empty"}`; (c) `verification_coverage` = `{verified: 2, eligible: 7, coverage: 0.285714}`; (d) `reasons[]` = 4 interleaved pairs of `reliability_floor` + `<kind>_resolved`; (e) `root_cause` = `"evidence_below_reliability_floor"`; (f) `verdict` = `"SOURCE_UNRELIABLE"`, `verification_state` = `"unverified"`. **No field names the precondition.** | `[R: receipt.py:50-71, 74-114, 130-158; decide.py:150-158, 311-329]` |
| 10 | **influences intervention?** | **Yes, indirectly.** Every order-scoped load-bearing claim (`ORDER_BELONGS_TO_CUSTOMER`, `AMOUNT_NOT_EXCEEDING_ORDER`, `WITHIN_REFUND_WINDOW`, `ORDER_ATTRIBUTES_MATCH`) sees evidence below the reliability floor **and** `Confidence.NONE` ⇒ `source_unreliable = True` **and** `unverifiable = True` ⇒ verdict `SOURCE_UNRELIABLE` (precedence) ⇒ `verdict_handling.SOURCE_UNRELIABLE: escalate` ⇒ `ESCALATE`. | `[R: decide.py:311-329, 400-409, 426-427; servicing.yaml:33-36]` · `[B: reports/extraction-completeness-v1.md §8 — gs-129 → ESCALATE; verified this session — verdict `SOURCE_UNRELIABLE`]` |
| 11 | **failure observable / auditable?** | **Partially, and mislabelled.** An auditor *can* reconstruct "the order does not exist" from the 4 repeated evidence notes plus 4 `unavailable` claims. But it is **not named, not counted as a distinct thing**, and the two most prominent labels actively point elsewhere: `verdict = SOURCE_UNRELIABLE` and `root_cause = evidence_below_reliability_floor` both read as *"the source gave us low-quality data"*, when the truth is *"the record you asked about is absent"*. There is no `foundational_requirement` / `precondition` field. | `[I]` from `[R: receipt.py:50-71; decide.py:311-315]` · `[verified this session]` |

**One-line summary of the lifecycle:** the *failure mode* is handled safely
end-to-end (`ESCALATE`, never a fabricated pass); the *requirement* has no
representation at any stage — it exists in the architecture only as the shadow
cast by several claims going `UNAVAILABLE` together, under a verdict label
(`SOURCE_UNRELIABLE`) and root cause (`evidence_below_reliability_floor`) that
describe a different problem.

---

## 7. Why it is currently unrepresentable

Three independent structural reasons `[I, from R]`:

1. **No `asserted_value`.** `Claim` is `{id, kind, subject, asserted_value,
   tier, resolver, load_bearing}` `[R: schema.py:264-272]`. Every existing
   `ClaimKind` maps to a `ProposedAction` field whose value is the agent's
   assertion (`_ASSERTED_VALUE_FIELD` `[R: extract.py:84-102]`), except the two
   already-special derived checks (`EXCERPT_CONTAINS_THIRD_PARTY_PII`,
   `ORDER_ATTRIBUTES_MATCH`). `order_record_resolves` has nothing an agent
   asserts — "the record exists" is a presupposition of referencing it, not a
   statement about it.

2. **The check is on the *process*, not a *value*.** Every claim's outcome in
   `decide()` is a comparison: predicate flag, `clause_match`, or
   `grounding_score ≥ threshold` `[R: decide.py:86-114, 340-378]`. The record-
   resolution check is `Evidence.confidence != Confidence.NONE` — a property of
   whether resolution *succeeded*, which `decide()` already reads but treats
   only as "mark this claim `UNAVAILABLE` and flag the verdict `unverifiable` /
   `source_unreliable`", not as its own checkable proposition
   `[R: decide.py:155-158, 311-329]`.

3. **It is a common precondition, not a sibling.** In `gs-129` a *single* root
   cause (no row for `OR-10283`) produces *four* `UNAVAILABLE` claims
   `[B: bench/extraction_gold_v1.jsonl]`. A `ClaimKind` is a peer in a flat
   list `[R: schema.py:399, Decision.claims: list[Claim]]`; modelling a
   1-to-many precondition as one more peer loses the "these four are all
   downstream of that one" structure.

The P1 machinery itself anticipates this: `ModellingState.UNMODELLED` exists
precisely so "a future free-text claim miner cannot make a claim disappear
without leaving a trace" `[R: schema.py:119-135]` — but `order_record_resolves`
is not a claim the miner failed to model, it is a requirement with *no claim
shape to take*.

---

## 8. Option A — make foundational requirements first-class `ClaimKind`s

**Shape:** add `ORDER_RECORD_RESOLVES` (and, for consistency,
`CURRENCY_INTEGRITY`, and — where an evidence channel exists — an identity
kind) to the `ClaimKind` enum; add `_TIER` / `_LOAD_BEARING` rows; add a
`claim_binding` per order-acting manifest; wire a predicate or a
`decide()` special case.

**Consequences (all `[I]`, grounded in the cited code):**

| area | consequence |
|---|---|
| `ClaimKind` vocabulary | enum grows; every consumer that switches on `ClaimKind` (`ladder._TIER`, `ladder._LOAD_BEARING`, `decide._PREDICATE_FOR_KIND`, `orders._FIELD_FOR_KIND`, `extract._ASSERTED_VALUE_FIELD`) needs a row or an explicit exclusion `[R: those tables]` |
| gold / reference schema | `bench/extraction_gold_v1.schema.json` enumerates the 12 allowed `claim_kind`s `[R: :107-112]`; P3-B's `foundational_requirements[]` and P3-A's `UNREPRESENTABLE_REQUIRED` would have to migrate into `gold_claims[]` — **the frozen corpus would need re-authoring** (a stop condition — §23) |
| extraction | `build_claims` emits it; but its `asserted_value` is `None` (no agent assertion), so it is a second "derived check" exception alongside PII/attributes `[R: extract.py:232-239]` |
| verification eligibility | it enters `build_verification_ledger` as a load-bearing eligible claim ⇒ **it joins the P1 denominator** `[R: decide.py:210-219]` |
| P1 coverage number | **denominator integrity is lost.** P1's denominator is defined as *"the load-bearing claims that had an authoritative check path — not every claim that should have existed"* `[R: schema.py:356-369; docs/verification-coverage.md:96-99]`. `order_record_resolves` is exactly a "should have existed" precondition. Folding it in re-opens the circularity P1 was built to close `[R: docs/verification-coverage.md:8-14]` |
| double-count | for `gs-129` the receipt would show `ORDER_RECORD_RESOLVES: contradicted` **plus** `ORDER_BELONGS_TO_CUSTOMER / AMOUNT_NOT_EXCEEDING_ORDER / WITHIN_REFUND_WINDOW / ORDER_ATTRIBUTES_MATCH: unavailable` — one root failure represented as five ledger rows, four of which are not independent evidence `[I]` |
| receipts | one more `claims[]` row; `verification_coverage` denominator shifts from 7 to 8 on every `issue_refund`, changing a published, sha-covered number on **every** receipt `[R: receipt.py:94-114]` |
| intervention | see §14 — done meaningfully (missing record ⇒ hard `CONTRADICTED`), `gs-129/130/133/134` move `ESCALATE → BLOCK`; done cosmetically (missing record ⇒ `UNAVAILABLE`), it only adds denominator noise |
| mixing concerns | a precondition now lives in the same enum, same list, same ledger, same denominator as agent factual claims — the exact collapse task §8 warns against |
| generality | solves **one** of three L2 cases. `currency_integrity` and `independent_user_authentication` still have **no evidence channel** `[R: bench/extraction_reference.py:323-341]`, so they stay unrepresentable and the taxonomy is now inconsistent (one promoted, two not) |

**Where Option A is genuinely attractive:** it needs no new schema type, and a
reader scanning `claims[]` sees everything in one place. If the project's
priority were "one list, no new concepts", this is the cheaper path. But the
cost is paid in the one number P1 spent a whole phase making honest.

---

## 9. Option B — a separate foundational-precondition layer

**Shape `[REC]`:**

```
        Action preconditions        record_resolves? · currency_coherent? · actor_established?
                 │                   status ∈ {SATISFIED, VIOLATED, NOT_ESTABLISHED, NOT_APPLICABLE}
                 ▼
        Claim extraction            (unchanged)
                 ▼
        Claim verification          P1 coverage over representable claims  (unchanged denominator)
                 ▼
        Decision                    verdict + intervention
```

- A new type — call it `FoundationalRequirement` — with **its own status
  enum**, deliberately *not* `VerificationStatus`: `SATISFIED` / `VIOLATED` /
  `NOT_ESTABLISHED` (couldn't even determine) / `NOT_APPLICABLE`.
- **Its own denominator**, reported separately:
  `satisfied load-bearing preconditions / required load-bearing preconditions`
  — never added to `verified / eligible`.
- Declared per manifest in a new block (`foundational_requirements:` alongside
  `claim_bindings:`), or — for the first, descriptive iteration — derived by a
  read-only bench from the P3-A/P3-B references, exactly as
  `bench/manifest_claim_coverage.py` derives kind coverage today
  `[R: bench/manifest_claim_coverage.py:170-172]`.
- On the receipt: a `foundational_requirements` block **distinct from**
  `claims[]` and `verification_coverage`, inside the signature.
- **Descriptive-only first.** The layer reports status; it does not change
  verdict or intervention. This mirrors P1's "first validate the measurement;
  a promotion path can come later" `[R: docs/verification-coverage.md:114-128]`.
  Today's behaviour (missing record → `SOURCE_UNRELIABLE` → `ESCALATE`) is
  *already* at least as strict as a precondition gate would require, so a
  descriptive layer changes nothing the gate enforces.

**Consequences (`[I]` unless tagged):**

| area | consequence |
|---|---|
| P1 denominator | **untouched.** `verified / eligible` stays 7-wide for `issue_refund`; no circularity, no double-count `[R: decide.py:210-219 unchanged]` |
| claims that go `UNAVAILABLE` | still `UNAVAILABLE` on the receipt (honest), but now *attributable*: "these 4 are unavailable **because** precondition `order_record_resolves` = VIOLATED" |
| status model | a failed precondition is distinguishable from `CONTRADICTED` (evidence refutes a claim) and from `UNAVAILABLE` (a claim's evidence couldn't be obtained) — see §13 |
| audit | the auditor gets a first-class line, not a four-note inference; `root_cause` can point at the precondition instead of mis-pointing at the ownership check |
| extensibility | `order_record_resolves`, `currency_integrity`, `independent_user_authentication` are **one shape with one home**; P3-A's `UNREPRESENTABLE_REQUIRED` and P3-B's `foundational_requirements[]` unify into it |
| tau2 | `ORDER_BELONGS_TO_CUSTOMER`-as-identity becomes representable *as a precondition with status `NOT_ESTABLISHED`* even where it is unbindable *as a claim* — the gap stays visible with its reason attached, which is exactly what P3-A already does in prose `[R: bench/extraction_reference.py:106-123]` |
| new concept cost | one new type, one new enum, one new receipt block, one new (small) denominator. Not a framework — the same order of addition as P1's `ClaimVerification` / `VerificationLedger` `[R: schema.py:331-390]` |
| invariants | `decide()` stays pure; M1–M5 unaffected while the layer is descriptive `[R: docs/invariants.md:11-13]` |

---

## 10. Comparison table

| criterion (task §16) | Option A — `ClaimKind` | Option B — separate layer |
|---|---|---|
| 1. conceptual correctness | ✗ models a presuppositional gate as a truth-functional assertion | ✓ matches the actual structure (§4) |
| 2. separation of concerns | ✗ preconditions share the enum/list/ledger with agent claims | ✓ distinct type, status model, denominator |
| 3. auditability | ~ one list, but a 1:N failure shows as 5 rows, 4 non-independent | ✓ one named line + attributable claim unavailability |
| 4. verification semantics | ✗ "verified" would have to mean "a lookup returned a row" for one kind and "evidence supports the assertion" for the rest | ✓ verification semantics untouched; precondition has its own vocabulary |
| 5. denominator integrity | ✗ re-opens the "claims that should have existed" circularity P1 closed | ✓ P1 denominator unchanged; separate small denominator for preconditions |
| 6. extraction completeness | ~ makes *one* L2 case a claim; other two still unrepresentable | ✓ all L2 cases in one representation |
| 7. intervention correctness | ✗ meaningful wiring flips `gs-129/130/133/134` `ESCALATE→BLOCK` (§14) | ✓ descriptive-first = no change; promotion is a separate, explicit decision |
| 8. receipt clarity | ~ familiar shape, misleading counts | ✓ "not represented" is separate from "not verified" (§13) |
| 9. extensibility across tools | ✗ every order tool needs a binding + the two channel-less cases block it | ✓ uniform; channel-less cases report `NOT_ESTABLISHED` |
| 10. compatibility w/ current arch | ~ touches enum + 5 dispatch tables + frozen gold schema | ✓ additive; frozen gold untouched; `decide()` untouched |
| 11. distinguishes the 5 states (task §16.11) | ✗ collapses "unmodelled requirement" into "a claim" | ✓ see §13 — five distinct states |
| 12. risk of misleading coverage | ✗ high — the headline number moves and conflates two things | ✓ low — two numbers, each named, each recomputable |

Legend: ✓ meets · ~ partial / conditional · ✗ fails.

---

## 11. Impact on P1 verification coverage

- **Option A:** `verification_coverage.eligible` for `issue_refund` goes 7 → 8
  on every action; the ratio denominator changes on every receipt; and a
  precondition now sits in a population defined to exclude preconditions
  `[R: schema.py:356-369]`. If `ORDER_RECORD_RESOLVES` resolves `VERIFIED` on
  the happy path (record found), coverage *rises* on clean actions for a reason
  unrelated to how much of the agent's reasoning was checked — precisely the
  "measures nothing" failure mode of the retired `coverage_ratio`
  `[R: docs/verification-coverage.md:8-14]`.

- **Option B:** P1's number, ledger, receipt block, and `decide()` path are
  **unchanged** `[REC]`. The missing-record cases still read ≈28.6% — which is
  now *correct and informative*: "only 2 of 7 representable load-bearing claims
  were verifiable, **because** a foundational precondition failed". The
  precondition layer carries its own ratio
  (`satisfied / required` preconditions), reported beside P1, never inside it.

**Neither option should let a precondition failure inflate P1 coverage.**
Option B achieves this by construction; Option A requires care that its own
structure works against.

---

## 12. Impact on extraction completeness

P3-C's `claim_set_recovery` (100%) is a statement about the **representable**
claim set and does not change under either option — the extractor already
recovers every representable claim `[B]`.

- **Option A** would convert the 30 `unmodelled_required` instances into 30
  ordinary gold claims. Recall would still be 100% *only if* the extractor is
  then updated to emit the new kind; until then P3-C recall would **drop** and
  the frozen corpus would be invalid (stop condition, §23).

- **Option B** keeps `unmodelled_required` as the honest count of load-bearing
  checks with no claim shape, and adds a **precondition-coverage** measurement
  (`required_preconditions_with_a_status / required_preconditions`) as the
  companion to P3-A's kind-coverage and P1's verification-coverage. Three
  numbers, three questions, no overlap:

  | metric | question |
  |---|---|
  | P3-A manifest claim-coverage | of the required *kinds*, how many does the manifest *bind*? |
  | P1 verification coverage | of the *bound* load-bearing claims, how many *verified* on this decision? |
  | **precondition coverage (new)** | of the required *foundational preconditions*, how many have a *known status* on this decision, and how many are *satisfied*? |

---

## 13. Impact on receipts

Current missing-record receipt for `gs-129`, **verified this session by a
deterministic offline recompute** (`build_receipt` over `run_p1('gs-129')`,
frozen clock `2026-08-14`, no LLM, no network, nothing written):

```jsonc
{
  "verdict": "SOURCE_UNRELIABLE",                          // reads as "the source gave bad data"
  "intervention": "ESCALATE",
  "root_cause": "evidence_below_reliability_floor",         // also reads as a data-quality problem
  "verification_state": "unverified",
  "verification_coverage": { "verified": 2, "eligible": 7, "coverage": 0.285714, "coverage_na": false },
  "reasons": [
    { "rule": "reliability_floor",                   "expected": "corroborated", "observed": "unverified", "policy_version": "servicing-v1" },
    { "rule": "order_belongs_to_customer_resolved",  "expected": "a value",     "observed": null,         "policy_version": null },
    { "rule": "reliability_floor",                   "expected": "corroborated", "observed": "unverified", "policy_version": "servicing-v1" },
    { "rule": "amount_not_exceeding_order_resolved", "expected": "a value",     "observed": null,         "policy_version": null },
    { "rule": "reliability_floor",                   "expected": "corroborated", "observed": "unverified", "policy_version": "servicing-v1" },
    { "rule": "within_refund_window_resolved",       "expected": "a value",     "observed": null,         "policy_version": null },
    { "rule": "reliability_floor",                   "expected": "corroborated", "observed": "unverified", "policy_version": "servicing-v1" },
    { "rule": "order_attributes_match_resolved",     "expected": "a value",     "observed": null,         "policy_version": null }
  ],
  "claims": [
    { "kind": "order_belongs_to_customer",  "verification": {"status":"unavailable","reason":"authoritative_lookup_empty"} },
    { "kind": "amount_not_exceeding_order", "verification": {"status":"unavailable","reason":"authoritative_lookup_empty"} },
    { "kind": "within_refund_window",       "verification": {"status":"unavailable","reason":"authoritative_lookup_empty"} },
    { "kind": "amount_within_authority",    "verification": "verified" },
    { "kind": "policy_clause_current",      "verification": "verified" },
    { "kind": "clause_semantics_match",     "verification": {"status":"unverified","reason":"no_conclusive_check_ran"} },
    { "kind": "order_attributes_match",     "verification": {"status":"unavailable","reason":"authoritative_lookup_empty"} }
  ],
  "evidence": [
    { "claim_id":"OR-10283:order_belongs_to_customer", "value": null, "confidence":"none",
      "reliability_class":"unverified",
      "query":"SELECT customer_id FROM orders WHERE order_id = 'OR-10283'",
      "note":"no order found for order_id='OR-10283'" }
    // ...three more, identical note, for amount_not_exceeding_order / within_refund_window / order_attributes_match
  ]
}
```

The information *is* there — four evidence notes and four `unavailable` claims.
What is missing is a **name for the thing that went wrong**, and what is
*present* actively points away from it: `verdict` and `root_cause` both say
"unreliable source" when the record is simply absent. Answering task §14's
questions:

| question | Option A | Option B `[REC]` |
|---|---|---|
| should a failed foundational precondition appear on the receipt? | yes — as a `claims[]` row | **yes — as a distinct `foundational_requirements` block** |
| should it count toward verification coverage? | it would, unavoidably | **no — separate ratio** |
| should it have its own status? | no — reuses `VerificationStatus` | **yes — `SATISFIED / VIOLATED / NOT_ESTABLISHED / NOT_APPLICABLE`** |
| distinguishable from `CONTRADICTED`? | ✗ if wired as a hard check, it *is* `CONTRADICTED` | **✓ different enum, different block** |
| distinguishable from `SOURCE_UNRELIABLE` / `UNAVAILABLE`? | ✗ the four downstream claims are already `UNAVAILABLE` and the verdict is already `SOURCE_UNRELIABLE` | **✓ the precondition is `VIOLATED`; the claims are `UNAVAILABLE` *because of it*; the verdict label is free to be corrected** |
| can an auditor reconstruct why the action was not permitted? | ~ yes, from 8 reasons + 4 claims + 4 evidence notes, past a misleading verdict label | **✓ yes, from one line: `order_record_resolves: VIOLATED`** |
| can the receipt expose "not represented" separately from "not verified"? | ✗ no — everything is a claim | **✓ that is the entire point of the separate block** |

Two secondary receipt fixes the implementation task should carry, **not made
by this review** `[REC]`:

- `_root_cause` should recognise the record-resolution case and emit e.g.
  `root_cause: "order_record_unresolved"` instead of falling through to
  `evidence_below_reliability_floor` `[R: receipt.py:50-71]`.
- the verdict label for "the record does not exist" is arguably wrong as
  `SOURCE_UNRELIABLE` — the source was perfectly available and answered
  correctly ("no such row"). Whether a missing record should carry its own
  verdict/label, or stay `SOURCE_UNRELIABLE`, or move to `UNVERIFIABLE`, is a
  **design question for the precondition-layer spec**, not something to change
  in `decide()` now.

---

## 14. Impact on intervention

**Current `[R + B]`, verified this session:** missing row ⇒ 4 load-bearing
order-scoped claims see evidence below the reliability floor **and**
`Confidence.NONE` ⇒ `source_unreliable` **and** `unverifiable` both set ⇒
verdict `SOURCE_UNRELIABLE` (precedence) ⇒
`verdict_handling.SOURCE_UNRELIABLE: escalate` ⇒ `ESCALATE`
`[R: decide.py:311-329, 400-409, 426-427; servicing.yaml:33-36]`. Matches the
P3-C per-case table (`ESCALATE`) for `gs-129/130/133/134`.

**Option A, wired meaningfully** (missing record ⇒ `ORDER_RECORD_RESOLVES`
predicate returns `False` ⇒ a hard `C1` contradiction on reliable evidence):
`hard_contradiction = True` ⇒ verdict `CONTRADICTED`, which **overrides**
`SOURCE_UNRELIABLE` in the precedence chain `[R: decide.py:400-409]`.
`servicing.yaml` compensability is `fully` `[R: servicing.yaml:15-17]`, so
`_intervention_for(CONTRADICTED, c3_only=False)` returns `BLOCK`
`[R: decide.py:421-425]`. **`gs-129/130/133/134` move `ESCALATE → BLOCK`.**
That is a material change to submitted behaviour on four corpus cases and is
close to a stop condition (§20).

**Option A, wired cosmetically** (missing record ⇒ `ORDER_RECORD_RESOLVES`
evidence `Confidence.NONE` ⇒ the claim is `UNAVAILABLE` like the others):
no behaviour change, but the P1 denominator for `issue_refund` is now 8 with 5
of 8 unavailable (≈25%) — a worse, noisier number that still measures nothing
new.

**Option B, descriptive-first `[REC]`:** the precondition layer reports
`order_record_resolves: VIOLATED`; `decide()` is unchanged; the gate still
`ESCALATE`s exactly as it does today. **Zero behaviour change.**

**Option B, if later promoted (a separate, explicit decision — §21):** a
failed load-bearing precondition could *floor* the intervention at `ESCALATE`
(which is already where these cases land) or at `BLOCK`. Whether a missing
record should `BLOCK` rather than `ESCALATE` is a **policy question** this
review does not answer and must not answer silently.

---

## 15. Impact on auditability

| today | Option B |
|---|---|
| "why was this not allowed?" → read 8 `reasons`, 4 claim rows, 4 evidence notes, and get past a `SOURCE_UNRELIABLE` verdict that is not what happened | → read one line: `order_record_resolves: VIOLATED` |
| "was this checked and failed, or never checked?" → `unavailable` claim vs `unverified` claim vs a real source outage all look similar | → `VIOLATED` precondition vs `UNVERIFIED` claim vs `UNAVAILABLE` claim are three different things in two different blocks |
| "did the verifier even know it needed the record?" → not answerable from the receipt | → `required: true` on the precondition row answers it |
| verdict / `root_cause` | `SOURCE_UNRELIABLE` / `evidence_below_reliability_floor` — both describe a data-quality problem that did not occur | free to name the precondition |

Option B directly serves the receipt's stated purpose — *"the clear audit
trail behind every decision … the thing that goes on screen and makes a judge
understand the entire pitch in four seconds"* `[R: docs/decision-receipt.md:1-8]`
— for the one case where today's receipt makes the judge do detective work.

---

## 16. Generality beyond `issue_refund`

The finding is **not** specific to `issue_refund`. Evidence of analogous
foundational requirements elsewhere in the *current* architecture:

| requirement | tools | category | representable as a claim today? | source |
|---|---|---|---|---|
| `order_record_resolves` | `issue_refund` (and, by the same logic, every order-acting tool) | record resolution (F) | **no** | `[B: P3-B foundational_requirements[]; P3-C §15]` |
| `currency_integrity` | `issue_refund`, `approve_discount`, `approve_service_credit` | field integrity (D) | **no** — "no `ClaimKind` expresses currency / field integrity today" | `[R: bench/extraction_reference.py:323-331; reports/manifest-claim-coverage.md:33]` |
| `independent_user_authentication` | all 6 tau2 retail tools | actor authentication (G) | **no** — "no claim kind or evidence channel for 'the session user is who they claim to be'" | `[R: bench/extraction_reference.py:332-341; reports/manifest-claim-coverage.md:34]` |
| `ORDER_BELONGS_TO_CUSTOMER` (as an identity/ownership precondition) | all 6 tau2 retail tools | authorization / ownership (G) | representable as a *claim*, but **unbindable** in tau2 — no DB-level authenticated-identity channel | `[R: bench/extraction_reference.py:106-123; manifests/tau2_cancel_pending_order.yaml:6-15]` |
| `AMOUNT_NOT_EXCEEDING_ORDER` unbound by `discount_approval` | `approve_discount` | **a representable claim simply not bound** — *different category* | `[R: reports/manifest-claim-coverage.md:11, 26; bench/extraction_reference.py:237-252]` |

Two distinct problems are visible here and must not be conflated `[REC]`:

1. **Representable-but-unbound** (`discount_approval` / `AMOUNT_NOT_EXCEEDING_
   ORDER`): a `ClaimKind` exists; the manifest omits the binding. P3-A already
   measures this as a kind-coverage miss. **Not** a foundational-requirement
   problem. **Carried forward unresolved as `NEEDS_HUMAN_DECISION`** — this
   review does not touch it.

2. **Unrepresentable** (`order_record_resolves`, `currency_integrity`,
   `independent_user_authentication`, tau2 identity): no claim shape exists.
   **This** is the foundational-requirement class, and it already has **four
   known members across three tool families**. That count is the strongest
   single argument that this is an abstraction, not a one-off `[I]`.

`send_document` (use case 2) is a useful negative check: its two required
kinds (`RECIPIENT_ENTITLED_TO_DOC`, `DOC_CLASSIFICATION_PERMITTED`) are both
bound and representable, and its one "expected but omitted" kind
(`EXCERPT_CONTAINS_THIRD_PARTY_PII`) is a *deliberate* non-requirement, not an
unrepresentable one `[R: bench/extraction_reference.py:197-215, 299-309]`. So
not every tool has an unrepresentable foundational requirement — but three of
the five tool families do.

---

## 17. tau2 comparison

`ORDER_BELONGS_TO_CUSTOMER` for the tau2 retail tools is the cleanest existing
parallel `[R: reports/manifest-claim-coverage.md:28-29;
bench/extraction_reference.py:106-123; manifests/tau2_cancel_pending_order.yaml:6-15]`:

- The check is **required** and **load-bearing** (you cannot correctly cancel /
  modify / return an order without establishing it is the requester's — T2,
  T34).
- It is **representable as a `ClaimKind`** (unlike `order_record_resolves`).
- It is **unbindable in the tau2 domain as integrated**: tau2 exposes no
  structural, DB-level authenticated-identity channel independent of the agent
  conversation; binding it would need previous-tool-output (disallowed) or the
  evaluator's hidden ground truth (circular).
- Its status is recorded as **`REQUIRED_BUT_UNREPRESENTABLE`** and **must not
  change** (task §12, §20). This review uses it only as evidence.

**What tau2 shows for the architecture question:** even a check that *has* a
`ClaimKind` can be **required but not satisfiable** for reasons that are
properties of the *integration*, not the vocabulary. P3-A already handles this
by keeping the requirement listed with its reason attached in
`binding_note` / `UNREPRESENTABLE_REQUIRED` — i.e. P3-A **already built a
lightweight separate-layer representation in prose**. Option B is the
generalisation of what P3-A did ad hoc: a structured home for
"required, here is its status, here is why" that works whether the blocker is
*no `ClaimKind`* (`order_record_resolves`), *no evidence channel*
(`independent_user_authentication`), or *no bindable channel in this
integration* (tau2 `ORDER_BELONGS_TO_CUSTOMER`).

Option A cannot express the tau2 case at all — there is nothing to bind, so
adding a `ClaimKind` changes nothing there.

---

## 18. Threat-model implications

The finding maps onto existing threats `[R: docs/threat-model.md]`; **no new
threat category is required** `[REC]`:

| threat | relevance | current status |
|---|---|---|
| **T8 — Source row is missing** | *the* direct match: "Lookup finds no entity → resolver returns `Confidence.NONE` evidence; decision does not manufacture a favorable fact" | `MITIGATED` (engineering). The mitigation is real and P3-C confirms it (`ESCALATE`, not a fabricated pass). The *representation* gap is not a T8 regression. |
| **T32 — Extraction differs from agent intent** | "Extractor omits or changes intended meaning … claim completeness" — status `NOT TESTED` | P3-B/P3-C are the first tests of this. `order_record_resolves` is the concrete instance of "a load-bearing dimension can be missing while the receipt reads 100% covered" `[R: docs/extraction-reliability.md:28-37]` |
| **T1 — Incorrect factual claim** | residual risk explicitly names "Unmodelled claims and unchecked semantics remain" | unchanged |
| **T27 — Agent and resolver share a store** | a missing row in the shared store is exactly where "correlated source error" and "record absence" meet | `DOCUMENTED LIMITATION` |
| **silent-pass / denominator** | P3-A's silent-pass analysis (`docs/extraction-reliability.md:129-160`) is the kind-level version of this | P3-C gives the instance-level version: 4 structural gaps, 0 realized |

**What changes in the threat model's language `[REC]`, if Option B is adopted:**
T8's residual-risk column could note that the missing-row condition is now
*named and counted* as a foundational-precondition status, not only inferable
from claim unavailability — i.e. the mitigation gains an **observability**
property it does not currently have. This is a documentation edit for a later
task, not a new threat.

If the project preferred a new label, the honest name would be
**"required precondition outside the representable model"** — but T32 already
covers it, and the taxonomy's own rule is "do not invent a new threat unless
the existing one genuinely cannot express the finding" `[R: task §15]`. It can.

---

## 19. Recommended architecture

**`[REC]` Option B — a separate foundational-precondition layer, introduced
descriptively first.**

Reasons, in priority order:

1. **Conceptual correctness (§4).** `order_record_resolves` fails every
   structural test for being a claim: no `asserted_value`, checked on the
   *process* not a *value*, one-to-many with claims, not agent-attributable.
   Three independent reasons, each grounded in the code.

2. **Denominator integrity (§8, §11).** P1's entire contribution was making
   the coverage number able to fail by defining its denominator as *"claims
   that had a check path"*, explicitly excluding *"claims that should have
   existed"*. `order_record_resolves` is a "should have existed" precondition.
   Option A puts it back in the denominator; Option B keeps it out.

3. **It is already an abstraction, found repeatedly (§2, §16).**
   `currency_integrity`, `independent_user_authentication`,
   `order_record_resolves` — three no-`ClaimKind` requirements, plus tau2's
   `ORDER_BELONGS_TO_CUSTOMER` (a `ClaimKind` exists but no bindable channel):
   one shape, four instances, currently living in two artifacts with no runtime
   representation and no shared definition. P3-A's `binding_note` /
   `UNREPRESENTABLE_REQUIRED` is a prose prototype of the layer.

4. **No behaviour change (§14).** Descriptive-first Option B changes nothing
   the gate enforces. Option A, wired meaningfully, moves four submitted corpus
   cases `ESCALATE → BLOCK`.

5. **It matches the project's own established discipline.** P1 was added
   descriptively, validated, and left un-promoted pending an explicit decision
   `[R: docs/verification-coverage.md:114-128]`. The same staging applies here
   and for the same reason: *"a benchmark that cannot fail is worth less than
   no benchmark"* `[R: docs/limitations.md:262-264]`, and a coverage number
   that silently conflates "not verified" with "not representable" is the same
   trap.

6. **Auditability (§13, §15).** The one case where today's receipt makes an
   auditor infer the root cause from four repeated evidence notes — and where
   `root_cause` actively mis-points — is exactly the case a named precondition
   line fixes.

7. **Generality (§16, §17).** One representation covers no-`ClaimKind`,
   no-evidence-channel, and no-bindable-channel-in-this-integration. Option A
   covers only the first, and only where a channel exists.

---

## 20. What should NOT change

`[REC]` — explicit non-goals, several of them protected by task constraints:

- **P1 `verification_coverage`** — its formula, denominator (`load_bearing_
  verification_eligible_claims`), ledger, receipt block, and the fact that it
  does not feed verdict/intervention. `[R: docs/verification-coverage.md]`
- **The `ClaimKind` enum** — no new members. `[R: schema.py:153-178]`
- **`decide()`** — stays a pure function of record facts; M1–M5 hold.
  `[R: decide.py:1-29; docs/invariants.md]`
- **Submitted intervention behaviour** — `gs-129/130/133/134` stay `ESCALATE`;
  the ALLOW/BLOCK/ESCALATE outcomes in `reports/extraction-completeness-v1.md`
  §8 are frozen.
- **The frozen P3-B gold corpus** — sha
  `79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d`,
  `bench/extraction_gold_v1.*`, and P3-C's results. `[R: task §18]`
- **The four carried-forward human/policy decisions** — all still open:
  1. `approve_discount` / `AMOUNT_NOT_EXCEEDING_ORDER` = `NEEDS_HUMAN_DECISION`
  2. tau2 / `ORDER_BELONGS_TO_CUSTOMER` = `REQUIRED_BUT_UNREPRESENTABLE`
  3. refund day-7 inclusion = `AMBIGUOUS`
  4. `gs-145–150` post-window disposition = `BLOCK | ESCALATE` unresolved
- **`docs/p06-post-p02-integrity.sha256`** and the known P06 test failure
  (`tests/test_tau2_c2_controlplane_side.py::test_post_p02_integrity_record_
  accounts_for_one_authorized_change`) — untouched, stale hash, unrelated.
- **Whether a failed precondition should ever `BLOCK`** — a policy question,
  deliberately left open (§21).

---

## 21. Open human / policy decisions

These must be decided by a human before any *promotion* of the layer beyond
descriptive; none is decided here:

1. **Should a failed load-bearing foundational precondition feed intervention
   at all?** If yes: floor at `ESCALATE` (status quo for the record case) or at
   `BLOCK`? A missing order record and a wrong-currency payout may warrant
   different floors.
2. **`currency_integrity`** — does it get an evidence channel (compare tool-call
   `currency` to the resolved order's currency column), which would make it a
   *representable claim* and move it out of the foundational-requirement class
   entirely? This is a modelling decision with a real answer, unlike the tau2
   identity gap.
3. **`independent_user_authentication` / tau2 identity** — remains
   `REQUIRED_BUT_UNREPRESENTABLE`; the layer would only make the gap *visible
   and counted*, not closed. Confirm that visibility-without-closure is the
   intended posture (P3-A already takes it).
4. **Per-manifest declaration vs derived** — should preconditions be declared
   in each manifest (`foundational_requirements:` block) or derived read-only
   from the P3-A/P3-B references? Declaration is more honest per-use-case;
   derivation ships faster and keeps the reference as the single source.
5. **Receipt size** — the receipt is already over its ≈2 KB design target
   `[R: docs/verification-coverage.md:160-169]`; a new block adds to that.
   Acceptable? (P1's block was kept "because the block is load-bearing audit
   evidence" — the same argument applies.)

---

## 22. Proposed next implementation task (if any)

`[REC]` — **one** of the following, not both, and still no change to
`schema.py` / `decide.py` / `ladder.py` / `extract.py` / `receipt.py` /
`intercept.py` / manifests / the frozen gold:

**Option B-1 (lightest — recommended first):** a read-only bench,
`bench/foundational_requirement_coverage.py`, that derives per-manifest and
per-case foundational-requirement status from the existing P3-A
`UNREPRESENTABLE_REQUIRED` + P3-B `foundational_requirements[]` +
(for the runtime status) the P1 ledger's `UNAVAILABLE` pattern, and writes
`reports/foundational-requirement-coverage.md`. This is the exact analogue of
`bench/manifest_claim_coverage.py` and needs zero production change. It makes
the gap a *number* alongside P3-A and P1, which is the same move P3-A made for
kind coverage.

**Option B-2 (design spec, no code):** a `docs/` spec for the
`FoundationalRequirement` type, its status enum, the `foundational_
requirements:` manifest block, the receipt block, and the separate denominator
— to be reviewed before any of it is built.

**Do not** proceed to P4. **Do not** implement Option A. **Do not** wire any
precondition into `decide()`.

---

## 23. Limitations

- **`[B]` scope.** P3-C is a deterministic benchmark over 30 `issue_refund`
  cases on ≈22 orders (L-CLUSTER), one manifest, one tool. `send_document`,
  `approve_discount`, `approve_service_credit`, and the tau2 tools are not
  exercised by it. The generality argument in §16 rests on the *P3-A
  reference* and the *manifests*, not on a run.
- **`[B]` the assertion-value (LLM) layer is not measured.** All "100%"
  figures are structural claim-set recovery. This review's argument does not
  depend on the LLM layer, but the reader should not read "100%" as
  end-to-end extraction accuracy `[R: reports/extraction-completeness-v1.md
  §0, §19]`.
- **The `gs-129` receipt in §13 was recomputed this session**, not taken from
  a stored artifact — `decisions.jsonl` in this tree contains no
  `SOURCE_UNRELIABLE` / `UNVERIFIABLE` receipt (11 lines: 8 `CONTRADICTED`, 3
  `VERIFIED`). The recompute called the real `run_p1('gs-129')` →
  `controlplane.decide.decide` → `controlplane.receipt.build_receipt` under the
  frozen clock, wrote nothing, and left HEAD and the gold hash unchanged. Its
  output (`verdict SOURCE_UNRELIABLE`, `root_cause evidence_below_reliability_
  floor`, `coverage 2/7`, `reason authoritative_lookup_empty`) is quoted
  verbatim. `[verified this session]`
- **`[I]` the "ESCALATE → BLOCK under Option A" claim (§14)** assumes Option A
  is wired so that a missing record is a hard `C1` contradiction on reliable
  evidence. A different wiring gives a different (worse-for-different-reasons)
  outcome. The point stands either way; the specific transition is
  wiring-dependent.
- **`[REC]` no metric is invented.** §12's "precondition coverage" is
  described conceptually only, as task §13 permits. Whether it is
  `satisfied/required`, `known-status/required`, or both is left to Option B-2.
- **This review does not establish that a live silent-pass is reachable.**
  P3-C found 0 realized opportunities. For `issue_refund` specifically, a
  missing record forces ≥4 of 7 load-bearing claims to `UNAVAILABLE`, so
  coverage cannot reach the ≥80% silent-pass threshold on that tool `[I, from
  R: servicing.yaml claim_bindings + orders.py]`. The structural concern is
  general; the realized risk on this tool is bounded low.
- **Policy neutrality.** Every one of the four carried-forward ambiguities
  (§20) is left exactly as found. The recommendation is an *architecture*
  choice (B over A) that does not require any of them to be resolved.

---

## Appendix — files read for this review

`controlplane/`: `schema.py`, `extract.py`, `ladder.py`, `decide.py`,
`receipt.py`, `intercept.py`, `bindings.py`, `manifest.py`, `compensation.py`,
`errors.py`, `ground.py`, `registry/__init__.py`, `registry/orders.py`,
`registry/sqlite_source.py`, `predicates/__init__.py`, `telemetry.py`.

`manifests/`: `servicing.yaml`, `discount_approval.yaml`,
`service_credit_approval.yaml`, `tau2_cancel_pending_order.yaml`,
`graphs/servicing.json`.

`docs/`: `verification-coverage.md`, `decision-receipt.md`,
`extraction-reliability.md`, `extraction-gold-annotation.md`,
`threat-model.md`, `architecture.md`, `invariants.md`, `limitations.md`,
`policy-manifest.md`, `gold-set.md` (§1, §6).

`bench/`: `extraction_reference.py`, `extraction_completeness_bench.py`
(structure + alignment/silent-pass logic), `extraction_gold_v1.schema.json`,
`extraction_gold_v1.meta.json`, `extraction_gold_v1.jsonl` (gs-005, gs-129),
`manifest_claim_coverage.py` (unrepresentable handling).

`reports/`: `extraction-completeness-v1.md`, `extraction-completeness-v1.json`,
`manifest-claim-coverage.md`, `verification-coverage.md`.

`tests/`: `test_extraction_completeness_bench.py`.

`decisions.jsonl` (verdict distribution + one CONTRADICTED receipt shape).
