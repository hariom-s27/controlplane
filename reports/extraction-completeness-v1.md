# P3-C — extraction completeness: independent gold vs the actual extractor

Harness: `bench/extraction_completeness_bench.py` (regenerate with `python bench/extraction_completeness_bench.py --write`).

## 0. Headline

- **Claim-set recovery: 100.0% recall, 100.0% precision, 100.0% decomposition accuracy** over 210 independently-required gold claims. Zero missed, wrong-kind, wrong-subject, merged, split or spurious claims. The manifest-driven extractor recovers every representable required claim, with the right kind and subject, atomically decomposed.
- **Every case (30/30) has a load-bearing required check the extractor's `ClaimKind` vocabulary cannot represent** (`order_record_resolves`). This is an extraction-completeness gap that P1 verification coverage, by construction, cannot show: the check is never in the denominator.
- **Silent-pass: 4 structural gaps, 0 realized.** In the 4 missing-record cases (`gs-129/130/133/134`) the unrepresentable check is actually violated, but P1 reports ~29% coverage and ESCALATEs — the gap does not hide behind a high score on this corpus.
- **Assertion-value layer (LLM `extract_action`) is not exercised** — 0/30 offline fixtures. Only claim-set recovery and (via the P1 pipeline) assertion-outcome are measured.

## 1. Benchmark scope

Deterministic benchmark over the frozen 30-case P3-B corpus, not a population estimate. Independent gold vs the actual ControlPlane extraction layer.

- Cases: **30** proposed `issue_refund` actions (the frozen P3-B corpus).
- Gold claims in scope: **210** (30 x 7 ClaimKinds).
- Frozen clock: `2026-08-14`. Manifest: `manifests/servicing.yaml`.

## 2. Frozen gold SHA

`79b209523bfc806e3495ac321abdcf9af2764a9f369e8949c496dd9ea6c8c56d` — asserted equal to the P3-B pin and to `bench/extraction_gold_v1.meta.json`. The corpus is read-only here.

## 3. Extractor entry point

- **Claim-set layer (measured):** `controlplane.extract.build_claims(action, load_manifest('servicing'))` — `build_claims` emits one `Claim` per `claim_bindings` entry in the active manifest; `classify_claims` (ladder S5) fills tier + load-bearing. No reimplementation.
- **Assertion-value layer:** `controlplane.extract.extract_action (NOT exercised offline: 0/30 fixtures)`.
- **P1 cross-check:** `bench.baselines.LiveQueryStrategy -> controlplane.decide.decide()` (deterministic: local sqlite + frozen clock).

## 4. Normalization

- `claim_kind`: ClaimKind enum / .value / .name -> .name (UPPER_SNAKE); no cross-kind aliasing
- `subject`: strip; drop one leading 'clause:' token; collapse whitespace; casefold
- `alignment_key`: (normalized_claim_kind, normalized_subject)
- `beyond_key`: same-subject/other-kind -> WRONG_KIND; same-kind/other-subject -> WRONG_SUBJECT; >1 extracted per gold -> SPLIT; >1 gold per single extracted -> MERGED; extracted with no gold key -> SPURIOUS (claim_set_complete == true)

## 5. Alignment

Primary key `(normalized_claim_kind, normalized_subject)`. Beyond the key, the taxonomy is decided as: same-subject/other-kind -> WRONG_KIND; same-kind/other-subject -> WRONG_SUBJECT; >1 extracted per gold -> SPLIT; >1 gold per single extracted -> MERGED; extracted with no gold key -> SPURIOUS (claim_set_complete == true)

## 6. Metric definitions

