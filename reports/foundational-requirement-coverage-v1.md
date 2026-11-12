# P3-E - foundational-requirement coverage: falsification of the P3-D architecture

Harness: `bench/foundational_requirement_coverage.py` (regenerate with `python bench/foundational_requirement_coverage.py --write`). Section numbers 1-30 match the task's required-report checklist.

Every line below is tagged: **[DRE]** direct repository evidence · **[BR]** benchmark result · **[AI]** architectural inference · **[REC]** recommendation.

## 0. Headline

- **[BR] A single foundational-requirement coverage percentage is INVALID for this evidence base.** No honest aggregate can be reported: every candidate foundational requirement is either `DETERMINABLE_BUT_DEGENERATE` or `NOT_ASSESSABLE`. Computed anyway it would read 86.7% (one requirement) or 92.9% (two) - and *that gap is the problem, not a result*.
- **[BR] R1 (decisive): the metric is degenerate.** `order_record_resolves` - the only assessable load-bearing foundational requirement with any variation - has a per-case state **bit-identical to the corpus column `record_lookup_status`** (yes). Any ratio over it equals `1 - 4/30` = 0.866667 by construction. `docs/retired-figures.md` item 2 retired exactly this identity-not-measurement pattern.
- **[BR] R2: `currency_integrity`** - P3-D's second example - is DORMANT on 30/30 cases and is ORDINARY_CLAIM-shaped by the boundary test, not foundational.
- **[REC] The claim/precondition boundary itself survives falsification.** `order_record_resolves` fails every test for being a claim. A separate, **descriptive-only** foundational-precondition layer (P3-D Option B) is supported - as a per-case named line and causal annotation, **not** as a coverage %.
- **[BR] Silent-pass unchanged: 4 structural, 0 realized** (`gs-129`, `gs-130`, `gs-133`, `gs-134`). Matches P3-C.

**Disposition: COMPLETE - ARCHITECTURE VALID (descriptive-only, as P3-D Option B) BUT SINGLE COVERAGE PERCENTAGE INVALID**

## 1. Scope

Falsification of the P3-D separate-foundational-layer recommendation and of a candidate foundational-requirement coverage percentage, over a frozen independently authored reference and the frozen 30-case P3-B issue_refund corpus. Deterministic; no model, no network.

- Frozen independent reference: `bench/foundational_requirement_reference_v1.jsonl` (sha256 `9a8f18b04726d6dd96f5634b2e9addc560b79f53a2312a1dae0dd433a49cadfa`), 6 candidate requirements.
- Per-case corpus: the 30 frozen P3-B `issue_refund` cases (`bench/human_label_sample.csv`).
- P3-B gold sha256 `79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d` - asserted untouched, never read as input.
- Frozen clock `2026-08-14`. No model, no network. Byte-identical output on repeat runs.
- Zero production files changed. `bench/extraction_gold_v1.jsonl` and the P3-C reports are not modified.

## 2. Research question

> Can foundational requirements be independently defined and measured as a distinct population without creating a misleading or manipulable coverage metric? And does measuring this population add information beyond P1 verification coverage?

**[BR] Answers:** the population can be *defined* and *listed*; it cannot be turned into a valid single percentage on this evidence base; and it adds information only as a *per-case causal annotation*, not as an aggregate number.

## 3. P3-D context

P3-D (`docs/foundational-requirements-architecture-review.md`) recommended **Option B** - a separate foundational-precondition layer, descriptive first - over **Option A** (a new `ClaimKind`). It did not implement the layer and **hedged on a metric**: its section 12 left the ratio form open, and section 23 states 'no metric is invented'. P3-E tests both the separate-layer claim (section 28 here) and the concrete candidate ratio the task asks about (task section 21).

**[DRE] P3-D internal inconsistency noted, non-material:** section 5 says `ClaimKind` has 15 members; section 8 and `controlplane/schema.py:153-178` say 12. The count is 12. This does not affect P3-D's argument or any number here.

## 4. Falsification methodology

1. Author an independent reference (section 5) and **freeze it by sha256 before any measurement** (task section 20).
2. Classify every candidate against a reproducible boundary test (sections 7-8).
3. Compute the per-case requirement/evidence states the frozen corpus can exercise (sections 11-12); a self-consistency guard re-derives them from the raw facts and aborts on drift.
4. Compute the candidate ratio, then attack it: add / remove / duplicate / status-flip / evidence-flip / drop-dependency (section 23).
5. Cross-check against P1 verification coverage (sections 21, 25) and the P3-C silent-pass result (section 22).
6. Report the metric as INVALID if it fails, and emit a per-requirement observability table instead (sections 10-11, 15).

## 5. Independent reference methodology

