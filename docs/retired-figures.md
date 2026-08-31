# Retired figures

An internal audit (`docs/experiment-audit.md`) found that four of the five
reported experiments were circular: their headline numbers were forced by
how the test inputs were built, not by anything the system does. None of
the four could produce a failing result. They are retired here.

**Public-release note:** this document records the methodological audit and
retirement decisions. Some corrective implementations and replacement
benchmark artifacts referenced below were developed later in an off-release
development state (source provenance: commit `b4ef009`, which is not an
ancestor of this public release, `6ec4261`) and are not part of this public
release. They are marked **OFF-RELEASE DEVELOPMENT HISTORY** below and are
not presented as publicly reproduced results.

This is evidence discipline, not an apology. A benchmark that cannot fail is
worth less than no benchmark — it trains a reviewer to distrust the numbers
that are real. Removing these makes the rest of the repo's measurements
more credible, not less.

Every retired figure is one the project generated about *itself*. The
external citations in the pitch (77.4% NLI SOTA, the 96%/25% LLM-judge
figures, the USPS OIG scan-error rates) are unaffected — they were never
ours to fabricate.

---

## 1. Confusion matrix — accuracy 1.000

| | |
|---|---|
| **Was** | 4×4 gold-vs-predicted matrix, accuracy 1.000, every off-diagonal 0, per-class precision and recall all 1.0 |
| **Appeared in** | `reports/confusion.md`, `reports/summary.json`, `README.md`, `bench/report.py` |
| **Why retired** | `bench/seb1_exp5_confusion_matrix.py` generated each "gold" case by calling `decide()` with arguments chosen to force a known verdict, then scored `decide()` on those same inputs. Label and prediction were the same function call. Accuracy was exactly 1.000 for every seed and every `n`. |
| **Replaced by** | Not replaced in this public release. **PUBLIC RELEASE STATE:** `bench/seb1_exp5_confusion_matrix.py` in `6ec4261` is unchanged — it runs to completion and still reproduces the circular result described above (`run()` does not raise `SystemExit` for a missing gold set; the only `SystemExit` in the file is an unrelated `dateparser` import guard). `reports/confusion.md` does not exist in this public release — the `reports/` directory is not part of this tree. **OFF-RELEASE DEVELOPMENT HISTORY:** a held-out gold set (`bench/gold_set.jsonl`, task P03) and a BLOCKED state for this experiment were developed later and are not part of this public release. |

## 2. order_id cross-validation — 100% with the check, 75% without

| | |
|---|---|
| **Was** | "100% verdict accuracy with the R3 `attributes_match` check on distractor cases, 75% without it" |
| **Appeared in** | `reports/summary.json`, `README.md` ("Exp 3's result is real and worth stating…") |
| **Why retired** | The gold label was *defined as* `resolves_to_distractor`, and the `attributes_match` predicate — the detector — recomputed that same boolean from the same fields. 100% agreement was an identity, not a measurement. The 75% baseline was `1 − P(wrong resolution)` read straight off the generator's coin flips. |
| **Replaced by** | Not replaced in this public release. **PUBLIC RELEASE STATE:** `bench/seb1_exp3_cross_validation.py` in `6ec4261` is unchanged from the circular version described above; `bench/exp3_ground_truth.jsonl` and `bench/exp3_checker.py` do not exist in this release, and `tests/test_seb1_experiments.py` asserts `accuracy_with_attributes_check == 1.0` rather than any ground-truth-file independence. **0.92 with the check / 0.755 without is an OFF-RELEASE DEVELOPMENT RESULT — not publicly reproducible from this release.** A ground-truth-file design (a checker-blind `bench/exp3_ground_truth.jsonl`, hidden same-colour/same-category/different-size distractors) was developed later; see `docs/experiment-audit.md` for detail. |

## 3. Mutation score — 1.000

