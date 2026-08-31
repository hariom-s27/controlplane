# Retired figures

An internal audit (`docs/experiment-audit.md`) found that four of the five
reported experiments were circular: their headline numbers were forced by
how the test inputs were built, not by anything the system does. None of
the four could produce a failing result. They are retired here.

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
| **Replaced by** | Nothing yet in this release. **Correction:** `run()` does not raise `SystemExit` in this tree — it executes and returns a matrix, still circular as described above, because the change that would block it pending an independent gold set is itself **prepared off-release and not merged into this tree**. A held-out set whose labels are assigned independently of `decide()` (`bench/gold_set.jsonl`, task P03) would resolve this; it does not exist here. |

## 2. order_id cross-validation — 100% with the check, 75% without

| | |
|---|---|
| **Was** | "100% verdict accuracy with the R3 `attributes_match` check on distractor cases, 75% without it" |
| **Appeared in** | `reports/summary.json`, `README.md` ("Exp 3's result is real and worth stating…") |
| **Why retired** | The gold label was *defined as* `resolves_to_distractor`, and the `attributes_match` predicate — the detector — recomputed that same boolean from the same fields. 100% agreement was an identity, not a measurement. The 75% baseline was `1 − P(wrong resolution)` read straight off the generator's coin flips. |
| **Replaced by** | A non-circular design — construction-time ground truth in `bench/exp3_ground_truth.jsonl`, checked by `bench/exp3_checker.py` (which never opens that file), gold verdict `resolved_order_id != true_order_id`, and "hidden" distractors (same colour and category, different size) the check cannot see — has been **prepared off-release and is not merged into this tree**. In this release, `bench/seb1_exp3_cross_validation.py` is unchanged and remains circular as described above. The figures **0.92 with the check, 0.755 without** (CP_SEED=20260814, n=200) come from that off-release work — **not a current public result; not reproducible from this tree.** |

## 3. Mutation score — 1.000

| | |
|---|---|
| **Was** | Mutation score 1.000, all six operators at 1.000 |
| **Appeared in** | `reports/summary.json`, `README.md`, `docs/invariants.md` |
| **Why retired** | The six operators were derived from the six checks `decide()` already implements (`tests/test_mutation.py`'s own docstring: "one operator per `docs/invariants.md`'s table"). Every mutant corrupted a fact some check was already watching, so every mutant was caught. The score restated the unit tests. |
| **Replaced by** | A rewrite deriving operators from the **specification** — the `issue_refund` tool JSON schema and `manifests/servicing.yaml` — including elements the gate has no mechanism to enforce (`currency` enum, negative amount, latency/escalation budgets, retention days, risk tier) has been **prepared off-release and is not merged into this tree**. In this release, `controlplane/mutation.py` is unchanged: still the original six operators described above, still scoring 1.000 by construction. The figure **0.60** (9 of 15 operators catchable) comes from that off-release rewrite — **not a current public result; not reproducible from this tree.** |

## 4. Bias probe — "no detectable difference"

| | |
|---|---|
| **Was** | "no detectable difference", p ≈ 0.62, minimum detectable effect 0.17 at n=200, 80% power |
| **Appeared in** | `reports/summary.json`, `README.md` ("…rather than a bare 'no bias found.'") |
| **Why retired** | `controlplane/bias_probe.py` drew a group label with `rng.choice(["A","B"])` and never passed it to `decide()`, which is a pure function of facts that exclude it. With no path by which the label could affect the outcome, "no detectable difference" was the only result the test could produce. It passed by construction, not by correctness. |
| **Replaced by** | In this release, `controlplane/bias_probe.py` still exists, unchanged, and still passes by construction as described above. A replacement — deleting the probe in favour of `tests/test_no_protected_attributes.py` (a structural check that `decide()` and every type feeding it carry no protected-attribute field), `docs/limitations.md`, and a clearly-labelled proxy analysis `bench/bias_proxy_probe.py` — has been **prepared off-release and is not merged into this tree**; none of those three files exist here. |

## 5. Coverage ratio — 1.0

| | |
|---|---|
| **Was** | "C1+C2 coverage_ratio = 1.0", also surfaced per-decision as `telemetry.coverage.coverage_ratio` |
| **Appeared in** | `reports/coverage.md`, `reports/summary.json`, `controlplane/schema.py`, `controlplane/telemetry.py`, `bench/report.py` |
| **Why retired** | `ladder.py` maps every `ClaimKind` to a tier (enforced at import), and every claim a governed tool can emit is C1/C2/C3 — the only C5 kind, `CUSTOMER_INTENT`, is in no tool's claim list. So `(C1+C2+C3)/total` was deterministically 1.0. It restated a hardcoded claim list; it measured nothing about traffic. |
| **Replaced by** | Per-tier claim **counts** remain — they are descriptive telemetry and show C1/C2 dominate while C3 is probabilistic. `tests/test_ladder.py` does enforce, in this release, that every `ClaimKind` is mapped to a tier — that part is shipped. Removing the **ratio** itself from `schema.Decision.coverage`, `telemetry.py`, and the reports has been **prepared off-release and is not merged into this tree**: in this release, `schema.py`'s `coverage` property still computes `coverage_ratio = checkable / total`, unchanged, still deterministically 1.0 for any claim set a governed tool can produce. |

---

## What was checked and left in place

| Figure | Status |
|---|---|
| Grounding scores 0.921 (accurate paraphrase) / 0.023 (fluent-but-wrong) | Real — measured against the downloaded HHEM-2.1-Open model, `tests/test_ground.py` |
| Grounding model load (cold start) + HHEM scored-call latency | Real — **P09 measures both** (`reports/latency.md` §E cold start ≈ 9 s one-time, I/O-bound and variable; §C/§G HHEM `ground` stage p50 161 ms over 1,050 scored calls) |
| Per-stage latency p50/p95/p99/max in `reports/latency.md` | Real — **P09**: 4 configurations × 1,050 gated calls each; unrounded percentiles in `summary.json['p09_latency']`. The old n=15/n=24 interim is superseded. |
| Decision receipt size: median 2,282 B, p95 3,763 B (n=120) | Real — generated through all three manifest pipelines; see `reports/summary.json` |
| Logger 2 (extraction accuracy under noise) | Honest `not_measured` stub — unchanged |
| `reports/noise_sweep.png` | Not a noise sweep; titled honestly as Exp 3's comparison — unchanged |