Authored **only** from: `docs/threat-model.md` threat ids; the refund/authority policy prose; the `ProposedAction` tool-argument schema; `docs/gold-set-annotation.md`; `bench/label.py` (an independent re-derivation of the refund rules that imports nothing from `controlplane.decide`/`predicates`/`ladder`/`ground`); `bench/human_label_sample.csv`; `bench/gold_set.jsonl` tool-call args; and `data/orders.db` as a fixture cross-check. Authored **without** `build_claims`/`classify_claims` output, the P1 ledger, any receipt, `decide()` output, cached `_ClaimedFields`, existing verification coverage, or `bench/extraction_gold_v1.jsonl` `foundational_requirements[]`. P3-A `UNREPRESENTABLE_REQUIRED` and P3-B `foundational_requirements[]` were read only *after* classification, as a second-annotator cross-check (Appendix A).

## 6. Definition of a foundational requirement

A condition that (a) must hold before an action's claim-level verification is meaningful or possible, (b) is not an agent-attributable value-checkable assertion, (c) is evaluated on whether verification is possible rather than by comparing an asserted value to evidence, and (d) can make a set of downstream claims unevaluable at once. Operationally: a candidate is FOUNDATIONAL_REQUIREMENT only if the boundary_test answers are (agent_can_assert_value=false, evaluated_by_value_comparison=false, uses_normal_evidence_resolver=false, attributable_to_agent_assertion=false, gates_multiple_downstream_claims=true, prerequisite_for_interpreting_action=true). A candidate that can be asserted and is checked by value comparison is an ORDINARY_CLAIM missing a ClaimKind. A candidate that is a structural property of the tool call needing no evidence is an ACTION_VALIDITY_CHECK.

## 7. Claim vs precondition boundary test

| requirement | class | assert? | value-cmp? | resolver? | agent-attrib? | gates N claims | prerequisite? |
|---|---|:--:|:--:|:--:|:--:|--:|:--:|
| `order_record_resolves` (issue_refund) | FOUNDATIONAL_REQUIREMENT | no | no | no | no | 4 | yes |
| `currency_integrity` (issue_refund) | ORDINARY_CLAIM | yes | yes | yes | yes | 0 | no |
| `order_record_fields_complete` (issue_refund) | FOUNDATIONAL_REQUIREMENT | no | no | no | no | 4 | yes |
| `refund_amount_well_formed` (issue_refund) | ACTION_VALIDITY_CHECK | yes | no | no | yes | 0 | yes |
| `independent_user_authentication` (tau2_retail_order_action) | FOUNDATIONAL_REQUIREMENT | no | no | no | no | 2 | yes |
| `order_ownership_established` (tau2_retail_order_action) | UNCLEAR | yes | yes | yes | yes | 0 | yes |

**[BR] Only `order_record_resolves` and `order_record_fields_complete` pass every foundational test.** `currency_integrity` is asserted-and-value-compared (an ordinary claim missing a `ClaimKind`). `refund_amount_well_formed` needs no evidence and gates nothing (action validity). `independent_user_authentication` passes the test but has no evidence channel. `order_ownership_established` is a representable claim P3-A already counts as an unbound kind. **Four structurally different situations in a six-member candidate set.**

## 8. Action-validity boundary

**[DRE]** `bench/label.py`'s own precedence chain interleaves three categories before it reaches ordinary claims: missing record (foundational, -> `UNVERIFIABLE`) -> blank load-bearing field (foundational, -> `SOURCE_UNRELIABLE`) -> currency mismatch (value comparison / ordinary-claim-shaped, -> `SOURCE_UNRELIABLE`) -> non-positive amount (action validity, -> `SOURCE_UNRELIABLE`). **[AI]** They are **not** one homogeneous 'precondition layer' - the repo's own independent labeller distinguishes them by *verdict* and *order*, not by a separate status vocabulary. `refund_amount_well_formed` belongs in the existing Pydantic/enforcement path (threat T31), not a precondition layer. The action-validity boundary is real and does **not** sit inside the foundational set.

## 9. Requirement dependency analysis

**[BR]** `order_record_resolves` gates exactly **4 of 7** `issue_refund` claims - `ORDER_BELONGS_TO_CUSTOMER`, `AMOUNT_NOT_EXCEEDING_ORDER`, `WITHIN_REFUND_WINDOW`, `ORDER_ATTRIBUTES_MATCH` (the claims on the `orders` resolver with `subject: action.order_id`). It does **not** gate `AMOUNT_WITHIN_AUTHORITY` (`authority` resolver), `POLICY_CLAUSE_CURRENT` or `CLAUSE_SEMANTICS_MATCH` (`policy` resolver). Confirmed empirically: in `gs-129` exactly those 4 claims resolve `UNAVAILABLE`.

