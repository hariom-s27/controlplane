# Retired figures

An internal audit (`docs/experiment-audit.md`) found that four of the five
reported experiments were circular: their headline numbers were forced by
how the test inputs were built, not by anything the system does. None of
the four could produce a failing result. They are retired here.

This is evidence discipline, not an apology. A benchmark that cannot fail is
worth less than no benchmark — it trains a reviewer to distrust the numbers
that are real. Removing these makes the rest of the repo's measurements
more credible, not less.

Every retired figure below is one the project generated about *itself*.
External figures once quoted in the pitch (an NLI state-of-the-art score,
LLM-judge approval/catch rates, USPS OIG scan-error rates) are not backed by
any committed file in this repository and are no longer quoted in its
public text.

---

## 1. Confusion matrix — accuracy 1.000

| | |
|---|---|
| **Was** | 4×4 gold-vs-predicted matrix, accuracy 1.000, every off-diagonal 0, per-class precision and recall all 1.0 |
| **Appeared in** | `reports/confusion.md`, `reports/summary.json`, `README.md`, `bench/report.py` |
| **Why retired** | `bench/seb1_exp5_confusion_matrix.py` generated each "gold" case by calling `decide()` with arguments chosen to force a known verdict, then scored `decide()` on those same inputs. Label and prediction were the same function call. Accuracy was exactly 1.000 for every seed and every `n`. |
| **Replaced by** | Nothing yet — the experiment is **BLOCKED**. `run()` raises `SystemExit`. It resumes when task P03 delivers `bench/gold_set.jsonl`, a held-out set whose labels are assigned independently of `decide()`. `reports/confusion.md` now says so. |

## 2. order_id cross-validation — 100% with the check, 75% without

| | |
|---|---|
| **Was** | "100% verdict accuracy with the R3 `attributes_match` check on distractor cases, 75% without it" |
| **Appeared in** | `reports/summary.json`, `README.md` ("Exp 3's result is real and worth stating…") |
| **Why retired** | The gold label was *defined as* `resolves_to_distractor`, and the `attributes_match` predicate — the detector — recomputed that same boolean from the same fields. 100% agreement was an identity, not a measurement. The 75% baseline was `1 − P(wrong resolution)` read straight off the generator's coin flips. |
| **Replaced by** | `bench/seb1_exp3_cross_validation.py` rebuilt: the true order id is recorded at construction time in `bench/exp3_ground_truth.jsonl`, a file the checker (`bench/exp3_checker.py`) never opens — asserted by AST inspection in `tests/test_seb1_experiments.py`. Gold verdict is `resolved_order_id != true_order_id`. The corpus now includes "hidden" distractors (same colour and category, different size) that the check cannot see. **Current numbers:** in README ("Honest limitations") and `docs/claims.yaml` (`exp3-accuracy-with-check`, `exp3-accuracy-without-check`), recomputed by `tests/test_claims.py`. The check misses every hidden-distractor wrong resolution — a real, reported blind spot, which is what makes the experiment able to fail. |

## 3. Mutation score — 1.000

| | |
|---|---|
| **Was** | Mutation score 1.000, all six operators at 1.000 |
| **Appeared in** | `reports/summary.json`, `README.md`, `docs/invariants.md` |
| **Why retired** | The six operators were derived from the six checks `decide()` already implements (`tests/test_mutation.py`'s own docstring: "one operator per `docs/invariants.md`'s table"). Every mutant corrupted a fact some check was already watching, so every mutant was caught. The score restated the unit tests. |
| **Replaced by** | `bench/mutation.py` (originally shipped as `controlplane/mutation.py`) rewritten so operators come from the **specification** — the `issue_refund` tool JSON schema and `manifests/servicing.yaml` — including elements the gate has no mechanism to enforce (`currency` enum, negative amount, latency/escalation budgets, retention days, risk tier). **Current score:** in `docs/invariants.md` and `docs/claims.yaml` (`mutation-score`, `inv-mutation-catchable`), with a per-operator table in `reports/summary.json` naming exactly which spec violations the gate does not catch. A score of 1.0 now fails `tests/test_mutation.py` — it would mean the operator set had drifted back to mirroring the implementation. |

## 4. Bias probe — "no detectable difference"

| | |
|---|---|
| **Was** | "no detectable difference", p ≈ 0.62, minimum detectable effect 0.17 at n=200, 80% power |
| **Appeared in** | `reports/summary.json`, `README.md` ("…rather than a bare 'no bias found.'") |
| **Why retired** | `controlplane/bias_probe.py` drew a group label with `rng.choice(["A","B"])` and never passed it to `decide()`, which is a pure function of facts that exclude it. With no path by which the label could affect the outcome, "no detectable difference" was the only result the test could produce. It passed by construction, not by correctness. |
| **Replaced by** | The probe is **deleted**. In its place: `tests/test_no_protected_attributes.py` verifies *structurally* that `decide()` and every type feeding it carry no protected-attribute field and that `decide()`'s signature takes no such parameter — a stronger claim than a statistical test over a variable the function cannot read. `docs/limitations.md` carries the reasoning. `bench/bias_proxy_probe.py` is a clearly-labelled proxy analysis (group label correlated with `amount_paise`, an input `decide()` does read) that exists only to show the statistical machinery has power when an effect is actually present. |

## 5. Coverage ratio — 1.0

| | |
|---|---|
| **Was** | "C1+C2 coverage_ratio = 1.0", also surfaced per-decision as `telemetry.coverage.coverage_ratio` |
| **Appeared in** | `reports/coverage.md`, `reports/summary.json`, `controlplane/schema.py`, `controlplane/telemetry.py`, `bench/report.py` |
| **Why retired** | `ladder.py` maps every `ClaimKind` to a tier (enforced at import), and every claim a governed tool can emit is C1/C2/C3 — the only C5 kind, `CUSTOMER_INTENT`, is in no tool's claim list. So `(C1+C2+C3)/total` was deterministically 1.0. It restated a hardcoded claim list; it measured nothing about traffic. |
| **Replaced by** | Per-tier claim **counts** stay — they are descriptive telemetry and show C1/C2 dominate while C3 is probabilistic. The **ratio** is gone from `schema.Decision.coverage`, `telemetry.py`, and the reports. "Every `ClaimKind` is mapped to a tier" is now framed as what it is — an invariant, tested in `tests/test_ladder.py`, whose violation is a bug, not a low metric. |

---

## Other figures checked later, and their status (P05b, 2026-11-14)

| Figure | Status |
|---|---|
| HHEM grounding scores for the two `tests/test_ground.py` fixtures | Retired by P05b: the exact scores were never committed; the test checks only that each is above / below its threshold |
| Grounding model load (cold start) + HHEM scored-call latency (P09) | Retired by P05b (`docs/errata.md`): not in the current latency evidence pack |
| Per-stage and end-to-end latency in `reports/latency.md` (P09) | Retired by P05b (`docs/errata.md`); current figures come only from `bench/results/latency-m1-356ec58/` |
| Decision receipt size (P05 era) | Retired by P05b (`docs/errata.md`): stale since the verification-coverage block was added; no current size is quoted |
| Logger 2 (extraction accuracy under noise) | Honest `not_measured` stub — unchanged |
| `reports/noise_sweep.png` | Not a noise sweep; titled honestly as Exp 3's comparison — unchanged |
