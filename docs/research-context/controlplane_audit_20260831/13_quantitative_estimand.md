# L. Quantitative / estimand audit

Every numeric claim in the repository, with its numerator, denominator, and what random quantity (if any) it estimates. Labels: **MEASURED** / **DERIVED** (computed analytically by this audit from the generator source) / **REPORTED** (asserted by the repo) / **INFERRED**.

---

## L.1 "100% verdict accuracy with the R3 `attributes_match` check, 75% without"
*Source: `README.md`, Honest limitations; `c653b7f` commit message. Label: **DERIVED** (this audit) / **REPORTED** (the repo).*

| Element | Value |
|---|---|
| Numerator | cases where mapped verdict == `case["gold_verdict"]` |
| Denominator | **all 200 generated cases** |
| Inclusion | all; no exclusions |
| Treatment | presence of the `ORDER_ATTRIBUTES_MATCH` claim + its evidence + its predicate key |
| Comparator | the same 200 cases without it |
| Estimator | proportion |
| Uncertainty | **none reported, and none is meaningful** |
| Pairing | paired (same case objects both arms) — but see below |
| Independence | cases are i.i.d. draws from the generator; **the two arms are not independent measurements, they are two evaluations of one deterministic function** |
| Unit of analysis | one synthetic case |

**"Percentage of WHAT?"** — of all generated cases, only ~25% of which can discriminate between the arms. The 75% figure is therefore `1 − (density of discriminating cases)`, i.e. **a property of the generator's two `rng.random() < 0.5` draws**, tunable to any value between 0% and 100% by editing line 178. `bench/seb1_exp3_cross_validation.py`'s own docstring calls the density a tuning knob ("Tune to ~50% distractor density … and report the density" — `docs/ROADMAP.md:890`).

**"Compared against WHAT population under WHAT protocol?"** — against itself, under a protocol where the treatment's input and the outcome's label are the same Boolean.

**Verdict: NOT A PERFORMANCE MEASUREMENT.** Report it as: *"an integration check confirming the attribute predicate reaches BLOCK; the accuracy figures are properties of the generator and are not reported as performance."*

---

## L.2 Exp 5 confusion matrix, accuracy, precision, recall, cost-weighted error
*Label: **DERIVED**.*

| Element | Value |
|---|---|
| Numerator | diagonal count |
| Denominator | 200 (4 classes × 50) |
| Treatment | none |
| Estimator | proportion; per-class one-vs-rest precision/recall |
| Uncertainty | none reported |
| Unit | one synthetic decision |

Accuracy = **1.000** identically. Precision = recall = 1.000 for all four classes; FP = FN = 0 by construction.

Cost-weighted block: `false_allow_total_paise = 0` and `false_block_review_count = 0`, because there are no off-diagonal entries. **The cost model is correct, clearly labelled as assumed (`ASSUMED_*` constants plus a `"note"` field carried into the output), and multiplies zero.** The labelling discipline here is exemplary and should be preserved when real labels arrive.

**Verdict: a unit test formatted as a confusion matrix.**

---

## L.3 Mutation score
*Label: **DERIVED**.* Numerator = mutants where `intervention is not ALLOW`; denominator = 200. Value = **1.000** for every seed (see `10_benchmark_construct_validity.md` §I.3 for the per-operator derivation).

