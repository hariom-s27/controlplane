# M. Statistical / multi-seed audit

## M.1 The four things being conflated in this repository

| Concept | Present? | Where |
|---|---|---|
| **Determinism** | YES, strongly | `CP_SEED=20260814`, `CP_DEMO_DATE=2026-08-14`, byte-identical DB build asserted by `tests/test_data.py::test_build_is_byte_deterministic`, content-hashed LLM fixtures, pure `decide()` |
| **Generalisation** | NO | one seed, one generator, one domain, one model, one clock |
| **Sampling uncertainty** | reported once, meaninglessly | the bias probe's p-value and MDE — over a variable with no channel |
| **Model stochasticity** | NOT MEASURED | `temperature=0.0` + content-hash cache; in `CP_MODE=fixture` (the default) the model is not called at all |

The project has achieved **excellent determinism** and treats it, in places, as though it were evidence of generalisation. `README.md`'s reproducibility section — *"If you run this code you should get the numbers we published; if you do not, that is a bug and we want to hear about it"* — is a determinism guarantee, correctly stated. It is not, and should not be read as, a validity guarantee.

## M.2 When is one seed acceptable?

**One seed is acceptable when the estimand is deterministic given the seed and the quantity of interest is not a population parameter.** That covers: the DB build hash, the negative-control transcript, unit tests, and the idempotency key.

**One seed is not acceptable when the reported quantity is an average over a random draw** — Exp 3, Exp 5, mutation, bias probe.

**But adding seeds to those four would be wrong, for a reason more fundamental than sample size:** their estimands are degenerate. Exp 5 and mutation return 1.000 for every seed; Exp 3's arms are analytic functions of two hard-coded probabilities. Multi-seed reporting would produce mean ± range around an analytically known constant, and would *increase* the appearance of rigour while adding zero information.

→ **§11's instruction — "No arbitrary statistical decoration" — points at exactly this, and the correct answer is to fix the construct, not the seed count.**

## M.3 Per-experiment decisions (§18)

| Experiment | Decision | Evidence-based reason |
|---|---|---|
| Exp 3 | **NO ADDITIONAL SEEDS REQUIRED** | Degenerate estimand (`13` §L.1). Seeds cannot repair label leakage |
| Exp 5 | **NO ADDITIONAL SEEDS REQUIRED** | Accuracy is 1.000 ∀ seeds |
| Mutation | **NO ADDITIONAL SEEDS REQUIRED** | Score is 1.000 ∀ seeds; already correctly framed |
| Bias probe | **NO ADDITIONAL SEEDS REQUIRED** | Null is structural |
| Negative control | **NO ADDITIONAL SEEDS REQUIRED** for the mechanism; **prompt-variation replication IS required** before any frequency claim | `gate_condition_check.txt` is n=5 and its script is broken (`15`, D-R1) |
| Gold-set-scored Exp 5 (after `label.py` lands) | **USEFUL BUT OPTIONAL for seeds; CLUSTER-ROBUST RESAMPLING IS REQUIRED** | `docs/gold-set.md` §2: 50 ALLOW cases on **5** source orders |
| Latency percentiles | **SCIENTIFICALLY REQUIRED** before publishing any latency figure | currently n=1 from three hard-coded constants (`13` §L.5) |
| Live-model variance (temperature > 0, repeated sampling) | **SCIENTIFICALLY REQUIRED** for any claim about agent behaviour frequency | `docs/evidence/gate_condition_check.txt` is the only such claim and it is n=5, one model |

## M.4 Clustering — the branch's most important statistical disclosure

`docs/gold-set.md` §2 states, unprompted:

> "Because several cases share one source order, the 150 cases are **clustered by `source_order_id`, not independent**. Any confidence interval computed over this set must account for that (cluster-robust SE, or a case-cluster bootstrap)."

and §5:

> "50 cases on 5 source orders. The false-positive rate this slice yields has far less independent information than n=50 suggests — treat it as roughly '5 orders, each probed 10 ways'."

**This audit endorses that assessment entirely and adds two consequences:**

1. The effective sample size for the ALLOW slice — the slice that yields the false-positive (over-block) rate, which is the most reviewer-salient number in the entire programme — is **closer to 5 than to 50**. A naive binomial CI on `50` would be roughly **√10 ≈ 3.2× too narrow** under a high intra-cluster correlation, which is what "same order, varied amount and phrasing" implies. **DERIVED, order-of-magnitude.**
2. Therefore: **paired case-cluster bootstrap over `source_order_id`**, not ordinary bootstrap, and not more seeds. Comparisons across evidence-source arms should be **paired within case** (the same case scored by each arm) and resampled **at the cluster level**.

## M.5 Ordinary vs paired bootstrap

Where arms are evaluated on the same cases (Exp 3 today; any future E1–E4 ladder), the paired difference has far lower variance than the difference of independent proportions. Use a **paired, cluster-level bootstrap**: resample `source_order_id`s with replacement, carry all their cases, recompute the arm difference. Report mean ± percentile interval, and report the number of **clusters**, not the number of cases, as the effective n.

## M.6 "Implications of K=1 P06"

Not answerable: no P06 exists (`03_premise_reconciliation.md`). The isomorphic statement about the artifact that does exist:

> **The end-to-end pipeline has been exercised on K=1 scenario, replayed from a committed fixture. Every other number is a property of a generator.**

## M.7 What good statistical practice already exists

Recorded because it is real and should not be lost in the rewrite:

- Pre-registered pass criterion for the gate condition (majority of 5), stated in `docs/ROADMAP.md` S2 **before** the run
- MDE reported alongside p-value in `bias_probe.py` — the right instinct
- `agreement.py` refuses a partial κ, "so it is safe to wire into CI now"
- `docs/gold-set.md` §2 discloses clustering unprompted and prescribes the correct remedy
- `docs/gold-set.md` §3 discloses label tells and instructs readers to treat affected scores as upper bounds
- `mutation.py` and `docs/invariants.md` cite the FSE'14 caveat and refuse to read the score as a catch rate

**Several of these are better than what appears in published work of this kind.** The problem is not statistical literacy. It is that the literate machinery is pointed at degenerate estimands.