```
order_record_resolves
        |--> ORDER_BELONGS_TO_CUSTOMER
        |--> AMOUNT_NOT_EXCEEDING_ORDER      (one root failure, four UNAVAILABLE claims)
        |--> WITHIN_REFUND_WINDOW
        +--> ORDER_ATTRIBUTES_MATCH
```

**[BR]** The requirement is counted **once**, never once per gated claim. Gaming test F confirms dropping a downstream dependency does not change the count. This is why task section 22 forbids weighting a coverage number by downstream-claim count - it would double-count one root failure.

## 10. Requirement universe

| requirement | class | required | load-bearing | determinability | cases observed | state variation |
|---|---|:--:|:--:|---|--:|:--:|
| `order_record_resolves` | FOUNDATIONAL_REQUIREMENT | yes | yes | DETERMINABLE_BUT_DEGENERATE | 30 | yes |
| `currency_integrity` | ORDINARY_CLAIM | yes | yes | DETERMINABLE_BUT_DEGENERATE | 30 | yes |
| `order_record_fields_complete` | FOUNDATIONAL_REQUIREMENT | yes | yes | DETERMINABLE_BUT_DEGENERATE | 30 | yes |
| `refund_amount_well_formed` | ACTION_VALIDITY_CHECK | yes | yes | DETERMINABLE_BUT_DEGENERATE | 30 | no |
| `independent_user_authentication` | FOUNDATIONAL_REQUIREMENT | yes | yes | NOT_ASSESSABLE | 0 | no |
| `order_ownership_established` | UNCLEAR | yes | yes | NOT_ASSESSABLE | 0 | no |

**[BR][limitation L-ENUMERATION]** This is a **lower bound, not a closed population**. P3-A never enumerated `order_record_resolves` for any tool; P3-B found it for `issue_refund` only, by construction. Absence from this list is not proof of absence - so the denominator of any coverage ratio is undefined (task stop condition: 'the denominator is ill-defined').

## 11. Status-state analysis

| requirement | requirement_state distribution (over the 30 cases) |
|---|---|
| `order_record_resolves` | {'SATISFIED': 26, 'VIOLATED': 4} |
| `currency_integrity` | {'NOT_ESTABLISHED': 4, 'SATISFIED': 26} |
| `order_record_fields_complete` | {'NOT_APPLICABLE': 4, 'SATISFIED': 26} |
| `refund_amount_well_formed` | {'SATISFIED': 30} |

**[BR]** Four states are authored (`SATISFIED` / `VIOLATED` / `NOT_ESTABLISHED` / `NOT_APPLICABLE`). On the frozen corpus:

- **only `order_record_resolves` shows a load-bearing SATISFIED/VIOLATED split** (26 / 4).
- **the SATISFIED-vs-NOT_APPLICABLE and VIOLATED-vs-NOT_ESTABLISHED calls are judgement-laden.** P3-B marks the missing-record case `VIOLATED`; `bench/label.py` labels it `UNVERIFIABLE` and `docs/gold-set-annotation.md` frames `NO_MATCH` as 'we cannot check this' (i.e. `NOT_ESTABLISHED`). The frozen reference records `VIOLATED` with the alternative in `alt_reading`. Gaming test D shows the metric moves on this call - so this is not the objective status axis a coverage denominator needs.
- **is the P3-D four-state model sufficient?** For a *reference* it is adequate (it can express every situation the corpus and threat model raise). It is **not sufficient as a runtime enum** - see section 12.

## 12. Evidence-state analysis

| requirement | evidence_state distribution (over the 30 cases) |
|---|---|
| `order_record_resolves` | {'AVAILABLE': 26, 'UNAVAILABLE': 4} |
| `currency_integrity` | {'AVAILABLE': 26, 'UNAVAILABLE': 4} |
| `order_record_fields_complete` | {'AVAILABLE': 26, 'NOT_REQUIRED': 4} |
| `refund_amount_well_formed` | {'AVAILABLE': 30} |

**[BR]** Requirement-state and evidence-state are genuinely different dimensions (task section 14: *missing evidence != violated requirement*). But two repository facts limit how far the distinction can be pushed:

- **[DRE] the current runtime cannot represent either axis.** A missing row, a NULL load-bearing field, and an unreadable source all collapse to `Evidence(confidence=Confidence.NONE)` -> claim `UNAVAILABLE` -> verdict `SOURCE_UNRELIABLE`, `root_cause` `evidence_below_reliability_floor` (`controlplane/registry/orders.py:60-82`; `controlplane/decide.py:155-158, 311-329`; verified on `gs-129`). So `VIOLATED` vs `NOT_ESTABLISHED` is **not observable** in a receipt today.
- **[AI] for `order_record_resolves` the two axes partly collapse by definition** - the requirement *is* the statement 'authoritative evidence could be obtained'. Splitting status from evidence is artificial for exactly the requirement that most needs a separate layer.

