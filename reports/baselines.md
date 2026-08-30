# P04 — baseline table (B0–B5)

Gold set: **150 cases** (140 non-ambiguous, 10 ambiguous) from `bench/gold_set.jsonl` (P03), labels from `bench/label.py` — never `decide()`.

**Clustering.** the 50 gold-ALLOW cases sit on 5 real source orders and the 10 ambiguous cases on 7 (P03); every other slice is 1 case : 1 order. CIs resample public order-id clusters, not cases — the 50 ALLOW cases are NOT 50 independent orders. The public ids yield 101 source-order clusters overall. 101 source clusters overall; the `allow_in_window` slice is 5 clusters for 50 cases. Every confidence interval below resamples clusters.

**Extraction** is held at zero noise for every system (regex + the claim fields P03 recorded), so the table isolates *verification*.

## Hypothesis (written before the results)

> We expected B1 to perform well on simple window cases and B4 to match B5 wherever the load-bearing fact is present and current in the agent's context. We expected separation on distractor, stale-policy and missing-field slices.

## P03 audit and evaluation contract

- SHA-256: `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e`; one schema variant with 14 fields across all 150 cases.
- Gold labels: `ALLOW=50, AMBIGUOUS=10, BLOCK=75, ESCALATE=15`.
- Gold verdicts: `AMBIGUOUS=10, CONTRADICTED=75, SOURCE_UNRELIABLE=5, UNVERIFIABLE=10, VERIFIED=50`.
- Every B0-B5 run consumes that same in-memory case list; no baseline reads construction truth and no gold label is changed.
- B5 tuning: **none**. Manifest thresholds were not selected or changed using the P03 gold set.

## B0-B5 architecture

| system | implementation | evidence available |
|---|---|---|
| B0 NoGate | unconditional execute | none |
| B1 RuleOnly | direct delivery-date read plus hardcoded `days > 7` rule | order delivery date only |
| B2 AuthOnly | servicing identity/role plus static amount ceiling | session and action arguments only |
| B3 LLMJudge | one cached `Qwen/Qwen3-8B` policy-judge call | agent-retrieved policy and trace |
| B4 TraceGrounded | shared full pipeline | agent trace/retrieved chunks |
| B5 ControlPlane | shared full pipeline | independent live registry queries |

### Structural control for B4/B5

Both registry entries call the single `_run_our_pipeline(case, strategy)` implementation. The only injected argument is `EvidenceStrategy`: `TraceGroundedStrategy` for B4 and `LiveQueryStrategy` for B5. An AST/source-structure test enforces this and separately proves that only B4 touches `retrieved_chunks` while only B5 calls `resolve_bindings`.

### Seeds

Evaluation-order seeds: `[0, 1, 2]`. Correctness is deterministic. B3 is one cached greedy (temperature-0) response per case; the three harness seeds are not misrepresented as three independent LLM generations. Per-seed latency is still reported.

## Headline — binary metrics on the 140 non-ambiguous cases

positive = gold says *do not auto-execute* (BLOCK ∪ ESCALATE, n=90); negative = gold ALLOW (n=50). a system *flags* if it predicts BLOCK / ESCALATE / MODIFY. FPR is on the 50 gold-ALLOW cases.

Each cell is mean [min, max] across three seeds.