- **claim_recall**: CORRECT / gold_claims_in_scope
- **claim_precision**: aligned_extracted_claims / comparable_extracted_claims  (aligned = comparable - spurious)
- **miss_rate**: missed_required_claims / required_gold_claims  (missed = MISSED_CLAIM + WRONG_KIND + WRONG_SUBJECT on a required gold claim)
- **spurious_rate**: SPURIOUS_CLAIM / comparable_extracted_claims
- **decomposition_accuracy**: correct_decomposition_units / decomposition_units  (unit = one gold claim; CORRECT counts, MERGED/SPLIT do not)
- **wrong_kind_rate**: WRONG_KIND / gold_claims_in_scope
- **wrong_subject_rate**: WRONG_SUBJECT / gold_claims_in_scope
- **unmodelled_required_rate_over_cases**: cases with >=1 load-bearing unmodelled foundational requirement / n_cases
- **assertion_outcome_agreement_rate**: outcome_agreed / scorable_claims  (scorable = 6 outcome-scorable kinds, non-AMBIGUOUS expected assertion)
- **silent_pass**: see silent_pass.definition; structural_gap vs realized_opportunity are reported separately

## 7. Aggregate metrics

| metric | value |
|---|---|
| claim recall | 100.0% (210/210) |
| claim precision | 100.0% (210/210) |
| miss rate (required) | 0.0% (0/210) |
| spurious rate | 0.0% (0/210) |
| decomposition accuracy | 100.0% (210/210) |
| wrong-kind rate | 0.0% (0/210) |
| wrong-subject rate | 0.0% (0/210) |
| merged cases | 0 |
| split cases | 0 |
| unmodelled-required rate (over cases) | 100.0% (30/30) |
| assertion-outcome agreement (scorable) | 83.0% (146/176) |

## 8. Per-case table

| case | class | gate | recall | missed req | unmodelled LB | P1 cov | P1 v/e | P1 interv | silent-pass |
|---|---|---|--:|--:|--:|--:|--:|---|:--:|
| `gs-005` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-009` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-011` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-016` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-027` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-031` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-035` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-040` | authority_boundary_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-045` | normal_allow | ALLOW | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-052` | window_expired_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-056` | window_expired_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-059` | window_expired_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-067` | window_expired_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-088` | stale_policy_version_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-093` | multi_violation_block | BLOCK | 7/7 | 0 | 1 | 57.1% | 4/7 | BLOCK | - |
| `gs-111` | window_expired_block | BLOCK | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-129` | record_unresolved_escalate | ESCALATE | 7/7 | 0 | 1 | 28.6% | 2/7 | ESCALATE | gap |
| `gs-130` | record_unresolved_escalate | ESCALATE | 7/7 | 0 | 1 | 28.6% | 2/7 | ESCALATE | gap |
| `gs-133` | record_unresolved_escalate | ESCALATE | 7/7 | 0 | 1 | 28.6% | 2/7 | ESCALATE | gap |
| `gs-134` | record_unresolved_escalate | ESCALATE | 7/7 | 0 | 1 | 28.6% | 2/7 | ESCALATE | gap |
| `gs-141` | window_boundary_ambiguous | AMBIGUOUS | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-142` | window_boundary_ambiguous | AMBIGUOUS | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-143` | window_boundary_ambiguous | AMBIGUOUS | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-144` | window_boundary_ambiguous | AMBIGUOUS | 7/7 | 0 | 1 | 85.7% | 6/7 | ALLOW | - |
| `gs-145` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-146` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-147` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-148` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-149` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |
| `gs-150` | supervisor_discretion_band | BLOCK\|ESCALATE | 7/7 | 0 | 1 | 71.4% | 5/7 | BLOCK | - |

## 9. Error taxonomy counts

| code | type | count |
|---|---|--:|
| A | CORRECT | 210 |
| B | MISSED_CLAIM | 0 |
| C | WRONG_KIND | 0 |
| D | WRONG_SUBJECT | 0 |
| E | UNMODELLED (load-bearing foundational req.) | 30 |
| F | MERGED_CLAIM | 0 |
| G | SPLIT_CLAIM | 0 |
| H | SPURIOUS_CLAIM | 0 |

## 10. Missed claims

None.

