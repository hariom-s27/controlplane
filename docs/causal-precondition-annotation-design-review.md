# P3-F — Read-Only Causal Precondition Annotation: Design Gate

> **Historical record (last changed 2026-11-13).** This file records work as of that date and is not maintained. Numbers, file paths and status statements in it are not current claims; current numbers are in `docs/claims.yaml` (checked by `tests/test_claims.py`) and corrections to frozen reports are in `docs/errata.md`.

**Task:** P3-F READ-ONLY CAUSAL PRECONDITION ANNOTATION DESIGN GATE
**Predecessor:** P3-E (`reports/foundational-requirement-coverage-v1.md`) — frozen, not modified.
**Repository HEAD:** `5b82915bf3d5be089c046f99b2d1b6b9133a34f0` (`v1.0-round2`).
**Branch:** `p1-verification-coverage`.
**Status:** READ-ONLY — zero production files modified.

Every line below is tagged: **[DRE]** direct repository evidence · **[AI]** architectural inference · **[REC]** recommendation.

---

## 1. Proposition Under Test

> "A read-only causal-precondition annotation exposes a deterministic
> dependency that is **not already reconstructible from P1**, without
> claiming stronger causality than the evidence supports."

This is P3-E §28.3's surviving recommendation after P3-E falsified the
standalone foundational-requirement coverage percentage.  P3-F does NOT
assume this annotation should be implemented.  The task succeeds even if
the answer is "do not implement."

---

## 2. P3-E Context & Constraints Carried Forward

**[DRE]** P3-E established (all frozen, not re-derived here):

| P3-E finding | Status | P3-F treatment |
|---|---|---|
| Coverage percentage INVALID (degenerate, manipulable) | Confirmed | Not rescued. No coverage % computed. |
| Claim/precondition boundary survives falsification | Confirmed | Tested further (§5–§7). |
| `currency_integrity` = ordinary claim missing a ClaimKind | Confirmed | Preserved unchanged (§17). |
| `tau2::independent_user_authentication` = conceptually required, runtime-unassessable | Confirmed | Preserved unchanged (§18). |
| Per-case causal annotation = the only candidate that survived | Under test | This document's purpose. |
| Silent-pass: 4 structural, 0 realized | Confirmed | Not re-derived (§20). |

**Constraints from the task specification:**
- Do NOT calculate: foundational coverage %, precondition success %, causal coverage %, safety score, readiness score, weighted score, cross-tool foundational percentage.
- Do NOT treat A (static dependency), B (runtime causality), and C (correlational co-occurrence) as equivalent.
- Temporal ordering alone is NOT causal evidence.
- Burden of proof: **NEW AUDIT VALUE**, not **DIFFERENT LABEL**.

---

## 3. Definitions: Three Kinds of "Because"

The annotation claims "these N claims are UNAVAILABLE **because** precondition X
was not satisfied."  The word "because" hides three structurally different
relationships.  P3-F MUST NOT treat them as equivalent:

| Label | Relationship | Evidence required | Example |
|---|---|---|---|
| **A. Static dependency** | X's schema position makes Y's evaluation impossible by construction | Code trace showing Y's resolver requires X's output | `orders.py` returns `Confidence.NONE` when `row is None` → `decide.py` assigns `UNAVAILABLE` |
| **B. Runtime causality** | X failed at time t₁, and this failure caused Y to fail at time t₂ | Runtime log with timestamps, no confounders | Not available in the current architecture — `decide()` is a pure function with no causal log |
| **C. Correlational co-occurrence** | X failed and Y failed in the same case | Co-occurrence count; no directional evidence | 4/4 missing-record cases show both `order_record_resolves=VIOLATED` and 4 claims `UNAVAILABLE` |

**[AI] The current evidence supports A (static dependency) and C (co-occurrence).  It does NOT support B (runtime causality).**  The `decide()` function (`decide.py:267-470`) is a pure function — it receives pre-resolved evidence and evaluates claims.  There is no runtime log of "X failed, causing Y to fail."  The dependency is structural: `orders.py:60-70` returns `Evidence(confidence=Confidence.NONE)` when the row is absent, and `decide.py:151-158` assigns `UNAVAILABLE` when `ev.confidence == Confidence.NONE`.  This is a code-level guarantee, not a runtime causal observation.

**The annotation must claim A (static dependency), not B (runtime causality).**

---

## 4. The Proposition Decomposed

The proposition has three independent clauses, each a gate:

| Gate | Clause | Required evidence |
|---|---|---|
| G1 | The dependency is deterministic | Code trace: X absent → Y UNAVAILABLE, no exceptions |
| G2 | The annotation exposes information not already reconstructible from P1 | Show what P1 outputs for gs-129 and what an auditor must infer vs. what the annotation would state |
| G3 | The annotation does not claim stronger causality than supported | Compare the annotation's "because" to the evidence type (A, B, or C) |

**All three gates must pass for the proposition to hold.  Failure of any one gate is sufficient to reject.**

---