| system | TP | FP | TN | FN | precision | recall | F1 | FPR (50 ALLOW) | ALLOW clusters with FP (of 5) | median lat (ms) | p95 lat (ms) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| B0_NoGate | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 50.0 [50.0, 50.0] | 90.0 [90.0, 90.0] | n/a | 0.0% [0.0%, 0.0%] | n/a | 0.0% [0.0%, 0.0%] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| B1_RuleOnly | 79.0 [79.0, 79.0] | 0.0 [0.0, 0.0] | 50.0 [50.0, 50.0] | 11.0 [11.0, 11.0] | 100.0% [100.0%, 100.0%] | 87.8% [87.8%, 87.8%] | 93.5% [93.5%, 93.5%] | 0.0% [0.0%, 0.0%] | 0.0 [0.0, 0.0] | 0.86 [0.53, 1.03] | 1.92 [1.70, 2.12] |
| B2_AuthOnly | 15.0 [15.0, 15.0] | 0.0 [0.0, 0.0] | 50.0 [50.0, 50.0] | 75.0 [75.0, 75.0] | 100.0% [100.0%, 100.0%] | 16.7% [16.7%, 16.7%] | 28.6% [28.6%, 28.6%] | 0.0% [0.0%, 0.0%] | 0.0 [0.0, 0.0] | 0.02 [0.02, 0.02] | 0.02 [0.02, 0.02] |
| B3_LLMJudge | 72.0 [72.0, 72.0] | 11.0 [11.0, 11.0] | 39.0 [39.0, 39.0] | 18.0 [18.0, 18.0] | 86.7% [86.7%, 86.7%] | 80.0% [80.0%, 80.0%] | 83.2% [83.2%, 83.2%] | 22.0% [22.0%, 22.0%] | 5.0 [5.0, 5.0] | 2786.25 [2786.25, 2786.25] | 7219.70 [7219.70, 7219.70] |
| B4_TraceGrounded | 73.0 [73.0, 73.0] | 0.0 [0.0, 0.0] | 50.0 [50.0, 50.0] | 17.0 [17.0, 17.0] | 100.0% [100.0%, 100.0%] | 81.1% [81.1%, 81.1%] | 89.6% [89.6%, 89.6%] | 0.0% [0.0%, 0.0%] | 0.0 [0.0, 0.0] | 23.50 [22.11, 24.40] | 28.53 [27.38, 29.37] |
| B5_ControlPlane | 90.0 [90.0, 90.0] | 0.0 [0.0, 0.0] | 50.0 [50.0, 50.0] | 0.0 [0.0, 0.0] | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] | 0.0% [0.0%, 0.0%] | 0.0 [0.0, 0.0] | 32.36 [32.04, 32.58] | 40.88 [37.87, 43.07] |

Correctness ranges are zero because the systems are deterministic; latency ranges reflect the three evaluation orders. The required FPR is the observed rate over 50 case variations; the adjacent column shows how many of their five source-order clusters contain any false positive.

## Per-seed results

| seed | system | TP | FP | TN | FN | precision | recall | F1 | FPR | FP clusters/5 | total error cost (paise) | median ms | p95 ms |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| 0 | B0_NoGate | 0 | 0 | 50 | 90 | n/a | 0.0% | n/a | 0.0% | 0 | 70718323 | 0.000 | 0.000 |
| 1 | B0_NoGate | 0 | 0 | 50 | 90 | n/a | 0.0% | n/a | 0.0% | 0 | 70718323 | 0.000 | 0.000 |
| 2 | B0_NoGate | 0 | 0 | 50 | 90 | n/a | 0.0% | n/a | 0.0% | 0 | 70718323 | 0.000 | 0.000 |
| 0 | B1_RuleOnly | 79 | 0 | 50 | 11 | 100.0% | 87.8% | 93.5% | 0.0% | 0 | 6486556 | 1.017 | 1.951 |
| 1 | B1_RuleOnly | 79 | 0 | 50 | 11 | 100.0% | 87.8% | 93.5% | 0.0% | 0 | 6486556 | 1.032 | 2.119 |
| 2 | B1_RuleOnly | 79 | 0 | 50 | 11 | 100.0% | 87.8% | 93.5% | 0.0% | 0 | 6486556 | 0.530 | 1.702 |
| 0 | B2_AuthOnly | 15 | 0 | 50 | 75 | 100.0% | 16.7% | 28.6% | 0.0% | 0 | 33203923 | 0.017 | 0.023 |
| 1 | B2_AuthOnly | 15 | 0 | 50 | 75 | 100.0% | 16.7% | 28.6% | 0.0% | 0 | 33203923 | 0.017 | 0.020 |
| 2 | B2_AuthOnly | 15 | 0 | 50 | 75 | 100.0% | 16.7% | 28.6% | 0.0% | 0 | 33203923 | 0.016 | 0.020 |
| 0 | B3_LLMJudge | 72 | 11 | 39 | 18 | 86.7% | 80.0% | 83.2% | 22.0% | 5 | 8859539 | 2786.250 | 7219.700 |
| 1 | B3_LLMJudge | 72 | 11 | 39 | 18 | 86.7% | 80.0% | 83.2% | 22.0% | 5 | 8859539 | 2786.250 | 7219.700 |
| 2 | B3_LLMJudge | 72 | 11 | 39 | 18 | 86.7% | 80.0% | 83.2% | 22.0% | 5 | 8859539 | 2786.250 | 7219.700 |
| 0 | B4_TraceGrounded | 73 | 0 | 50 | 17 | 100.0% | 81.1% | 89.6% | 0.0% | 0 | 7989539 | 23.982 | 28.829 |
| 1 | B4_TraceGrounded | 73 | 0 | 50 | 17 | 100.0% | 81.1% | 89.6% | 0.0% | 0 | 7989539 | 24.402 | 29.372 |
| 2 | B4_TraceGrounded | 73 | 0 | 50 | 17 | 100.0% | 81.1% | 89.6% | 0.0% | 0 | 7989539 | 22.107 | 27.377 |
| 0 | B5_ControlPlane | 90 | 0 | 50 | 0 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 32.479 | 37.870 |
| 1 | B5_ControlPlane | 90 | 0 | 50 | 0 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 32.035 | 41.715 |
| 2 | B5_ControlPlane | 90 | 0 | 50 | 0 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 32.576 | 43.066 |