`docs/invariants.md` already states the correct framing (Just & Ernst, FSE'14; "a rigorous lower bound and a regression signal, not a real-world catch rate"). **Keep it. Do not publish the number as a headline.**

---

## L.4 Bias probe: p-value and "MDE 0.17 at n=200, 80% power"
*Label: **REPORTED** by README; the null is **DERIVED** as structural.*

| Element | Value |
|---|---|
| Numerator | blocks per group, where `blocked = intervention in (BLOCK, ESCALATE)` |
| Denominator | group size (~100 each; not fixed — `rng.choice` yields a binomial split, so `n_a ≠ n_b` in general) |
| Estimand | difference in block rate between two groups **that differ in a variable `decide()` never receives** |
| Estimator | two-proportion z-test, normal approximation |
| Uncertainty | p-value + MDE at 80% power — good practice |
| Unit | one synthetic decision |

**"What random quantity does the interval represent?"** — sampling variation between two random partitions of one distribution. It is a valid RNG-independence check; it is not a bias estimate, because there is no channel through which bias could enter.

Two further notes: `blocked` conflates BLOCK and ESCALATE (different costs, per the project's own D49 reasoning); and the MDE formula assumes equal group sizes (`n_per_group = (n_a+n_b)/2`) while the actual split is random.

---

## L.5 Latency: "model load ~13.2s, then ~0.1–0.5s per scored call"
*Label: **REPORTED**, n=1, one machine, no environment recorded.*

`bench/report.py:41-43` hard-codes `MEASURED_GROUNDING_LOAD_MS = 13_209.0`, `MEASURED_GROUNDING_CALL_MS = 109.8`, `TYPICAL_PREDICATE_MS = 0.6`, and the promotion-cost chart is drawn entirely from them. The chart's own subtitle says *"n=1 per bar"* — honest — but this **directly contradicts** README's *"`make report` regenerates … never from hand-typed numbers"* (contradiction C-1).

`telemetry.py::latency_percentiles` computes real p50/p95/p99 from `decisions.jsonl` — but `decisions.jsonl` is **gitignored**, so no percentile is reproducible from the repository. `bench/report.py::_latency_report` correctly emits `None` for every stage when the file is absent.

**Verdict: no latency claim in this repository is currently defensible.** Any comparison to OAP's "median 53 ms (N=1,000)" or Aegis's "238 ms median" would be **NOT DIRECTLY COMPARABLE** and should not be attempted.

---

## L.6 Coverage ratio
*Label: **DERIVED** from `schema.py::Decision.coverage`.*

`coverage_ratio = (C1+C2+C3)/total_claims`; the separate `deterministically_checkable = C1+C2`. Note `bench/report.py::_coverage_report` computes `coverage_ratio_c1_c2 = (C1+C2)/claims_total` — **a different quantity under a similar name**. Two ratios, two definitions, one shared vocabulary. Fix the naming before either is published.

Because tiers are assigned by a static table (`ladder.py::_TIER`), for `issue_refund` the ratio is **fixed at 7/7 = 1.0** (C1×3, C2×3, C3×1) for every decision, and for `send_document` at 3/3 = 1.0. The "measurement" is a property of the table.

---

## L.7 Receipt size
*Label: **REPORTED**.* `tests/test_receipt.py` asserts `< 2048` bytes on a **1-claim, 1-evidence** decision. README concedes the real BLOCK receipt is **~3.8 KB** (7 claims, 7 evidence). The test therefore cannot fail on the case the claim is about. **The README's disclosure is honest; the test is a strawman.**

---

## L.8 "3/5 proposed a refund unprompted"
*Label: **REPORTED**, not reproducible.* Numerator 3, denominator 5, unit = one phrasing. The pass criterion (majority) is stated in advance in `docs/ROADMAP.md` S2 — **that is good pre-registration discipline**. But `scripts/gate_check.py:42` unpacks 3 values from a 4-tuple and raises `ValueError` as committed (`15_reproducibility.md` D-R1), so the transcript predates the current code and cannot be regenerated.

---

## L.9 Numbers the repository correctly refuses to report

Worth naming, because they are the reason to trust the rest:

- `telemetry.py::_extraction_accuracy_block` → `{"status": "not_measured"}`
- `telemetry.py::_promotion_cost_block` → `not_measured` when no grounding ran
- `bench/reviewer_console.py --auto-approve` — README: *"exists only to prove the console doesn't crash — it is explicitly NOT a measurement"*
- `bench/agreement.py` — refuses Cohen's κ until all 30 human labels exist
- `reports/noise_sweep.png` — README: *"is not a noise sweep"*, and the chart's own title says so
- `docs/ROADMAP.md:81` — a kill list of superseded figures (`+36 points`, `63.3%/99.2%`, `55.8%`, `8% on HARD`, `15× swing`, `DBNR 2–3%`, `97–98%`) and *"the fabricated Runlayer sentence"*

**This is the strongest research-integrity signal in the artifact.** Six places where a number could have been invented and was not. See `19_claim_positioning_corrections.md`.

---

## L.10 Summary

| Claim | Label | Defensible as stated? |
|---|---|---|
| 100% / 75% (Exp 3) | DERIVED | **NO** — tautology |
| Exp 5 accuracy / P / R | DERIVED | **NO** — tautology |
| Mutation score | DERIVED | **Only** as a regression signal |
| Bias null + MDE | DERIVED | **Only** as an independence check |
| Grounding 0.921 / 0.023 | REPORTED, n=1 | Weak; not reproducible from repo |
| Latency 13.2 s / 109.8 ms / 0.6 ms | REPORTED, n=1, hard-coded | **NO** |
| Coverage ratio | DERIVED | Trivially 1.0; two conflicting definitions |
| Receipt < 2 KB | REPORTED | **NO** — real value ~3.8 KB, disclosed |
| 3/5 gate condition | REPORTED | Not reproducible |
| 77.4% NLI SOTA | verified externally | **YES as a number**, but it bounds a model the project does not run |
| USPS 32.6% | verified externally | **YES** (163/500); wording "origin office" should be "post office" |
| USPS 2.45% | — | **PRIMARY SOURCE NOT VERIFIED** |