## 11. Spurious claims

None.

## 12. Wrong-kind claims

None.

## 13. Wrong-subject claims

None.

The P3-B `subject_note` on all 60 policy claims flags the specific trap: a WRONG_SUBJECT finding would arise if `build_claims` fell back to `action.order_id` for `POLICY_CLAUSE_CURRENT` / `CLAUSE_SEMANTICS_MATCH`. It does not — `manifest.policy_id` resolves to `refund_window`, which normalizes equal to gold's `clause:refund_window`.

## 14. Merged / split cases

Merged: 0. Split: 0.

`gs-093` (multi-violation) is the case that tests whether two independent load-bearing violations (`WITHIN_REFUND_WINDOW`, `AMOUNT_WITHIN_AUTHORITY`) are incorrectly merged. The extractor keeps them as two distinct claims with distinct kinds — no merge.

## 15. Unmodelled claims

every issue_refund case carries `order_record_resolves` (load-bearing) and `currency_integrity` (dormant) as foundational_requirements with representable_as_claimkind == false. No ClaimKind can carry them, so they are never in the extracted claim universe. This is distinct from a missed claim: the extractor cannot represent the requirement at all.

- Load-bearing unmodelled requirement instances: **30** (`order_record_resolves`, one per case).
- `currency_integrity` is also present in every case as an unmodelled requirement, marked DORMANT (not load-bearing here).

## 16. Silent-pass opportunities

a load-bearing required check absent from the extracted claim universe (an unmodelled foundational requirement that is actually VIOLATED) while P1 coverage >= 0.80 AND the intervention is permissive (ALLOW/MODIFY), so the omission could hide behind a high score. Extraction-completeness / observability condition, not a security verdict.

- Structural gap (load-bearing required check absent from the claim universe **and** actually VIOLATED): **4** cases — `gs-129`, `gs-130`, `gs-133`, `gs-134`.
- Realized opportunity (structural gap **and** P1 coverage >= 80% **and** permissive intervention): **0** cases — none.

Interpretation: in the missing-record cases the independently-required `order_record_resolves` check has no `ClaimKind` and never enters the P1 denominator. Whether that becomes a *hidden* pass depends on whether P1 still reports a high score on those cases. See the per-case table.

## 17. P1 coverage cross-check

ControlPlane verifies the claims it extracts; the question P3-C asks is whether the independently-required claim set is fully inside that extracted universe. Cases where P1 coverage is high but an independently-required check is missing are listed under silent_pass.realized_opportunity_case_ids.

| case | gold req | matched | missed req | LB unmodelled | P1 cov | P1 v/e | P1 interv |
|---|--:|--:|--:|--:|--:|--:|---|
| `gs-005` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-009` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-011` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-016` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-027` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-031` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-035` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-040` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-045` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-052` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-056` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-059` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-067` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-088` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-093` | 7 | 7 | 0 | 1 | 57.1% | 4/7 | BLOCK |
| `gs-111` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-129` | 7 | 7 | 0 | 1 | 28.6% | 2/7 | ESCALATE |
| `gs-130` | 7 | 7 | 0 | 1 | 28.6% | 2/7 | ESCALATE |
| `gs-133` | 7 | 7 | 0 | 1 | 28.6% | 2/7 | ESCALATE |
| `gs-134` | 7 | 7 | 0 | 1 | 28.6% | 2/7 | ESCALATE |
| `gs-141` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-142` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-143` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-144` | 7 | 7 | 0 | 1 | 85.7% | 6/7 | ALLOW |
| `gs-145` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-146` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-147` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-148` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-149` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |
| `gs-150` | 7 | 7 | 0 | 1 | 71.4% | 5/7 | BLOCK |

## 18. Assertion-outcome limitations