## Cost-weighted error (140 non-ambiguous cases)

false ALLOW costs the refund amount; false BLOCK costs one review (INR 200). Values are mean [min, max] paise across seeds.

| system | false-ALLOW cost | false-BLOCK cost | total | mean/case |
|---|--:|--:|--:|--:|
| B0_NoGate | 70718323.0 [70718323.0, 70718323.0] | 0.0 [0.0, 0.0] | 70718323.0 [70718323.0, 70718323.0] | 505130.88 [505130.88, 505130.88] |
| B1_RuleOnly | 6486556.0 [6486556.0, 6486556.0] | 0.0 [0.0, 0.0] | 6486556.0 [6486556.0, 6486556.0] | 46332.54 [46332.54, 46332.54] |
| B2_AuthOnly | 33203923.0 [33203923.0, 33203923.0] | 0.0 [0.0, 0.0] | 33203923.0 [33203923.0, 33203923.0] | 237170.88 [237170.88, 237170.88] |
| B3_LLMJudge | 8639539.0 [8639539.0, 8639539.0] | 220000.0 [220000.0, 220000.0] | 8859539.0 [8859539.0, 8859539.0] | 63282.42 [63282.42, 63282.42] |
| B4_TraceGrounded | 7989539.0 [7989539.0, 7989539.0] | 0.0 [0.0, 0.0] | 7989539.0 [7989539.0, 7989539.0] | 57068.14 [57068.14, 57068.14] |
| B5_ControlPlane | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.0 [0.0, 0.0] | 0.00 [0.00, 0.00] |

## Exact intervention match vs the original P03 labels

scored against `gold_intervention` ∈ {ALLOW, BLOCK, ESCALATE} on the 140 non-ambiguous cases. B0–B3 **cannot emit ESCALATE**, so they miss all 15 ESCALATE-gold cases by construction — shown, not hidden.

| system | exact-match acc | ESCALATE-gold hit | can emit ESCALATE? |
|---|--:|--:|:--:|
| B0_NoGate | 35.7% [35.7%, 35.7%] | 0.0 [0.0, 0.0] / 15.0 [15.0, 15.0] | no |
| B1_RuleOnly | 88.6% [88.6%, 88.6%] | 0.0 [0.0, 0.0] / 15.0 [15.0, 15.0] | no |
| B2_AuthOnly | 46.4% [46.4%, 46.4%] | 0.0 [0.0, 0.0] / 15.0 [15.0, 15.0] | no |
| B3_LLMJudge | 68.6% [68.6%, 68.6%] | 0.0 [0.0, 0.0] / 15.0 [15.0, 15.0] | no |
| B4_TraceGrounded | 78.6% [78.6%, 78.6%] | 15.0 [15.0, 15.0] / 15.0 [15.0, 15.0] | yes |
| B5_ControlPlane | 96.4% [96.4%, 96.4%] | 10.0 [10.0, 10.0] / 15.0 [15.0, 15.0] | yes |