| | |
|---|---|
| **Was** | Mutation score 1.000, all six operators at 1.000 |
| **Appeared in** | `reports/summary.json`, `README.md`, `docs/invariants.md` |
| **Why retired** | The six operators were derived from the six checks `decide()` already implements (`tests/test_mutation.py`'s own docstring: "one operator per `docs/invariants.md`'s table"). Every mutant corrupted a fact some check was already watching, so every mutant was caught. The score restated the unit tests. |
| **Replaced by** | Not replaced in this public release. **PUBLIC RELEASE STATE:** `controlplane/mutation.py` in `6ec4261` still defines exactly the same six operators described above; there is no specification-derived operator set, and `reports/` (including `reports/summary.json`) does not exist in this public release. **0.60 is an OFF-RELEASE DEVELOPMENT RESULT — not publicly reproducible from this release.** A specification-derived operator set (from the `issue_refund` tool JSON schema and `manifests/servicing.yaml`, including `currency`, negative amount, latency/escalation budgets, retention days, risk tier) was developed later; see `docs/experiment-audit.md` for detail. |

## 4. Bias probe — "no detectable difference"

| | |
|---|---|
| **Was** | "no detectable difference", p ≈ 0.62, minimum detectable effect 0.17 at n=200, 80% power |
| **Appeared in** | `reports/summary.json`, `README.md` ("…rather than a bare 'no bias found.'") |
| **Why retired** | `controlplane/bias_probe.py` drew a group label with `rng.choice(["A","B"])` and never passed it to `decide()`, which is a pure function of facts that exclude it. With no path by which the label could affect the outcome, "no detectable difference" was the only result the test could produce. It passed by construction, not by correctness. |
| **Replaced by** | Not deleted in this public release. **PUBLIC RELEASE STATE:** `controlplane/bias_probe.py` still exists in `6ec4261` with the same counterfactual-twin design described above (`group` still never reaches `decide()`); it was reworded to also report a minimum detectable effect (MDE) alongside the p-value, so the "no detectable difference" conclusion in this release is at least accompanied by a quantified bound. **OFF-RELEASE DEVELOPMENT HISTORY:** `tests/test_no_protected_attributes.py`, `docs/limitations.md`, and `bench/bias_proxy_probe.py` do not exist in this public release — the structural replacement described here was developed later and is not part of this release. |

## 5. Coverage ratio — 1.0

| | |
|---|---|
| **Was** | "C1+C2 coverage_ratio = 1.0", also surfaced per-decision as `telemetry.coverage.coverage_ratio` |
| **Appeared in** | `reports/coverage.md`, `reports/summary.json`, `controlplane/schema.py`, `controlplane/telemetry.py`, `bench/report.py` |
| **Why retired** | `ladder.py` maps every `ClaimKind` to a tier (enforced at import), and every claim a governed tool can emit is C1/C2/C3 — the only C5 kind, `CUSTOMER_INTENT`, is in no tool's claim list. So `(C1+C2+C3)/total` was deterministically 1.0. It restated a hardcoded claim list; it measured nothing about traffic. |
| **Replaced by** | Partially reflected in this public release. **PUBLIC RELEASE STATE:** `tests/test_ladder.py` exists in `6ec4261` and enforces "every `ClaimKind` is mapped to a tier" as an invariant. `coverage_ratio` has **not** been removed from `controlplane/schema.py` or `controlplane/telemetry.py` in this release — both still compute and surface it. Per-tier claim counts remain as descriptive telemetry alongside the ratio, not instead of it; full removal of the ratio from schema/telemetry/reports was completed later, off-release. |

---

## What was checked and left in place

| Figure | Status |
|---|---|
| Grounding scores 0.921 (accurate paraphrase) / 0.023 (fluent-but-wrong) | Real — measured against the downloaded HHEM-2.1-Open model, `tests/test_ground.py` |
| Grounding model load (cold start) + HHEM scored-call latency | **OFF-RELEASE DEVELOPMENT RESULT.** Measured in later off-release development (source provenance: `reports/latency.md` §E/§C/§G at commit `b4ef009`, not an ancestor of this public release) — cold start ≈ 9 s one-time, I/O-bound and variable; HHEM `ground` stage p50 161 ms over 1,050 scored calls. `reports/latency.md` does not exist in this public release; not publicly reproducible from `6ec4261`. |
| Per-stage latency p50/p95/p99/max in `reports/latency.md` | **OFF-RELEASE DEVELOPMENT RESULT.** Same provenance as above — 4 configurations × 1,050 gated calls each, unrounded percentiles in `summary.json['p09_latency']` at `b4ef009`. `reports/` (including `reports/latency.md` and `reports/summary.json`) is not part of this public release. |
| Decision receipt size: median 2,282 B, p95 3,763 B (n=120) | **OFF-RELEASE DEVELOPMENT RESULT.** Same provenance — generated through all three manifest pipelines, recorded in `reports/summary.json` at `b4ef009`. That artifact does not exist in this public release; the aggregate n=120 statistic is not publicly reproducible from `6ec4261`. |
| Logger 2 (extraction accuracy under noise) | Honest `not_measured` stub — unchanged |
| `reports/noise_sweep.png` | Not a noise sweep; titled honestly as Exp 3's comparison — unchanged |