ORDER_ATTRIBUTES_MATCH (NOT_DETERMINABLE_FROM_CORPUS, L-ATTR) is excluded from scoring. AMBIGUOUS expected assertions (gs-141..144 WITHIN_REFUND_WINDOW) are preserved, never forced to HOLDS/VIOLATED — the ControlPlane status is reported but not scored. This is assertion-OUTCOME agreement, a different measurement from claim-set recovery and assertion-value recovery.

| ClaimKind | outcome agreement (scorable, non-AMBIGUOUS) |
|---|--:|
| AMOUNT_NOT_EXCEEDING_ORDER | 100.0% (30/30) |
| AMOUNT_WITHIN_AUTHORITY | 100.0% (30/30) |
| CLAUSE_SEMANTICS_MATCH | 0.0% (0/30) |
| ORDER_BELONGS_TO_CUSTOMER | 100.0% (30/30) |
| POLICY_CLAUSE_CURRENT | 100.0% (30/30) |
| WITHIN_REFUND_WINDOW | 100.0% (26/26) |

**Driver of <100%:** Every disagreement is CLAUSE_SEMANTICS_MATCH resolving to UNVERIFIED. That claim IS extracted (30/30) and IS verification-eligible (tier C3), but the P1 cross-check pipeline (bench.baselines LiveQueryStrategy) passes grounding_score=None -- the S8 grounding check is not wired on this path -- so the C3 outcome is never computed. This is a pipeline-path property of the cross-check, NOT a claim-set extraction defect.

- AMBIGUOUS claims preserved (not scored): **4** (`gs-141..144` WITHIN_REFUND_WINDOW).
- NOT_DETERMINABLE_FROM_CORPUS preserved (not scored): **26** (ORDER_ATTRIBUTES_MATCH, one per case).

Where ControlPlane's verification resolves an AMBIGUOUS claim to a definite status, that is reported here and is **not** counted as agreement or disagreement:

| case | ClaimKind | gold expected | ControlPlane verification status |
|---|---|---|---|
| `gs-141` | WITHIN_REFUND_WINDOW | AMBIGUOUS | verified |
| `gs-142` | WITHIN_REFUND_WINDOW | AMBIGUOUS | verified |
| `gs-143` | WITHIN_REFUND_WINDOW | AMBIGUOUS | verified |
| `gs-144` | WITHIN_REFUND_WINDOW | AMBIGUOUS | verified |

The day-7 boundary (`gs-141..144`): ControlPlane's `window_days: 7` is inclusive, so its verification resolves `WITHIN_REFUND_WINDOW` to `verified`. The independent gold holds the day-7 inclusion **AMBIGUOUS** (policy text `window_day_boundary: unresolved_by_text`). This benchmark preserves AMBIGUOUS and takes no position on the disposition.

## 19. Limitations

- Deterministic benchmark over 30 cases on ~22 orders (L-CLUSTER). No CI, no population inference.
- L-ONE-TOOL: issue_refund only. send_document / approve_discount / approve_service_credit / tau2 not exercised.
- Assertion-VALUE layer (LLM extract_action) NOT exercised: 0/30 offline fixtures. Only the structural asserted_value slots are observed.
- L-ATTR: ORDER_ATTRIBUTES_MATCH assertion outcome is not scorable (base sheet omits the resolved order's colour/category). Its claim-set recovery IS measured.
- The P1 cross-check drives the downstream verdict from bench.baselines.action_from_case (deterministic claimed_* reconstruction, 'extraction noise = 0'), not the LLM extractor.
- Human policy decisions carried forward unresolved: approve_discount/AMOUNT_NOT_EXCEEDING_ORDER (NEEDS_HUMAN_DECISION, N/A here); tau2 ORDER_BELONGS_TO_CUSTOMER (REQUIRED_BUT_UNREPRESENTABLE, N/A here); refund day-7 inclusion (AMBIGUOUS, preserved); gs-145..150 post-window disposition (BLOCK|ESCALATE, not resolved by this benchmark).

## 20. Exact reproduction command

```
python bench/extraction_completeness_bench.py --write
```