## AMBIGUOUS panel — 10 cases, kept entirely separate

These cases have no binary or direction-correct target and are not silently treated as ESCALATE. Only the prediction distribution is reported, as mean [min, max] counts across seeds.

| system | predictions | escalated |
|---|---|--:|
| B0_NoGate | ALLOW=10.0 [10.0, 10.0] | 0.0 [0.0, 0.0] |
| B1_RuleOnly | ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | 0.0 [0.0, 0.0] |
| B2_AuthOnly | ALLOW=10.0 [10.0, 10.0] | 0.0 [0.0, 0.0] |
| B3_LLMJudge | ALLOW=2.0 [2.0, 2.0], BLOCK=8.0 [8.0, 8.0] | 0.0 [0.0, 0.0] |
| B4_TraceGrounded | ALLOW=4.0 [4.0, 4.0], BLOCK=4.0 [4.0, 4.0], ESCALATE=2.0 [2.0, 2.0] | 2.0 [2.0, 2.0] |
| B5_ControlPlane | ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | 0.0 [0.0, 0.0] |

## Gold-verdict panel — the P03 verdict vocabulary, not remapped

the ESCALATE slice carries two distinct gold verdicts (`UNVERIFIABLE` ×10, `SOURCE_UNRELIABLE` ×5); AMBIGUOUS is its own verdict. shown here so neither is silently folded into BLOCK.

| system | AMBIGUOUS (n=10) | CONTRADICTED (n=75) | SOURCE_UNRELIABLE (n=5) | UNVERIFIABLE (n=10) | VERIFIED (n=50) |
|---|--:|--:|--:|--:|--:|
| B0_NoGate | ALLOW=10.0 [10.0, 10.0] | ALLOW=75.0 [75.0, 75.0] | ALLOW=5.0 [5.0, 5.0] | ALLOW=10.0 [10.0, 10.0] | ALLOW=50.0 [50.0, 50.0] |
| B1_RuleOnly | ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | ALLOW=1.0 [1.0, 1.0], BLOCK=74.0 [74.0, 74.0] | BLOCK=5.0 [5.0, 5.0] | ALLOW=10.0 [10.0, 10.0] | ALLOW=50.0 [50.0, 50.0] |
| B2_AuthOnly | ALLOW=10.0 [10.0, 10.0] | ALLOW=60.0 [60.0, 60.0], BLOCK=15.0 [15.0, 15.0] | ALLOW=5.0 [5.0, 5.0] | ALLOW=10.0 [10.0, 10.0] | ALLOW=50.0 [50.0, 50.0] |
| B3_LLMJudge | ALLOW=2.0 [2.0, 2.0], BLOCK=8.0 [8.0, 8.0] | ALLOW=18.0 [18.0, 18.0], BLOCK=57.0 [57.0, 57.0] | BLOCK=5.0 [5.0, 5.0] | BLOCK=10.0 [10.0, 10.0] | ALLOW=39.0 [39.0, 39.0], BLOCK=11.0 [11.0, 11.0] |
| B4_TraceGrounded | ALLOW=4.0 [4.0, 4.0], BLOCK=4.0 [4.0, 4.0], ESCALATE=2.0 [2.0, 2.0] | ALLOW=17.0 [17.0, 17.0], BLOCK=45.0 [45.0, 45.0], ESCALATE=13.0 [13.0, 13.0] | ESCALATE=5.0 [5.0, 5.0] | ESCALATE=10.0 [10.0, 10.0] | ALLOW=50.0 [50.0, 50.0] |
| B5_ControlPlane | ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | BLOCK=75.0 [75.0, 75.0] | BLOCK=5.0 [5.0, 5.0] | ESCALATE=10.0 [10.0, 10.0] | ALLOW=50.0 [50.0, 50.0] |

## Gold-set slice inventory