## 5. Gate 1: Is the Dependency Deterministic?

### 5.1 Code trace

**[DRE]** The dependency is traced through three files:

1. **`controlplane/registry/orders.py:60-70`** — When `row is None` (no order found for `order_id`):
   ```python
   return Evidence(
       claim_id=claim.id,
       value=None,
       source="orders.db",
       confidence=Confidence.NONE,
       note=f"no order found for order_id={order_id!r}",
   )
   ```

2. **`controlplane/decide.py:151-158`** — When `ev.confidence == Confidence.NONE`:
   ```python
   return ClaimVerification(
       claim=claim,
       status=VerificationStatus.UNAVAILABLE,
       reason="authoritative_lookup_empty",
   )
   ```

3. **`manifests/servicing.yaml:45-75`** — Four of seven `claim_bindings` use `resolver: orders` with `subject: action.order_id`:
   - `ORDER_BELONGS_TO_CUSTOMER`
   - `AMOUNT_NOT_EXCEEDING_ORDER`
   - `WITHIN_REFUND_WINDOW`
   - `ORDER_ATTRIBUTES_MATCH`

   Three do NOT: `AMOUNT_WITHIN_AUTHORITY` (resolver: `authority`), `POLICY_CLAUSE_CURRENT` (resolver: `policy`), `CLAUSE_SEMANTICS_MATCH` (resolver: `policy`).

### 5.2 Verdict

**[DRE] Gate 1: PASS.**  The dependency is deterministic.  When `action.order_id` does not resolve to a row in `orders.db`, exactly 4 of 7 claims are assigned `UNAVAILABLE` with `reason: authoritative_lookup_empty`.  This is a static code-level guarantee (type A), not a runtime observation.  Confirmed empirically on `gs-129/130/133/134`.

### 5.3 Scope of the dependency

**[DRE]** The dependency is scoped to **one resolver × one subject**.  It does NOT gate:
- Claims on other resolvers (`authority`, `policy`).
- Claims using a different subject (none exist in the current manifest, but the binding is `subject: action.order_id`, not a global).
- Any claim that does not require a row lookup in `orders.db`.

This is narrower than "the action cannot proceed" — it is "4 specific claims cannot be evaluated."  The remaining 3 claims CAN still be evaluated (and are: `gs-129` shows `AMOUNT_WITHIN_AUTHORITY` as `VERIFIED`, `POLICY_CLAUSE_CURRENT` as `VERIFIED`, `CLAUSE_SEMANTICS_MATCH` as `UNVERIFIED` due to grounding being off).

---

## 6. Gate 2: Does the Annotation Expose Information Not Already Reconstructible from P1?

### 6.1 What P1 already outputs for gs-129

**[DRE]** The P1 verification ledger for `gs-129` contains (reconstructed from `decide.py` + `orders.py` code paths):

| Claim | Status | Reason |
|---|---|---|
| `ORDER_BELONGS_TO_CUSTOMER` | `UNAVAILABLE` | `authoritative_lookup_empty` |
| `AMOUNT_NOT_EXCEEDING_ORDER` | `UNAVAILABLE` | `authoritative_lookup_empty` |
| `WITHIN_REFUND_WINDOW` | `UNAVAILABLE` | `authoritative_lookup_empty` |
| `ORDER_ATTRIBUTES_MATCH` | `UNAVAILABLE` | `authoritative_lookup_empty` |
| `AMOUNT_WITHIN_AUTHORITY` | `VERIFIED` | (normal verification) |
| `POLICY_CLAUSE_CURRENT` | `VERIFIED` | (normal verification) |
| `CLAUSE_SEMANTICS_MATCH` | `UNVERIFIED` | (grounding off) |

Plus the evidence notes on each of the 4 UNAVAILABLE claims:
- `"no order found for order_id='OR-10283'"`

And the receipt (`receipt.py:50-71`):
- `verdict: SOURCE_UNRELIABLE`
- `root_cause: evidence_below_reliability_floor`
- `intervention: ESCALATE`

### 6.2 The backwards reconstruction test

**Can an auditor reconstruct the missing-record condition from P1 alone?**

**[AI] Yes.**  The auditor can:
1. Observe that 4 of 7 claims are `UNAVAILABLE`.
2. Read the `reason` field: all 4 say `authoritative_lookup_empty`.
3. Read the evidence `note` on any of them: `"no order found for order_id='OR-10283'"`.
4. Conclude: the order record did not resolve, and this is why these 4 claims are unavailable.

**Time cost:** 4 claim rows + cross-referencing the shared `order_id` + reading one note.  Not instant, but not requiring external knowledge.

**Information NOT present in P1:**
1. The **name** "order_record_resolves" — P1 has no concept of named preconditions.
2. The **grouping** — P1 does not say "these 4 claims share a single root cause."  The auditor must infer this from the identical `reason` and `note`.
3. The **correct root_cause label** — the receipt says `evidence_below_reliability_floor` (describing "bad data") when the truth is "absent record."

### 6.3 The root_cause mislabeling