## 13. Denominator analysis

**Candidate definition:** satisfied load-bearing foundational preconditions / required load-bearing foundational preconditions (NOT_APPLICABLE excluded from the denominator)

**[BR] The denominator is not a fixed population:**

- **not independently enumerable** (section 10): the candidate set is an open lower bound.
- **not stable under reasonable authoring choices**: including `order_record_fields_complete` (a genuine foundational requirement, always SATISFIED here) moves the ratio from 86.7% to 92.9% (gaming test A).
- **manipulable downward**: removing `order_record_resolves` - the one requirement that ever fails - makes the ratio read 100% / N/A (gaming test B).
- **degenerate at its core**:

```
requirement: issue_refund::order_record_resolves
per_case_state_is_bit_identical_to_record_lookup_status: True
n_cases: 30
n_record_unresolved: 4
candidate_coverage_equals_1_minus_slice_fraction: 0.866667
slice_fraction_is_a_corpus_construction_parameter: True
construction_parameter_source: bench/extraction_gold_v1.meta.json counts.by_difficulty_class.record_unresolved_escalate = 4
precedent: docs/retired-figures.md item 2 (order_id cross-validation): 'the detector recomputed that same boolean from the same fields ... an identity, not a measurement. The 75% baseline was 1 - P(wrong resolution) read straight off the generator's coin flips.'
verdict: DEGENERATE - the metric cannot fail for any reason not baked into how the 30 cases were sampled; it measures corpus composition, not ControlPlane.
```

**[BR] The P3-D section-12 alternative form** (`required preconditions with a KNOWN status / required preconditions` = 66.7%) is **also invalid**: also invalid - it measures how many requirements the reference author managed to assess (fixed by the authoring), not anything about ControlPlane. Same failure mode as the retired coverage_ratio (docs/retired-figures.md item 5).

## 14. Numerator analysis

**[BR]** The numerator (`SATISFIED` observations) inherits every denominator problem plus its own: the `SATISFIED` count is a recode of `record_lookup_status == FOUND` for the one requirement that varies, and is a constant 26 (or 30) for the requirements that do not. Gaming tests D and E show the numerator moves under a status re-reading that is *defensible*, not adversarial. There is no numerator that depends on ControlPlane's runtime behaviour - unlike P1's `verified` count, which can fall if a resolver breaks.

## 15. Aggregate results

**[BR] Verdict: INVALID. No aggregate foundational-requirement coverage percentage is reported.** N/A - zero requirements are non-degenerately assessable. Every FOUNDATIONAL_REQUIREMENT is either DETERMINABLE_BUT_DEGENERATE or NOT_ASSESSABLE, so there is no honest aggregate to report.

Reasons (full form):

- R1 DEGENERATE: the only assessable load-bearing foundational requirement with any variation (order_record_resolves) has a per-case state that is a 1:1 recode of one corpus construction parameter (record_lookup_status). The aggregate value equals 1 - (record-unresolved slice fraction) by construction and cannot fail for a reason not baked into corpus sampling. This is the pattern docs/retired-figures.md item 2 retired.
- R2 UNEXERCISABLE HEADLINE EXAMPLE: currency_integrity - the second requirement P3-D leans on - is DORMANT on 30/30 cases (every tool call and every orders.db row is INR) and is ORDINARY_CLAIM-shaped by the boundary test, not foundational.
- R3 NON-COMPARABLE ACROSS TOOLS: issue_refund has 1 assessable requirement; tau2 has 0 assessable; send_document has 0. '100% (1/1)' and 'N/A (0/0)' are not the same kind of quantity.
- R4 DENOMINATOR NOT INDEPENDENTLY ENUMERABLE: P3-A never listed order_record_resolves; P3-B found it for issue_refund only, by construction. The candidate set is an open lower bound, so the denominator is not a fixed population.
- R5 MANIPULABLE: gaming tests B (remove the failing requirement -> 100%/N/A) and D (VIOLATED -> SATISFIED -> 100%) both move the metric with no change to case safety, and D is a defensible re-reading rather than an adversarial edit.
- R6 CATEGORY INCOHERENT: the 6 candidates split across FOUNDATIONAL_REQUIREMENT (3, one of them NOT_ASSESSABLE), ORDINARY_CLAIM (1), ACTION_VALIDITY_CHECK (1), UNCLEAR (1). A single ratio would average over structurally different things.

**[REC] What is valid instead:** A deterministic per-requirement observability report (per_requirement_observability above) plus a per-case causal annotation on P1 unavailability (p1_x_foundational_matrix.per_case). Neither is a percentage. The per-requirement observability table (sections 10-12) and the per-case P1 x foundational table (section 16) are the aggregate artifacts. Task section 27 explicitly anticipates this outcome.