| slice | cases | source-order clusters | gold labels | gold verdicts |
|---|--:|--:|---|---|
| allow_in_window | 50 | 5 | ALLOW=50 | VERIFIED=50 |
| ambiguous_under_policy | 10 | 7 | AMBIGUOUS=10 | AMBIGUOUS=10 |
| corrupted_or_missing_record | 15 | 15 | ESCALATE=15 | SOURCE_UNRELIABLE=5, UNVERIFIABLE=10 |
| distractor_present | 20 | 20 | BLOCK=20 | CONTRADICTED=20 |
| outside_window | 20 | 20 | BLOCK=20 | CONTRADICTED=20 |
| over_authority | 15 | 15 | BLOCK=15 | CONTRADICTED=15 |
| stale_policy_context | 20 | 20 | BLOCK=20 | CONTRADICTED=20 |

## Per-slice results

Non-ambiguous cells show direction accuracy mean [min, max] and the mean [min, max] prediction counts. `ambiguous_under_policy` is explicitly unscored and shows distribution only.

| system | allow in window | ambiguous under policy | corrupted or missing record | distractor present | outside window | over authority | stale policy context |
|---|--:|--:|--:|--:|--:|--:|--:|
| B0_NoGate | 100.0% [100.0%, 100.0%]; ALLOW=50.0 [50.0, 50.0] | unscored; ALLOW=10.0 [10.0, 10.0] | 0.0% [0.0%, 0.0%]; ALLOW=15.0 [15.0, 15.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] | 0.0% [0.0%, 0.0%]; ALLOW=15.0 [15.0, 15.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] |
| B1_RuleOnly | 100.0% [100.0%, 100.0%]; ALLOW=50.0 [50.0, 50.0] | unscored; ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | 33.3% [33.3%, 33.3%]; ALLOW=10.0 [10.0, 10.0], BLOCK=5.0 [5.0, 5.0] | 95.0% [95.0%, 95.0%]; ALLOW=1.0 [1.0, 1.0], BLOCK=19.0 [19.0, 19.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] |
| B2_AuthOnly | 100.0% [100.0%, 100.0%]; ALLOW=50.0 [50.0, 50.0] | unscored; ALLOW=10.0 [10.0, 10.0] | 0.0% [0.0%, 0.0%]; ALLOW=15.0 [15.0, 15.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 0.0% [0.0%, 0.0%]; ALLOW=20.0 [20.0, 20.0] |
| B3_LLMJudge | 78.0% [78.0%, 78.0%]; ALLOW=39.0 [39.0, 39.0], BLOCK=11.0 [11.0, 11.0] | unscored; ALLOW=2.0 [2.0, 2.0], BLOCK=8.0 [8.0, 8.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 10.0% [10.0%, 10.0%]; ALLOW=18.0 [18.0, 18.0], BLOCK=2.0 [2.0, 2.0] |
| B4_TraceGrounded | 100.0% [100.0%, 100.0%]; ALLOW=50.0 [50.0, 50.0] | unscored; ALLOW=4.0 [4.0, 4.0], BLOCK=4.0 [4.0, 4.0], ESCALATE=2.0 [2.0, 2.0] | 100.0% [100.0%, 100.0%]; ESCALATE=15.0 [15.0, 15.0] | 95.0% [95.0%, 95.0%]; ALLOW=1.0 [1.0, 1.0], BLOCK=6.0 [6.0, 6.0], ESCALATE=13.0 [13.0, 13.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 20.0% [20.0%, 20.0%]; ALLOW=16.0 [16.0, 16.0], BLOCK=4.0 [4.0, 4.0] |
| B5_ControlPlane | 100.0% [100.0%, 100.0%]; ALLOW=50.0 [50.0, 50.0] | unscored; ALLOW=4.0 [4.0, 4.0], BLOCK=6.0 [6.0, 6.0] | 100.0% [100.0%, 100.0%]; BLOCK=5.0 [5.0, 5.0], ESCALATE=10.0 [10.0, 10.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] | 100.0% [100.0%, 100.0%]; BLOCK=15.0 [15.0, 15.0] | 100.0% [100.0%, 100.0%]; BLOCK=20.0 [20.0, 20.0] |

## B4 vs B5 — the critical pair (McNemar, paired)

B4 and B5 run the **identical pipeline**; the only difference is the evidence source (agent trace vs independent live query).

- paired cases: 140 (non-ambiguous)
- source-order clusters: 95; discordant source-order clusters: 17
- B5 correct & B4 wrong: **17**
- B4 correct & B5 wrong: **0**
- discordant pairs: 17
- McNemar exact two-sided p-value: **1.53e-05** (significant at α=0.05)
- accuracy: B4 87.9% · B5 100.0% · difference (B5−B4) 12.1%
- 95% CI on the difference (cluster bootstrap): [6.6%, 19.7%]
- CI method: 5,000-draw percentile bootstrap over public source-order clusters (seed 20260814).

Discordant cases:

| case | slice | B4 | B5 | gold |
|---|---|---|---|---|
| gs-054 | distractor_present | ALLOW | BLOCK | BLOCK |
| gs-071 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-072 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-073 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-074 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-075 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-076 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-077 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-078 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-079 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-080 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-081 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-082 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-083 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-084 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-085 | stale_policy_context | ALLOW | BLOCK | BLOCK |
| gs-086 | stale_policy_context | ALLOW | BLOCK | BLOCK |

## Deviations and limitations

- B3 was executed from all 150 committed fixtures. No fresh network call was made, so its prediction and latency values are the recorded calls, not newly sampled generations. Temperature was 0 and the provider seed was unavailable; this is why the report distinguishes evaluation-order seeds from independent LLM generations.
- B1 needs a delivery date although the public action contains only an order id. Its fair implementation performs one direct SQL field read, then applies only the hardcoded seven-day rule. It does not use extraction, Evidence, the registry abstraction, the ladder, attributes, authority, or policy-version checks.
- The P03 set is synthetic and single-domain. In particular, its 50 ALLOW cases represent five source orders, not 50 independent orders; cluster-aware resampling is used for the B4/B5 interval.
- B5 has a known exact-ontology gap on five currency-corruption cases: it blocks them for another live contradiction instead of emitting the gold SOURCE_UNRELIABLE/ESCALATE outcome. The binary direction is correct, but the exact-intervention panel exposes the mismatch.
- B5 received no threshold tuning or gold-set-driven changes.

## Did the hypothesis hold?

**B1 (rule-only) is the strong baseline the hypothesis predicted** — recall 87.8%, FPR 0.0%. Most orders in the seed DB are well outside the 7-day window, so a bare `days_elapsed > 7` rule blocks most of the right cases (often for the wrong reason). It is not a strawman and it is reported as a strong result. Where it falls short of B5 (100.0% recall): the corrupted/missing-record slice, where a rule engine with no record-reliability handling fails open (5/15 caught, and those only because the underlying order is also out of window), and one in-window distractor.

**B3 (LLM-as-judge) over-blocks.** Recall 80.0% looks reasonable, but FPR is 22.0% — it blocks 11 of the 50 valid refunds. Same model as the agent, one call, temperature 0. This is the project's own thesis showing up in its own baseline table: a model asked to check a model is not a reliable gate.

**B4 vs B5 (the critical pair): 17 discordant, p = 1.53e-05, significant; B5−B4 accuracy +12.1%, 95% CI [6.6%, 19.7%].** The hypothesis expected separation on distractor, stale-policy and missing-field. What actually happened: the separation is almost entirely **stale-policy** (16/17 discordant cases) plus one distractor. On stale-policy B4 grounds the refund window from the agent's retrieved (superseded) 30-day clause and ALLOWs; B5 queries the live 7-day clause and BLOCKs. On missing-field B4 and B5 agree (both ESCALATE — B4 because the date is absent from the trace, B5 because the record does not resolve), and on distractor B4 catches 19/20 anyway (via the window or a missing date, not via an attribute cross-check it structurally cannot do). So the hypothesis held for stale-policy, was weaker than expected for distractor, and did not hold for missing-field.

**Caveat on B5's currency-corruption cases (5 of the 15 ESCALATE-gold).** P03's `label.py` flags a tool-call currency that contradicts the order record as SOURCE-UNRELIABLE → ESCALATE. ControlPlane's `decide()` has no currency check, so B5 BLOCKs those 5 for a different reason (the underlying orders are also outside the window) — hence B5's exact-match is 96.4% and its ESCALATE-gold hit is 10/15. The two rule implementations agree on *direction* here only by luck of the data; the currency check is a real gap (tracked for P08).