**[DRE]** This is the strongest argument for the annotation.  `receipt.py:50-71` (`_root_cause()`) assigns `root_cause` by falling through a chain of conditions:

```python
if decision.unverifiable and not decision.source_unreliable:
    return "no_verifiable_evidence"
# ... (other conditions)
return "evidence_below_reliability_floor"  # fallback
```

For the missing-record case, `decide.py:311-329` sets BOTH `source_unreliable = True` (line 313, because `ev.reliability_class` < floor) AND `unverifiable = True` (line 325, because `ev.confidence == Confidence.NONE`).  The verdict precedence (`decide.py:400-409`) gives `SOURCE_UNRELIABLE` priority over `UNVERIFIABLE`.  Then `_root_cause()` falls through to `evidence_below_reliability_floor` — a label that describes "the evidence was obtained but was unreliable", not "the record does not exist."

**[AI] The label is factually wrong for the missing-record case.**  The evidence is not "below the reliability floor" — there IS no evidence because the record does not exist.  `Confidence.NONE` means "nothing was found," not "something unreliable was found."

**However:** Fixing this mislabel does NOT require a "precondition annotation."  It requires a corrected `_root_cause()` branch in `receipt.py` — e.g., checking `ev.confidence == Confidence.NONE` and returning `order_record_unresolved` (or similar) before the fallback.  This is a receipt bug fix, not a precondition layer.

### 6.4 Verdict

**[AI] Gate 2: MARGINAL PASS — the annotation adds two things, one of which (root_cause correction) is independently justified as a bug fix and does not require a precondition annotation layer.**

| What the annotation adds | Category | Requires annotation layer? |
|---|---|---|
| Named precondition ("order_record_resolves") | Convenience label | No — could be a comment or a structured field on the evidence |
| Causal grouping ("these 4 claims share one cause") | DIFFERENT LABEL — the 4 identical `reason` + `note` fields already imply it | No |
| Correct root_cause label | **NEW AUDIT VALUE** — changes what the receipt communicates | **No** — fixable in `_root_cause()` alone |

---

## 7. Gate 3: Does the Annotation Claim Stronger Causality Than Supported?

### 7.1 What the annotation would say

P3-E §28.3 proposes:

> "these N claims are `UNAVAILABLE` because precondition `order_record_resolves` was not satisfied"

### 7.2 What kind of "because" this is

**[AI]** The word "because" in the annotation claims **A (static dependency)**: the schema structure guarantees that if the order record doesn't resolve, these 4 claims cannot be evaluated.  This is supported by the code trace in §5.

**The annotation does NOT claim B (runtime causality).**  It does not say "the order lookup failed at 14:32:01 and this caused the customer_id check to fail at 14:32:02."  There is no timestamp-ordered causal chain.  `decide()` is a pure function that receives all evidence at once.

**The annotation does NOT need to claim B to be useful.**  A is sufficient: "by construction, these claims require a resolved order record, and none was found."

### 7.3 Risk of over-claiming

**[AI]** The phrasing "because precondition X was not satisfied" is accurate for type A if:
- "because" is understood as "given the code structure, it is impossible for these claims to be evaluated when X is not satisfied"
- NOT as "X's failure at runtime caused Y's failure at runtime"

**Risk:** An auditor unfamiliar with the A/B distinction might read runtime causality into the annotation.  This risk is mitigatable by phrasing: "precondition `order_record_resolves`: NOT_SATISFIED — claims dependent on `orders` resolver with subject `action.order_id` could not be evaluated" (describes the structural dependency without using the word "caused").

### 7.4 Verdict

**[AI] Gate 3: CONDITIONAL PASS.**  The annotation can be phrased to claim only static dependency (A), which the evidence supports.  It MUST NOT be phrased as runtime causality (B).  The phrasing in P3-E §28.3 is acceptable if "because" is understood structurally.

---

## 8. The gs-129 Walkthrough

**[DRE]** Full trace of `gs-129` through the pipeline:

```
INPUT
  case_id: gs-129
  order_id: OR-10283
  record_lookup_status: NO_MATCH (human_label_sample.csv)

ORDERS.PY (registry/orders.py:60-70)
  SELECT ... FROM orders WHERE order_id = 'OR-10283'
  row = None
  → Evidence(value=None, confidence=Confidence.NONE,
             note="no order found for order_id='OR-10283'")
  (returned for each of the 4 orders-resolver claims)

DECIDE.PY (_verify_one_claim, lines 151-158)
  ev.confidence == Confidence.NONE
  → ClaimVerification(status=UNAVAILABLE, reason="authoritative_lookup_empty")
  (for all 4 orders-resolver claims)

DECIDE.PY (decide, lines 311-329)
  source_unreliable = True  (ev.reliability_class < floor)
  unverifiable = True       (ev.confidence == NONE)

DECIDE.PY (verdict precedence, lines 400-409)
  SOURCE_UNRELIABLE wins over UNVERIFIABLE
  → verdict = SOURCE_UNRELIABLE

SERVICING.YAML (verdict_handling, line 35)
  SOURCE_UNRELIABLE: escalate
  → intervention = ESCALATE

RECEIPT.PY (_root_cause, lines 50-71)
  Falls through to: "evidence_below_reliability_floor"
  ← MISLABEL: should say "order record absent" or similar

P1 LEDGER
  coverage = 2/7 (VERIFIED: AMOUNT_WITHIN_AUTHORITY, POLICY_CLAUSE_CURRENT)
            (UNVERIFIED: CLAUSE_SEMANTICS_MATCH — grounding off)
            (UNAVAILABLE: 4 orders-resolver claims)
  coverage_value ≈ 28.6%
```

