# Retired figures

An internal audit (`docs/experiment-audit.md`) found that four of the five
reported experiments were circular: their headline numbers were forced by
how the test inputs were built, not by anything the system does. None of
the four could produce a failing result. They are retired here.

**Release-state note:** the public baseline is `6ec4261` (`origin/main`). The
verified local release candidate is represented by the audited HEAD; it is not
public until integrated and pushed. Its ancestor `986b65e` contains the original
C/I/D reconciliation, `dce2e4c` contains the later recipient-authorization
correction, and `aac3bea`, the Step 6B endpoint and immediate engineering
parent, synchronizes the threat model. The candidate chain adds no benchmark or
research artifacts and does not rerun or validate any benchmark result listed
here. Corrective implementations and replacement artifacts from off-release
commit `b4ef009` are not ancestors of the baseline or candidate. They remain
historical/off-release evidence and are not presented as public or candidate
results below.

This is evidence discipline, not an apology. A benchmark that cannot fail is
worth less than no benchmark. Removing the figures prevents them from being
mistaken for independent evidence.

Every retired figure is one the project generated about *itself*. This record
does not audit or validate external citations from the pitch.

---

## 1. Confusion matrix — accuracy 1.000

| | |
|---|---|
| **Was** | 4×4 gold-vs-predicted matrix, accuracy 1.000, every off-diagonal 0, per-class precision and recall all 1.0 |
| **Appeared in** | `reports/confusion.md`, `reports/summary.json`, `README.md`, `bench/report.py` |
| **Why retired** | `bench/seb1_exp5_confusion_matrix.py` generated each "gold" case by calling `decide()` with arguments chosen to force a known verdict, then scored `decide()` on those same inputs. Label and prediction were the same function call. Accuracy was exactly 1.000 for every seed and every `n`. |
| **Replaced by** | Not replaced in the public baseline or verified candidate. `bench/seb1_exp5_confusion_matrix.py` remains unchanged and runs to completion, reproducing the circular result above; it does not raise `SystemExit` for a missing gold set. No `reports/` directory is committed. **OFF-RELEASE DEVELOPMENT HISTORY:** a held-out `bench/gold_set.jsonl` and a later BLOCKED state were developed at `b4ef009`; neither is part of the baseline or candidate. |

## 2. order_id cross-validation — 100% with the check, 75% without

| | |
|---|---|
| **Was** | "100% verdict accuracy with the R3 `attributes_match` check on distractor cases, 75% without it" |
| **Appeared in** | `reports/summary.json`, `README.md` ("Exp 3's result is real and worth stating…") |
| **Why retired** | The gold label was *defined as* `resolves_to_distractor`, and the `attributes_match` predicate — the detector — recomputed that same boolean from the same fields. 100% agreement was an identity, not a measurement. The 75% baseline was `1 − P(wrong resolution)` read straight off the generator's coin flips. |
| **Replaced by** | Not replaced in the public baseline or verified candidate. `bench/seb1_exp3_cross_validation.py` remains circular; neither `bench/exp3_ground_truth.jsonl` nor `bench/exp3_checker.py` exists, and `tests/test_seb1_experiments.py` asserts the circular 1.0 result rather than checker/ground-truth independence. **0.92 with the check / 0.755 without is an OFF-RELEASE DEVELOPMENT RESULT from `b4ef009`; it is not publicly reproducible and is not a candidate result.** The checker-blind ground-truth design and hidden distractors are described in `docs/experiment-audit.md`. |

## 3. Mutation score — 1.000