## 16. Per-case results (P1 x foundational)

| case | P1 cov | P1 v/e | P1 interv | order_record_resolves | evidence_state | P1 UNAVAILABLE claim kinds |
|---|--:|--:|---|---|---|---|
| `gs-005` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-009` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-011` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-016` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-027` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-031` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-035` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-040` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-045` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-052` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-056` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-059` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-067` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-088` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-093` | 57.1% | 4/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-111` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-129` | 28.6% | 2/7 | ESCALATE | VIOLATED | UNAVAILABLE | amount not exceeding order, order attributes match, order belongs to customer, within refund window |
| `gs-130` | 28.6% | 2/7 | ESCALATE | VIOLATED | UNAVAILABLE | amount not exceeding order, order attributes match, order belongs to customer, within refund window |
| `gs-133` | 28.6% | 2/7 | ESCALATE | VIOLATED | UNAVAILABLE | amount not exceeding order, order attributes match, order belongs to customer, within refund window |
| `gs-134` | 28.6% | 2/7 | ESCALATE | VIOLATED | UNAVAILABLE | amount not exceeding order, order attributes match, order belongs to customer, within refund window |
| `gs-141` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-142` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-143` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-144` | 85.7% | 6/7 | ALLOW | SATISFIED | AVAILABLE | - |
| `gs-145` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-146` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-147` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-148` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-149` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |
| `gs-150` | 71.4% | 5/7 | BLOCK | SATISFIED | AVAILABLE | - |

**[DRE]** P1 coverage never reaches 100% on this corpus - `CLAUSE_SEMANTICS_MATCH` (tier C3) is `UNVERIFIED` in all 30 cases because grounding (`CP_GROUNDING`) is off. The empty `P1=100` rows in section 25 are that, not a foundational-requirement fact.

## 17. issue_refund analysis

**[BR]** All 30 cases are `issue_refund`. 26 resolve a record (`order_record_resolves` SATISFIED), 4 do not (`gs-129/130/133/134`). `currency_integrity`, `order_record_fields_complete` and `refund_amount_well_formed` show **zero informative variation** on this corpus (respectively: no currency mismatch possible; no NULL fields in `data/orders.db`; every amount a positive integer). So the entire measurable foundational signal on the frozen corpus is **one bit per case, and that bit is `record_lookup_status`.**

## 18. Missing-record analysis (gs-129/130/133/134)

**[DRE]** `record_lookup_status = NO_MATCH`; `data/orders.db` confirms no row. **[BR]** `decide()` -> 4 claims `UNAVAILABLE` (`authoritative_lookup_empty`) -> `source_unreliable` AND `unverifiable` -> verdict `SOURCE_UNRELIABLE` -> `ESCALATE`. P1 coverage 2/7 (~28.6%). **[BR]** `bench/label.py` independently calls this `UNVERIFIABLE` / `ESCALATE` (recorded as `gold_verdict` in `gold_set.jsonl`).

**[AI]** So there is genuine disagreement on whether the precondition is `VIOLATED` (a determinate breach: the query ran and returned zero rows) or `NOT_ESTABLISHED` (we could not check). The task warns against automatically reading a missing record as `VIOLATED`. The frozen reference uses `VIOLATED` (the query *did* run; a determinate negative), with `NOT_ESTABLISHED` attached as `alt_reading`. Either way the downstream `evidence_state` is `UNAVAILABLE` and the intervention is `ESCALATE` - the disagreement changes the metric (gaming test D) but not the gate outcome.

## 19. tau2 analysis

**[DRE]** `independent_user_authentication` passes the foundational boundary test but has **no evidence channel** in the tau2 integration -> `NOT_ASSESSABLE`. `order_ownership_established` (tau2 `ORDER_BELONGS_TO_CUSTOMER`) is a **representable claim** that is merely **unbound**; P3-A `reports/manifest-claim-coverage.md` already counts it (tau2 manifests at 50%). **[REC]** Carry both forward unchanged: `tau2 / ORDER_BELONGS_TO_CUSTOMER = REQUIRED_BUT_UNREPRESENTABLE` (task sections 16, 34).

**[AI]** *Conceptually representable* != *runtime assessable* (task section 16). tau2's requirements are perfectly expressible in the reference; the tau2 *integration* has no channel to assess them. A tau2 foundational-coverage % is `N/A (0/0)` - and folding `order_ownership_established` in would double-count a gap P3-A already measures.

## 20. Currency-integrity analysis

**[BR]** Boundary test: `currency` is a structural `ProposedAction` field (assertable, `schema.py:230`), and `bench/label.py:183-189` checks it by **value comparison** to `data/orders.db.currency` - structurally identical to `ORDER_ATTRIBUTES_MATCH` (colour/category) and `ORDER_BELONGS_TO_CUSTOMER` (customer_id), both `ClaimKind`s. It gates no other claim; it is not a prerequisite for interpreting the action. **[REC] Classification: ORDINARY_CLAIM missing a `ClaimKind`, not a foundational requirement.**

**[BR]** On the frozen corpus it is DORMANT 30/30 (every tool call and every `data/orders.db` row is INR). `gold_set.jsonl` `gs-136..140` (currency `USD`, records resolve) *would* exercise it - `bench/label.py` labels those `SOURCE_UNRELIABLE` - but they are outside the frozen P3-B corpus. **[DRE]** P3-D section 21 already flags this reclassification as an open modelling decision; P3-E does not resolve it, only classifies the shape.

## 21. P1 comparison

**[BR]** For every case: P1 verification coverage, the `order_record_resolves` state, and the current intervention are in the section 16 table. Rolled up by the 2x2 of {P1 full / P1 partial} x {foundational SATISFIED / not}:

- **P1=100 & FR=SAT**: n=0 
- **P1<100 & FR=SAT**: n=26 (`gs-005`, `gs-009`, `gs-011`, `gs-016`, `gs-027`, `gs-031`, `gs-035`, `gs-040`, `gs-045`, `gs-052`, `gs-056`, `gs-059`, `gs-067`, `gs-088`, `gs-093`, `gs-111`, `gs-141`, `gs-142`, `gs-143`, `gs-144`, `gs-145`, `gs-146`, `gs-147`, `gs-148`, `gs-149`, `gs-150`)
- **P1=100 & FR!=SAT**: n=0 
- **P1<100 & FR!=SAT**: n=4 (`gs-129`, `gs-130`, `gs-133`, `gs-134`)

**[REC]** P1 is **not** the source of truth for foundational requirements; it is only a comparison. The one thing the foundational view adds on the 4 missing-record cases: it names the *single shared cause* of 4 of the 5 unverified claims.

## 22. Silent-pass relationship

- structural gap: **4** (`gs-129`, `gs-130`, `gs-133`, `gs-134`)
- realized opportunity: **0**
- matches P3-C: **yes**

**[BR]** MARGINALLY. P1's per-case ledger already shows 4 claims as UNAVAILABLE with reason 'authoritative_lookup_empty'. The foundational layer names the single shared cause ('order_record_resolves: VIOLATED') instead of leaving it as an inference from 4 rows plus a receipt verdict (SOURCE_UNRELIABLE) and root_cause (evidence_below_reliability_floor) that both point at 'bad data' rather than 'absent record'. That is a per-case audit-trail improvement, not a coverage metric, and it does not change the 0 realized count.

**[REC]** Not a realized safety failure. For `issue_refund` a missing record forces >=4 of 7 load-bearing claims to `UNAVAILABLE`, so P1 cannot reach the >=80% silent-pass threshold on this tool - the structural gap is bounded, the realized risk is low, exactly as P3-C and P3-D already state.

## 23. Metric-gaming tests

| test | action | before | after | metric moved | case safety changed? | finding |
|---|---|--:|--:|:--:|:--:|---|
| A_add_required_requirement | add issue_refund::order_record_fields_complete (SATISFIED on all 26 FOUND, NOT_APPLICABLE on 4) to a pool that was just {order_record_resolves} | 86.7% | 92.9% | yes | no | the aggregate % moves purely because the denominator grew with an always-satisfied check - denominator-sensitive. |
| B_remove_the_failing_requirement | drop issue_refund::order_record_resolves from the frozen pool | 92.9% | 100.0% | yes | no | removing the only requirement that is ever VIOLATED makes the metric read 100%/N/A - pure denominator manipulation, and nothing stops a manifest author doing it. |
| C_duplicate_a_requirement | append a second copy of issue_refund::order_record_resolves | 92.9% | 92.9% | no | no | the metric dedupes by requirement_id so the ratio is unchanged - counting-once works - but a naive implementation that counted per row would halve the score. |
| D_status_corruption | flip order_record_resolves gs-129/130/133/134 from VIOLATED to SATISFIED | 92.9% | 100.0% | yes | no | status corruption inflates the metric directly to 1.0; and because VIOLATED-vs-NOT_ESTABLISHED is itself a judgement call (P3-B says VIOLATED, bench/label.py implies NOT_ESTABLISHED), this is not even an adversarial edit - it is a defensible re-reading. |
| E_unavailable_evidence_relabelled_satisfied | reclassify currency_integrity as foundational (as P3-A/P3-B do), then flip its 4 NOT_ESTABLISHED to SATISFIED | 90.7% | 95.3% | yes | no | relabelling 'evidence unavailable' as 'requirement satisfied' inflates the metric; the two-axis model is supposed to prevent this but nothing enforces the axis separation. |
| F_drop_downstream_dependency | remove one ClaimKind from order_record_resolves.downstream_claims_gated (4 -> 3) | 92.9% | 92.9% | no | no | no change - the requirement is counted once regardless of how many claims it gates. Correct behaviour, and the reason task section 22 forbids weighting by downstream-claim count. |

**[BR]** Tests A, B, D, E move the metric with no change to case safety. B (remove the failing requirement) and D (a defensible `VIOLATED`->`NOT_ESTABLISHED`->`SATISFIED` re-reading) are the serious ones: the first is denominator manipulation nothing prevents, the second is not even an adversarial edit. C and F confirm counting-once is implemented correctly.

## 24. Cross-tool comparability

- **customer_servicing**: foundational=['issue_refund::order_record_resolves', 'issue_refund::order_record_fields_complete']; assessable=['issue_refund::order_record_resolves', 'issue_refund::order_record_fields_complete']; not_assessable=-; other=['issue_refund::currency_integrity (ORDINARY_CLAIM)', 'issue_refund::refund_amount_well_formed (ACTION_VALIDITY_CHECK)']
- **tau2_retail_order_action**: foundational=['tau2_retail_order_action::independent_user_authentication']; assessable=-; not_assessable=['tau2_retail_order_action::independent_user_authentication']; other=['tau2_retail_order_action::order_ownership_established (UNCLEAR)']

**[DRE]** bench/extraction_reference.py UNREPRESENTABLE_REQUIRED has NO entry for send_document; P3-D section 16 confirms its two required kinds are both bound and representable. A foundational-coverage % for send_document is 0/0 = N/A.

**[BR]** issue_refund has 1 assessable load-bearing foundational requirement; the tau2 family has 0 assessable (1 NOT_ASSESSABLE + 1 already-counted-by-P3-A binding gap); send_document has none. A percentage of '100% (1/1)' for issue_refund and 'N/A (0/0)' for tau2 and send_document are not comparable quantities - they do not answer the same question and cannot be ranked. No severity, business-value, or downstream-claim weighting is applied (task section 22).

## 25. P1 x foundational interpretation matrix

- **P1=100 & FR=SAT** - the modelled load-bearing claim set was fully verified AND the record precondition held. NOT demonstrated: unmodelled claims (P3-A), assertion-value accuracy, record correctness, C3 semantics.
- **P1<100 & FR=SAT** - some modelled claims were not verified for a reason unrelated to the record precondition (here: C3 CLAUSE_SEMANTICS_MATCH is UNVERIFIED with grounding off, or a genuine contradiction on a window/authority claim). The foundational layer adds nothing on these cases.
- **P1=100 & FR!=SAT** - did not occur in this corpus and CANNOT for issue_refund: a missing record forces >=4 of 7 load-bearing claims to UNAVAILABLE, so P1 cannot reach 100%. This is why the P3-C silent-pass count is 0 realized.
- **P1<100 & FR!=SAT** - the 4 missing-record cases. P1 is ~29% AND the record precondition failed. The foundational line explains WHY 4 of the 5 unverified claims are unverified - a per-case causal annotation, not a coverage number.

**[REC]** Neither number is 'overall safety', a correctness guarantee, a risk guarantee, or a probability of correctness. No combined score is computed (task section 26).

## 26. Limitations

- L-ENUMERATION: the candidate set is a lower bound. P3-A never enumerated order_record_resolves for any tool; P3-B found it for issue_refund only, by construction. Absence of a foundational requirement from this list does not prove none exists.
- L-ONE-TOOL-EXERCISED: only issue_refund has a per-case corpus. currency_integrity, order_record_fields_complete and refund_amount_well_formed are all DEGENERATE on that corpus (no variation, or a 1:1 recode of one construction parameter). tau2 requirements are NOT_ASSESSABLE.
- L-DEGENERATE-STATUS: order_record_resolves per-case state is a deterministic function of one corpus construction parameter (record_lookup_status); see docs/retired-figures.md item 2 for the precedent this matches.
- L-STATUS-JUDGEMENT: whether a missing record is VIOLATED or NOT_ESTABLISHED is a judgement call (P3-B says VIOLATED; bench/label.py + docs/gold-set-annotation.md imply NOT_ESTABLISHED / UNVERIFIABLE). The frozen reference records VIOLATED with the alternative attached in alt_reading.
- L-RUNTIME-COLLAPSE: the current runtime (decide.py, receipt.py, orders.py) cannot represent the requirement_state x evidence_state matrix; a missing row, a NULL field and an unreadable source all collapse to Confidence.NONE -> SOURCE_UNRELIABLE.
- L-P1-CROSSCHECK: the P1 numbers come from `bench.baselines` `action_from_case` (deterministic `claimed_*` reconstruction, 'extraction noise = 0'), not the LLM extractor - the same basis P3-C uses.
- L-NO-RUNTIME-CHANGE: this benchmark does not and must not change `decide()`, the ledger, or any receipt; the runtime's inability to represent the two-axis model is reported, not fixed.
- L-SINGLE-AUTHOR: one classification pass with a boundary test, cross-checked against P3-A/P3-B after the fact (Appendix A). Not a multi-annotator study of the classifications themselves.

## 27. Falsification findings

| # | finding | outcome |
|---|---|:--:|
| F1 | the candidate coverage % is a 1:1 recode of one corpus construction parameter (`record_lookup_status`) | **supported** |
| F2 | P3-D's second example (`currency_integrity`) is unexercisable on the corpus and ordinary-claim-shaped | **supported** |
| F3 | the candidate category is incoherent - 4 structural situations across 6 members | **supported** |
| F4 | the denominator is not independently enumerable to completeness | **supported** |
| F5 | the metric is manipulable via denominator (test B) and via a defensible status re-reading (test D) | **supported** |
| F6 | the metric is not comparable across tools | **supported** |
| F7 | `order_record_resolves` is genuinely NOT a claim (P3-D's core boundary claim) | **confirmed - survives falsification** |
| F8 | a separate descriptive precondition *layer* is justified; a single coverage *percentage* is not | **supported** |

## 28. Recommendation

**[REC]**

1. **Keep the claim/precondition distinction P3-D drew.** `order_record_resolves` is not a claim; naming it as a distinct per-case precondition line is a real auditability gain over inferring it from 4 `UNAVAILABLE` claims plus a verdict (`SOURCE_UNRELIABLE`) and `root_cause` (`evidence_below_reliability_floor`) that both point at 'bad data' rather than 'absent record'.
2. **Do not build a foundational-requirement coverage percentage.** It is degenerate, denominator- and status-manipulable, non-comparable across tools, and its population is an open lower bound. This is the trap `docs/retired-figures.md` documents five times ('a benchmark that cannot fail is worth less than no benchmark').
3. **If anything ships, ship a per-case causal annotation** on the existing P1 ledger / receipt: 'these N claims are `UNAVAILABLE` because precondition `order_record_resolves` was not satisfied', plus a corrected `root_cause` (e.g. `order_record_unresolved`). Descriptive, unweighted, per-case, cannot be gamed by adding or removing list entries. This is a design recommendation, not a change made here.
4. **Reclassify `currency_integrity`** out of the foundational set - it is an ordinary claim awaiting a `ClaimKind` (a modelling decision, carried forward, not resolved here).
5. **Keep tau2 identity as `REQUIRED_BUT_UNREPRESENTABLE`**, measured by P3-A's kind-coverage, not double-counted here.

## 29. Whether production implementation is justified

**[REC] Partially.** A read-only, descriptive per-case precondition annotation (recommendation 3) is justified as an observability improvement and matches the P1 discipline (descriptive first, no verdict feedback). A `FoundationalRequirement` production type *with its own coverage denominator* is **not** justified by this evidence: the denominator cannot be made honest. No production code is changed by P3-E; the recommendation is for a future, separately-reviewed task.

## 30. Exact reproduction command

```
python bench/foundational_requirement_coverage.py --write
```

`--check` verifies the committed report/JSON are byte-identical to a fresh run. The benchmark re-hashes the frozen reference and the P3-B gold on every run and aborts on drift.

## Appendix A. Second-annotator cross-check (P3-A / P3-B, read after classification)

- `note`: P3-A UNREPRESENTABLE_REQUIRED and P3-B foundational_requirements[] were read only AFTER classification.
- `P3A_lists_order_record_resolves`: False
- `P3B_order_record_resolves_status_rule`: SATISFIED if record_lookup_status==FOUND else VIOLATED (extraction_gold_build.py:672-692) - agrees case-for-case with the frozen reference
- `P3B_currency_integrity`: DORMANT for all 30 - agrees the check is unexercised; P3-E additionally reclassifies it ORDINARY_CLAIM
- `P3E_agreement_with_P3B_on_order_record_resolves_per_case`: True

## Appendix B. Carried-forward decisions (unchanged by P3-E)

- approve_discount / AMOUNT_NOT_EXCEEDING_ORDER = NEEDS_HUMAN_DECISION
- tau2 / ORDER_BELONGS_TO_CUSTOMER = REQUIRED_BUT_UNREPRESENTABLE
- refund day-7 inclusion = AMBIGUOUS
- gs-145..150 post-window disposition = BLOCK|ESCALATE unresolved