**What P1 shows the auditor:** 4 claims UNAVAILABLE, reason `authoritative_lookup_empty`, verdict `SOURCE_UNRELIABLE`, root_cause `evidence_below_reliability_floor`, intervention `ESCALATE`.

**What the proposed annotation would add:** "precondition `order_record_resolves`: NOT_SATISFIED (basis: deterministic execution dependency — `orders.db` lookup returned no row for `OR-10283`)."

**What the annotation would change vs P1 alone:**
1. Names the precondition → **convenience** (the auditor could infer this).
2. Groups the 4 claims as sharing a cause → **convenience** (the 4 identical reasons already imply this).
3. (If bundled with a root_cause fix) Corrects the receipt label → **new audit value** (but achievable without a precondition annotation).

---

## 9. Falsification Tests

The proposition is: "the annotation exposes a deterministic dependency not already reconstructible from P1."  The following tests attempt to falsify each clause.

### Tests on "deterministic dependency"

| # | Test | Result | Verdict |
|---|---|---|---|
| F1 | Can a missing record ever produce a non-UNAVAILABLE claim on the orders resolver? | No — `orders.py:60-70` always returns `Confidence.NONE`, `decide.py:151-158` always assigns `UNAVAILABLE`. | Dependency is deterministic |
| F2 | Can a present record ever produce an UNAVAILABLE claim on the orders resolver? | Only if the field is NULL (`orders.py:72-82`) — a different precondition (`order_record_fields_complete`), not `order_record_resolves`. | Dependency is correctly scoped |
| F3 | Does the dependency hold for non-orders-resolver claims? | No — `AMOUNT_WITHIN_AUTHORITY` (authority resolver) is `VERIFIED` even in gs-129. | Dependency is correctly bounded |
| F4 | Is there a code path where `row is None` but the claim is NOT `UNAVAILABLE`? | No path exists in `orders.py` or `decide.py`. | Confirmed |
| F5 | Could a future code change break the determinism? | Yes — if `orders.py` were modified to return a default value on missing rows. But the annotation describes the current architecture, not a future one. | Accepted limitation |

### Tests on "not already reconstructible from P1"

| # | Test | Result | Verdict |
|---|---|---|---|
| F6 | Can an auditor determine from P1 alone that the order record is missing? | **Yes** — 4 claims UNAVAILABLE with `reason: authoritative_lookup_empty` + evidence note `"no order found for order_id=..."` | **The information IS reconstructible** |
| F7 | Can an auditor determine from P1 alone which claims share the same root cause? | **Yes, with effort** — the 4 identical reasons and notes imply a shared cause, but P1 doesn't state this explicitly | Reconstructible with inference |
| F8 | Can an auditor determine from the receipt alone (without the ledger) what happened? | **Partially** — `verdict: SOURCE_UNRELIABLE`, `root_cause: evidence_below_reliability_floor` — **mislabeled**. The receipt alone leads to the wrong conclusion ("bad data" not "absent record"). | **Receipt alone is misleading** |
| F9 | Would the annotation change the auditor's conclusion? | Only if the auditor reads ONLY the receipt and not the ledger. If they read the ledger, the evidence notes already reveal the truth. | Conditional |
| F10 | Is there any information in the proposed annotation that cannot be derived from P1 output + the code? | **No** — the annotation is a pre-computed inference from information already present. | The annotation is a convenience |

### Tests on "without claiming stronger causality"

| # | Test | Result | Verdict |
|---|---|---|---|
| F11 | Does the annotation claim runtime causality (type B)? | As phrased in P3-E §28.3 ("because"), it could be read as B. Rephrasing to "dependent on" avoids this. | Mitigatable |
| F12 | Does the annotation claim the precondition is the ONLY reason for UNAVAILABLE? | No — it says "these N claims are UNAVAILABLE because..." which correctly scopes to the named claims. | Acceptable |
| F13 | Could the same 4 claims be UNAVAILABLE for a DIFFERENT reason? | Yes — if `orders.db` is unreachable (SourceUnavailable), the same 4 claims would be UNAVAILABLE for a different reason. The annotation must distinguish "record absent" from "source unreachable." | The current runtime CANNOT distinguish these (`orders.py:56-58` translates OperationalError). |
| F14 | Does the annotation conflate VIOLATED with NOT_ESTABLISHED? | P3-E notes this ambiguity (gs-129: `VIOLATED` vs `alt_reading: NOT_ESTABLISHED`). The annotation as proposed does not take a position — it says "NOT_SATISFIED" which is neutral. | Acceptable |
| F15 | Does temporal co-occurrence constitute causal evidence? | No — `decide()` is a pure function. All claims are evaluated in the same call. There is no temporal sequence to establish B-type causality. Only A-type (structural) is available. | Correctly understood |