| | |
|---|---|
| **Was** | Mutation score 1.000, all six operators at 1.000 |
| **Appeared in** | `reports/summary.json`, `README.md`, `docs/invariants.md` |
| **Why retired** | The six operators were derived from the six checks `decide()` already implements (`tests/test_mutation.py`'s own docstring: "one operator per `docs/invariants.md`'s table"). Every mutant corrupted a fact some check was already watching, so every mutant was caught. The score restated the unit tests. |
| **Replaced by** | Not replaced in the public baseline or verified candidate. `controlplane/mutation.py` still contains the original six implementation-derived operators, and no `reports/summary.json` is committed. **0.60 (9 of 15 operators catchable) is an OFF-RELEASE DEVELOPMENT RESULT from `b4ef009`; it is not publicly reproducible and is not a candidate result.** The specification-derived operator design is described in `docs/experiment-audit.md`. |

## 4. Bias probe — "no detectable difference"

| | |
|---|---|
| **Was** | "no detectable difference", p ≈ 0.62, minimum detectable effect 0.17 at n=200, 80% power |
| **Appeared in** | `reports/summary.json`, `README.md` ("…rather than a bare 'no bias found.'") |
| **Why retired** | `controlplane/bias_probe.py` drew a group label with `rng.choice(["A","B"])` and never passed it to `decide()`, which is a pure function of facts that exclude it. With no path by which the label could affect the outcome, "no detectable difference" was the only result the test could produce. It passed by construction, not by correctness. |
| **Replaced by** | Not replaced in the public baseline or verified candidate. `controlplane/bias_probe.py` still exists with the counterfactual-twin design above; rewording it to include an MDE does not create a causal path from `group` to `decide()`. **OFF-RELEASE DEVELOPMENT HISTORY:** deletion in favor of `tests/test_no_protected_attributes.py`, `docs/limitations.md` and `bench/bias_proxy_probe.py` was developed at `b4ef009`; none of those paths exists here. |

## 5. Coverage ratio — 1.0

| | |
|---|---|
| **Was** | "C1+C2 coverage_ratio = 1.0", also surfaced per-decision as `telemetry.coverage.coverage_ratio` |
| **Appeared in** | `reports/coverage.md`, `reports/summary.json`, `controlplane/schema.py`, `controlplane/telemetry.py`, `bench/report.py` |
| **Why retired** | `ladder.py` maps every `ClaimKind` to a tier (enforced at import), and every claim a governed tool can emit is C1/C2/C3 — the only C5 kind, `CUSTOMER_INTENT`, is in no tool's claim list. So `(C1+C2+C3)/total` was deterministically 1.0. It restated a hardcoded claim list; it measured nothing about traffic. |
| **Replaced by** | Partially reflected in the public baseline and candidate. `tests/test_ladder.py` enforces "every `ClaimKind` is mapped to a tier" as an invariant, and per-tier counts remain. The ratio itself has **not** been removed: `controlplane/schema.py` and `controlplane/telemetry.py` still compute and surface it. Full removal occurred only in off-release development. |

---

## Other reported figures and release status

| Figure | Status |
|---|---|
| Grounding scores 0.921 (accurate paraphrase) / 0.023 (fluent-but-wrong) | **HISTORICAL LOCAL OBSERVATIONS.** The public baseline and candidate include the optional HHEM integration and qualitative threshold tests, but `tests/test_ground.py` does not assert these exact values and no committed measurement artifact records them. They were not rerun for the candidate and are not external validation. |
| Grounding model load (cold start) + HHEM scored-call latency | **OFF-RELEASE DEVELOPMENT RESULT.** P09 at `b4ef009` reported cold start ≈ 9 s and HHEM `ground` p50 161 ms over 1,050 calls. Its `reports/latency.md` is absent from the public baseline and candidate, so the result is not publicly reproducible from either tree. |
| Per-stage latency p50/p95/p99/max in `reports/latency.md` | **OFF-RELEASE DEVELOPMENT RESULT.** P09 at `b4ef009` used 4 configurations × 1,050 gated calls and stored aggregate percentiles in `reports/summary.json`. Neither report exists in the public baseline or candidate. |
| Decision receipt size: median 2,282 B, p95 3,763 B (n=120) | **OFF-RELEASE DEVELOPMENT RESULT.** The aggregate was recorded in `reports/summary.json` at `b4ef009`; that artifact is absent from the public baseline and candidate. It is not a current public or candidate measurement. |
| Logger 2 (extraction accuracy under noise) | Honest `not_measured` stub — unchanged |
| `reports/noise_sweep.png` | Not committed in the public baseline or candidate. If generated by the current report harness, it is the retired Exp 3 comparison, not a noise sweep or current result. |