### Summary

**11 of 15 tests confirm the proposition's clauses.  4 tests (F6, F7, F10, F13) challenge it:**
- F6/F7/F10: The information IS reconstructible from P1.  The annotation is a convenience, not new information.
- F13: The annotation cannot distinguish "record absent" from "source unreachable" because the runtime can't either.

---

## 10. Negative Controls

| # | Control | Expected result | Actual result | Pass? |
|---|---|---|---|---|
| N1 | Does the annotation add value for gs-005 (record resolves, normal case)? | No — the precondition is satisfied, there is nothing to annotate beyond "SATISFIED." | Confirmed — annotation is trivial for normal cases. | ✓ |
| N2 | Does the annotation add value for a case where CLAUSE_SEMANTICS_MATCH is UNVERIFIED (grounding off)? | No — this is unrelated to order_record_resolves. | Confirmed — the precondition is orthogonal. | ✓ |
| N3 | Does the annotation add value for a case where AMOUNT_WITHIN_AUTHORITY is CONTRADICTED (amount exceeds ceiling)? | No — this is on the authority resolver, not orders. | Confirmed — correctly scoped. | ✓ |
| N4 | Would the annotation fire for tau2 cases? | No — tau2 has no claim_bindings that use the orders resolver in the same way. `independent_user_authentication` is a different precondition with no evidence channel. | Confirmed — not cross-tool applicable without separate analysis. | ✓ |
| N5 | Does the annotation change the intervention for gs-129? | No — `ESCALATE` is already the outcome via `verdict_handling`. | Confirmed — read-only, no behavioral change. | ✓ |

**All 5 negative controls pass.**

---

## 11. The "New Audit Value" vs "Different Label" Judgment

This is the critical question.  The task specification states:

> The burden of proof is: **NEW AUDIT VALUE** not: **DIFFERENT LABEL**.

### 11.1 What the annotation provides

| Component | P1 already provides | Annotation adds | Category |
|---|---|---|---|
| Named precondition (`order_record_resolves`) | No — P1 has no concept of preconditions | A name for an inferred concept | **Different label** — the concept is implicit in P1's evidence notes |
| Causal grouping ("4 claims share one cause") | No — P1 lists claims individually | Explicit grouping | **Different label** — the 4 identical reasons already imply grouping |
| Precondition status (`NOT_SATISFIED`) | No — P1 has `UNAVAILABLE` on individual claims | A precondition-level status | **Different label** — renames `UNAVAILABLE` at a higher abstraction |
| Corrected root_cause label | P1 receipt says `evidence_below_reliability_floor` | Would say `order_record_unresolved` or similar | **New audit value** — changes what the receipt communicates |
| Basis ("deterministic execution dependency") | No — P1 has no dependency vocabulary | A typed dependency relationship | **Marginal new value** — tells the auditor WHY the claims are unavailable at a structural level |

### 11.2 Judgment

**[AI] The annotation is predominantly a DIFFERENT LABEL for information already present in P1.**

The ONE component that constitutes NEW AUDIT VALUE — the corrected root_cause label — does NOT require a precondition annotation layer.  It requires a bug fix to `_root_cause()` in `receipt.py`: adding a branch for `ev.confidence == Confidence.NONE` cases.

The precondition annotation as a whole is a convenience layer that:
- Makes implicit information explicit (valuable for auditability but not new information).
- Pre-computes an inference the auditor could make (saves time but doesn't change conclusions — except via the root_cause correction which is separable).

---

## 12. What the Proposed Annotation Would Contain

**[AI]** Based on P3-E §28.3, the annotation would be a read-only field on the P1 verification ledger or decision receipt:

```
precondition_annotations:
  - precondition: order_record_resolves
    status: NOT_SATISFIED
    basis: deterministic_execution_dependency
    affected_claims:
      - ORDER_BELONGS_TO_CUSTOMER
      - AMOUNT_NOT_EXCEEDING_ORDER
      - WITHIN_REFUND_WINDOW
      - ORDER_ATTRIBUTES_MATCH
    note: "orders.db lookup returned no row for order_id='OR-10283'"
```

---

## 13. What the Proposed Annotation Would NOT Contain

**[AI]** Per P3-E §28 and task constraints:

- NOT a coverage percentage.
- NOT a verdict or intervention (read-only).
- NOT a runtime causal log (type B).
- NOT a weighted score, severity, or business-value assessment.
- NOT applicable to tau2 (no evidence channel).
- NOT a substitute for P1 verification coverage (orthogonal).

---

## 14. Currency Integrity: Preserved as Ordinary Claim

**[DRE]** P3-E §20 reclassified `currency_integrity` as `ORDINARY_CLAIM` (missing a `ClaimKind`).  The boundary test confirms: it has an `asserted_value` (tool-call `currency`), is evaluated by value comparison (against `orders.db.currency`), and is structurally identical to `ORDER_ATTRIBUTES_MATCH` and `ORDER_BELONGS_TO_CUSTOMER`.

**[REC]** P3-F preserves this classification unchanged.  `currency_integrity` is NOT a precondition and would NOT appear in a precondition annotation layer.  It is a modelling gap — an ordinary claim that needs a `ClaimKind` — not a different kind of thing.

---

## 15. tau2 Identity: Preserved as Runtime-Unassessable

**[DRE]** `independent_user_authentication` passes the foundational boundary test (not assertable, not value-compared, gates downstream claims, prerequisite for interpretation) but has NO evidence channel in the tau2 integration.  Its `determinability` is `NOT_ASSESSABLE`.

**[REC]** P3-F preserves this unchanged: `tau2 / independent_user_authentication = REQUIRED_BUT_UNREPRESENTABLE`.  It is conceptually representable but runtime-unassessable.  A precondition annotation for tau2 would say "NOT_ASSESSABLE" on every case — adding no information.

---

## 16. Cross-Tool Applicability

**[AI]** The proposed annotation is specific to `issue_refund`:
- **issue_refund:** `order_record_resolves` gates 4 of 7 claims via the `orders` resolver.  The annotation is meaningful here.
- **tau2_retail_order_action:** No assessable preconditions.  Annotation would be empty or `NOT_ASSESSABLE`.
- **send_document:** Not analyzed by P3-D/P3-E.  No candidate preconditions identified.

**A precondition annotation layer is tool-specific, not universal.**  Each tool would need its own precondition enumeration — and P3-E demonstrated that even for `issue_refund`, the enumeration is an open lower bound.

---

## 17. Silent-Pass Relationship

**[DRE]** P3-C and P3-E both confirm: 4 structural silent-pass gaps (gs-129/130/133/134), 0 realized.  For `issue_refund`, a missing record forces ≥4 of 7 claims to `UNAVAILABLE`, so P1 cannot reach the 80% threshold → silent-pass is structurally bounded.

**[AI]** The precondition annotation does NOT change the silent-pass count.  It would name the reason for the structural gap but the gap is already identified and bounded.  The annotation adds no safety-relevant information that P3-C/P3-E haven't already stated.

---

## 18. Implementation Surface Analysis

**[AI]** Two implementation options, ordered by complexity:

### Option 1: Fix `_root_cause()` only (minimal)

**What:** Add a branch in `receipt.py:_root_cause()` for the missing-record case:
```python
if decision.source_unreliable and any(
    cv.reason == "authoritative_lookup_empty"
    for cv in decision.verification_ledger.verifications
):
    return "order_record_unresolved"
```

**Scope:** 3-5 lines in `receipt.py`.  No new types, no schema changes, no new layer.
**Value:** Fixes the mislabeled root_cause — the ONE component that constitutes new audit value.
**Risk:** Low.  Does not introduce new abstractions.

### Option 2: Full precondition annotation layer (P3-E §28.3)

**What:** Add a `precondition_annotations` field to the verification ledger or receipt.  Requires:
- A `Precondition` type in `schema.py`.
- A `PreconditionStatus` enum.
- Logic in `decide.py` or a new module to evaluate preconditions.
- Binding preconditions to claim sets (which claims each precondition gates).

**Scope:** New type + enum in `schema.py`, new evaluation logic, new field on `VerificationLedger` or `Decision`.
**Value:** Names preconditions explicitly, groups affected claims, provides a structured annotation.
**Risk:** Medium.  Introduces a new abstraction whose population is an open lower bound (P3-E finding F4).  If the layer is present, future developers may be tempted to compute a coverage % over it — exactly what P3-E falsified.

---

## 19. Risk of Over-Claiming

**[AI]** The precondition annotation claims "these claims are UNAVAILABLE because precondition X was not satisfied."  Risks:

1. **Treating correlation as causation.**  The annotation is safe IF it claims static dependency (A).  If misread as runtime causality (B), it over-claims.
2. **Implying completeness.**  If the annotation lists `order_record_resolves` as the precondition for 4 claims, an auditor might assume it is the ONLY precondition.  But `order_record_fields_complete` (NULL fields) is also a precondition — and the runtime cannot distinguish them (`orders.py:60-82` returns `Confidence.NONE` for both).
3. **Anchoring on the annotation.**  If the precondition says "NOT_SATISFIED," an auditor might skip reading the underlying evidence notes — losing the detail of which specific `order_id` was looked up.

---

## 20. Risk of Under-Claiming (Leaving the Mislabeling)

**[AI]** If no action is taken, the receipt continues to say `root_cause: evidence_below_reliability_floor` for missing-record cases.  An auditor relying only on the receipt (without examining the ledger) would conclude:

- "The evidence source was unreliable" → leads to investigation of data quality.
- NOT: "The order record does not exist" → which leads to investigation of why the agent referenced a nonexistent order.

**These are different remediation paths.**  The mislabeling has a real (if bounded) cost: it points the auditor in the wrong direction.

---

## 21. Temporal Ordering Is Not Causal Evidence

**[DRE]** `decide()` (`decide.py:267-470`) is a **pure function**.  It receives pre-resolved evidence as input and evaluates all claims in a single pass.  There is no temporal sequence: all 7 claims are evaluated in the same function call, and the evidence is fetched before `decide()` is invoked.

**[AI]** This means:
- The precondition's failure does not "happen before" the claims' failure — they are determined simultaneously from the same input.
- The dependency is structural (code-level guarantee), not temporal (one event causing a later event).
- The annotation must be phrased as "these claims require a resolved record to evaluate" (structural), not "the record lookup failed, causing these claims to fail" (temporal/causal).

---

## 22. Decision Table

| # | Question | Answer | Evidence |
|---|---|---|---|
| Q1 | Is `order_record_resolves` a genuine precondition (not a claim)? | **Yes** | P3-E §7 boundary test: no asserted_value, not value-compared, not agent-attributable, gates 4 claims. |
| Q2 | Is the dependency between `order_record_resolves` and the 4 claims deterministic? | **Yes** | Code trace: `orders.py:60-70` → `decide.py:151-158`. No exceptions. |
| Q3 | Is the dependency observable at runtime? | **Partially** — observable via 4 UNAVAILABLE claims, but mislabeled in the receipt. | `receipt.py:50-71`: `root_cause = evidence_below_reliability_floor` (wrong for absent record). |
| Q4 | Does P1 already expose the missing-record condition? | **Yes** — in the ledger (4 UNAVAILABLE + reason + notes). **No** — in the receipt (mislabeled root_cause). | Ledger exposes it; receipt obscures it. |
| Q5 | Does the annotation add strictly unreconstructible information? | **No** — all information is present in P1 output and can be inferred. | F6, F7, F10. |
| Q6 | Does the annotation correct a mislabel? | **Yes** — the `root_cause` label is factually wrong. | `receipt.py:50-71`: missing record ≠ "evidence below reliability floor." |
| Q7 | Does the root_cause correction require a precondition annotation layer? | **No** — fixable in `_root_cause()` alone (§18 Option 1). | 3-5 lines in `receipt.py`. |
| Q8 | Is the annotation's causal claim supported by the evidence? | **Yes, if phrased as static dependency (A).** Not if phrased as runtime causality (B). | §3, §7. |
| Q9 | Can the annotation be gamed? | **Not directly** — it is per-case and read-only.  But if a coverage % is later computed over preconditions, P3-E's gaming tests apply. | P3-E §23: gaming tests A-F. |
| Q10 | Does the annotation risk inflating audit scope? | **Marginally** — it adds a new layer that auditors must review. But it is read-only and descriptive. | §19 risk 3. |
| Q11 | Is the annotation cross-tool applicable? | **Only with per-tool analysis.**  tau2 has no assessable preconditions. | §16. |
| Q12 | Does the annotation preserve P3-E boundaries? | **Yes** — `currency_integrity` remains ordinary claim, tau2 identity remains unassessable. | §14, §15. |
| Q13 | Is the implementation cost proportional to the audit value? | **Option 1 (root_cause fix): yes.**  Option 2 (full layer): **disproportionate** given that the information is reconstructible. | §18. |

---

## 23. Evidence Summary

### Evidence FOR the annotation

1. **[DRE]** The `root_cause` label is factually wrong — `evidence_below_reliability_floor` misdescribes the missing-record condition.
2. **[DRE]** The receipt alone (without the ledger) leads to the wrong conclusion about the failure mode.
3. **[DRE]** The dependency is genuine and deterministic — code-traced through 3 files.
4. **[AI]** Naming the precondition makes the ledger more self-documenting for auditors who don't read the code.
5. **[AI]** Grouping 4 UNAVAILABLE claims under a shared cause saves the auditor an inference step.

### Evidence AGAINST the annotation

1. **[DRE]** The information IS reconstructible from P1's ledger — 4 claims with identical reason and note.
2. **[AI]** The root_cause correction (the strongest value component) does NOT require a precondition layer.
3. **[AI]** The precondition population is an open lower bound (P3-E F4) — introducing a layer invites coverage % computation, which P3-E falsified.
4. **[AI]** The runtime cannot distinguish "record absent" from "source unreachable" (`orders.py:56-58` vs `orders.py:60-70` both produce `Confidence.NONE`) — the annotation would inherit this conflation.
5. **[AI]** The annotation is tool-specific (`issue_refund` only) and not generalizable without per-tool analysis.
6. **[DRE]** `decide()` is a pure function — there is no runtime causal chain to annotate, only a structural dependency.

---

## 24. Falsification Result

**The proposition — "A read-only causal-precondition annotation exposes a deterministic dependency that is not already reconstructible from P1, without claiming stronger causality than the evidence supports" — is PARTIALLY FALSIFIED.**

- ✅ "deterministic dependency" — **confirmed** (Gate 1 passes).
- ❌ "not already reconstructible from P1" — **falsified for the ledger, upheld for the receipt only** (Gate 2 marginal pass).  The ledger already contains the information.  Only the receipt's mislabeled `root_cause` is genuinely misleading — and that is fixable without a precondition layer.
- ✅ "without claiming stronger causality" — **confirmed, conditional on phrasing** (Gate 3 conditional pass).

---

## 25. Disposition

### Disposition Options

| Code | Meaning |
|---|---|
| A | Implement fully as P3-E §28.3 described |
| B | Implement with modifications (narrower scope) |
| C | Implement only the root_cause correction (no precondition layer) |
| D | Defer pending further evidence |
| E | Do not implement (insufficient new audit value) |
| F | Do not implement (annotation would over-claim) |

### Selected Disposition: **C — Implement only the root_cause correction**

**[REC] Rationale:**

1. The ONE component that constitutes genuinely NEW AUDIT VALUE is the corrected `root_cause` label.  This is a receipt bug fix (`receipt.py:_root_cause()`), not a precondition annotation layer.

2. The full precondition annotation (named precondition + causal grouping + status) is predominantly a DIFFERENT LABEL for information already present in P1's ledger.  It makes implicit information explicit — a legitimate auditability improvement — but does not meet the "new audit value" burden of proof.

3. Introducing a precondition layer creates infrastructure whose population is an open lower bound (P3-E finding F4).  This invites future coverage % computation — exactly the pattern P3-E falsified and `docs/retired-figures.md` documents five times.

4. The root_cause fix is:
   - **Small** (3-5 lines in `receipt.py`).
   - **Self-contained** (no new types, no schema changes).
   - **Independently valuable** (fixes a factually wrong label).
   - **Not gameable** (per-case, not aggregated).

5. If the full annotation layer is desired in the future, it should be preceded by:
   - A closed enumeration of preconditions per tool (currently an open lower bound).
   - Resolution of the VIOLATED/NOT_ESTABLISHED ambiguity (P3-E §18, gaming test D).
   - Runtime ability to distinguish "record absent" from "source unreachable" (currently conflated).

---

## 26. Recommendations

1. **Fix `_root_cause()` in `receipt.py`** to correctly label the missing-record case.  Suggested: return `order_record_unresolved` (or `authoritative_record_absent`) when evidence has `reason: authoritative_lookup_empty` or `confidence == Confidence.NONE` with a note indicating no record was found.  This is a separately-reviewable task, NOT a change made by P3-F.

2. **Do not build a precondition annotation layer at this time.**  The audit value is marginal (different label, not new information for ledger readers), and the infrastructure risk (inviting coverage % computation) is real.

3. **Do not rescue the falsified coverage percentage.**  P3-E's finding stands: no honest aggregate percentage can be reported over preconditions.

4. **Preserve all P3-E boundaries:**
   - `currency_integrity` = ordinary claim missing a ClaimKind.
   - `tau2::independent_user_authentication` = conceptually required, runtime-unassessable.
   - P06 stale-hash failure: untouched.

5. **If a precondition annotation is revisited in the future**, require:
   - A closed, independently enumerable precondition population.
   - Phrasing that claims static dependency (A), not runtime causality (B).
   - An explicit prohibition on computing coverage % over preconditions.

---

## 27. Limitations

- **L-READ-ONLY:** P3-F is a design gate.  Zero production files are modified.  The root_cause fix is a recommendation, not a change.
- **L-SINGLE-TOOL:** The analysis is grounded in `issue_refund`.  Generalization to other tools requires separate per-tool analysis.
- **L-PURE-FUNCTION:** The "causality" analysis is limited by `decide()` being a pure function — no runtime causal chain exists to annotate.  Only structural (type A) dependency is available.
- **L-CONFLATION:** The runtime conflates "record absent" and "source unreachable" (`orders.py:56-58` vs `60-70` → same `Confidence.NONE`).  The annotation would inherit this limitation.
- **L-OPEN-POPULATION:** The precondition population is an open lower bound.  P3-F does not claim to have identified all preconditions.
- **L-SINGLE-AUTHOR:** One analysis pass, cross-checked against P3-D and P3-E findings.  Not a multi-reviewer study.

---

## 28. Safety Verification

- **HEAD:** `5b82915bf3d5be089c046f99b2d1b6b9133a34f0` — verified unchanged.
- **Branch:** `p1-verification-coverage` — verified unchanged.
- **Tag:** `v1.0-round2` — verified pointing to same commit.
- **Production files modified:** zero.
- **Frozen artifacts modified:** zero.
- **P06 stale-hash failure:** untouched.
- **Only new file:** this document (`docs/causal-precondition-annotation-design-review.md`).

