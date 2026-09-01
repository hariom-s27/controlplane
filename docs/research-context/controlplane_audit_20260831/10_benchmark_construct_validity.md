# I. Benchmark construct-validity audit

For each committed benchmark: DATA → LABEL → PREDICTION → DECISION → SCORE.

---

## I.1 SEB-1 Exp 3 — `bench/seb1_exp3_cross_validation.py`

| Stage | What it actually is |
|---|---|
| **DATA** | `_make_case(rng, place_distractor, agent_picks_distractor)`. Draws `colour`, `target_category`, `distractor_category ≠ target_category`, `days_ago ∈ [0,7]`, `amount ∈ [50 000, 2 000 000]` |
| **LABEL** | `gold_verdict = "CONTRADICTED" if resolves_to_distractor else "VERIFIED"` |
| **PREDICTION** | `_decide_for()` sets `predicate_result["attributes_match"] = (claimed_colour == resolved_colour) and (claimed_category == resolved_category)` |
| **DECISION** | `decide(...)`; `"VERIFIED" if intervention is ALLOW else "CONTRADICTED"` |
| **SCORE** | fraction where the mapped verdict equals `gold_verdict` |

### The defect, in three lines of the source

```
resolved_category = distractor_category if resolves_to_distractor else target_category
resolved_colour   = colour                      # "the wrong order still shares the colour"
gold_verdict      = "CONTRADICTED" if resolves_to_distractor else "VERIFIED"
```
Therefore `attributes_match == (colour == colour) and (target_category == resolved_category) == not resolves_to_distractor`.

**The predicate input and the gold label are the same Boolean.** Not correlated — *identical*.

- `accuracy_with_attributes_check` = **1.000 exactly**, for every seed and every n. **DERIVED.**
- `accuracy_without_attributes_check`: with the check removed, all remaining predicates pass by construction (`days_ago ≤ 7`, `amount ≤ 2 500 000`, `entity_match = True`), so the arm always predicts VERIFIED, and accuracy = P(gold = VERIFIED) = `1 − P(resolves_to_distractor)` = `1 − 0.5×0.5` = **0.75**. **DERIVED.**

The README states the arithmetic identity and reads it as corroboration: *"75% without it — exactly matching the 25% wrong-order-resolution rate the generator produces."* **That sentence is the proof of the tautology.**

### Diagnosis
- **circularity** — YES, total
- **tautology** — YES
- **generation/scoring coupling** — YES; `_make_case` and `_decide_for` share `case`
- **denominator ambiguity** — YES; the denominator is all 200 cases, but only ~50 (25%) can discriminate. Diluting with 150 non-discriminating cases makes 75% look like a performance figure rather than a base rate
- **tasks unable to falsify the system** — 100% of them

### Estimand, stated honestly
> *"P(the gate returns CONTRADICTED | the attribute check's input was constructed to disagree)"*, which is 1 by construction.

### What it does legitimately establish
That the `attributes_match` predicate is wired through `ladder → decide → intervention` and reaches BLOCK. **That is a valuable integration test.** Call it one.

---

## I.2 SEB-1 Exp 5 — `bench/seb1_exp5_confusion_matrix.py`

| Gold class | How generated | Why `decide()` must return it |
|---|---|---|
| ALLOW | `days_ago ∈ [0,7]`, CORROBORATED, HIGH | every predicate passes → VERIFIED → ALLOW |
| BLOCK | `days_ago ∈ [8,30]` | `within_window` False → hard contradiction → CONTRADICTED → BLOCK |
| ESCALATE | `Confidence.NONE` | `decide()` sets `unverifiable` and `continue`s → UNVERIFIABLE → `verdict_handling` → ESCALATE |
| SOURCE_UNRELIABLE | `Reliability.INFERRED` vs floor `corroborated` | rank 1 < rank 2 → `source_unreliable` → SOURCE_UNRELIABLE |

**Every gold class is defined by setting the exact input `decide()` deterministically maps to it.** Accuracy is 1.000 unless `decide()` is broken. **DERIVED.**

The FP/FN definitions are structurally sound (one-vs-rest per class, TP/FP/FN correctly computed), and the cost weighting is **correctly and prominently labelled as assumed**: `ASSUMED_COST_PER_HUMAN_REVIEW_PAISE`, `ASSUMED_MEAN_REFUND_PAISE`, and a `"note"` field carried into the output. **That labelling is exemplary.** The problem is upstream: it costs a matrix that cannot have off-diagonal entries.

- **evaluator leakage** — YES: the generator *is* the oracle
- **hidden-label dependence** — YES
- **asymmetric scoring** — the cost model is present and honest; it has nothing to weigh
- **non-identifiability** — the four gold classes are perfectly separated by construction, so precision/recall carry no information

**Fix already designed:** `docs/gold-set.md` prescribes exactly this — score Exp 5 against `bench/label.py`'s labels over the 150-case gold set, which shares no code with the gate. Then off-diagonal entries become possible.

---

## I.3 Mutation testing — `controlplane/mutation.py`

Six operators; each flips one input that `decide()` is *defined* to react to. Per-operator outcomes, **DERIVED**:

| Operator | Path | Result |
|---|---|---|
| `order_id_nonexistent` | `Confidence.NONE` on both `w` and `e` | UNVERIFIABLE → ESCALATE ✓ |
| `amount_above_ceiling` | `within_authority` False | BLOCK ✓ |
| `delivered_at_outside_window` | `days_ago = 8` | BLOCK ✓ |
| `clause_version_superseded` | `clause_match` False | BLOCK ✓ |
| `customer_id_mismatched` | `entity_match` False | BLOCK ✓ |
| `order_status_inconsistent` | `INFERRED` < floor | SOURCE_UNRELIABLE → ESCALATE ✓ |

**Mutation score = 1.000, all seeds.** `docs/invariants.md` already frames this correctly as a lower bound and a regression signal, and cites Just & Ernst (FSE'14). **Keep that framing and stop there.** A score of 1.000 that is analytically forced should never appear as a headline number.

Note the honest gap: the operators mutate the *inputs to `decide()`*, not the inputs to the *pipeline*. A mutation suite over `dispatch_tool`'s arguments would exercise extract → ladder → resolve → predicate and could genuinely fail — that is where the information is.

---

## I.4 Bias probe — `controlplane/bias_probe.py`

`group = rng.choice(["A","B"])` is drawn **after** `days_ago`/`amount`, and is never passed to `_twin_decision`. `decide()` accepts no protected-attribute field anywhere in `ProposedAction`, `Claim`, `Evidence` or `SessionContext`.

Groups A and B are therefore two random samples from one distribution. The two-proportion z-test is a **valid test of the RNG's independence** and **cannot detect bias**, because no channel exists.

The docstring anticipates this — *"If the label correlates with the outcome anyway, something is reading it through a back channel nothing here declares"* — but there is no back channel to find: the label is generated in the loop and discarded. Reporting the MDE alongside the p-value is genuinely good practice; here it quantifies the power of a test with no possible signal.

- **Honest description:** *"a structural check that `decide()`'s output is independent of a variable it never receives."*
- **Not supportable:** any sentence containing "no bias" or "bias tested". The docstring's own hedge ("this only tests `decide()`, not extraction or retrieval") is right and should be the whole claim.
- Note also: `blocked = intervention in (BLOCK, ESCALATE)` conflates two interventions with different costs — a definition worth stating explicitly if this is ever reported.

---

## I.5 The negative control — `docs/evidence/negative_control.txt`

**This is the repository's best evidence artifact, and it is genuinely good.** Gate off → refund executes on an order 26 days past delivery under a 7-day policy; gate on → BLOCK citing `within_window` and `within_authority`. It has a real construct: the agent's failure is *caused* by an unfiltered retrieval index that surfaces the superseded v3.8 clause, not by prompt engineering.

Construct-validity caveats:
1. **n=1**, one customer, one order, one phrasing.
2. `CP_MODE=fixture` is the default, so the transcript is a **replay** of committed JSON, not a live model decision.
3. `data/stale_index/chunks.json` — the artifact that *creates* the failure — is **gitignored** and generated by `data/build_db.py`.
4. The companion `gate_condition_check.txt` (3/5 phrasings) is the only defence against "you staged it", and **its generating script does not run against the committed code** (`15_reproducibility.md`, D-R1).

---

## I.6 The unmerged gold set — `docs/gold-set.md` (branch `8a48bf7`)

The methodology described here is **a different quality of work** from everything above, and this audit's assessment is that the design is sound:

| Property | Assessment |
|---|---|
| Independence via a second implementation (`label.py`) | **Correct design.** Re-deriving the 7-day window from clause *prose* and the ceiling from authority-clause prose, versus the gate's manifest scalars, is a real independent derivation path |
| Its own honesty about the limit of that independence | **Exemplary.** The doc states that `clauses.json` and `servicing.yaml` "were hand-authored together to agree, so a mistake in that shared intent would sit in both", and that what the two paths catch is **drift**, not error |
| Holdout isolation | Correct design (`ground_truth_holdout.jsonl` never opened by any checker) |
| Cross-check | `gold_set_build.build()` raises if `label.py` disagrees with the constructed slice — a real oracle-consistency check |
| Clustering disclosed | **YES**, prominently: ALLOW slice = 50 cases on **5** source orders; the doc demands cluster-robust SE or a case-cluster bootstrap |
| Confounding disclosed | **YES**: "a bare 'outside window → BLOCK' rule *passes* `over_authority`, `distractor_present` and much of `stale_policy_context` without doing an authority, attribute or version check at all". This is exactly the right worry and this audit did not have to find it |
| Label tells disclosed | **YES**: four named justifications carrying the answer; `claimed_policy_version = "v3.8"` uniquely identifying a slice |
| Human validation | **Correctly withheld.** `agreement.py` refuses κ until all 30 rows are filled; §6 forbids the phrase "human validated" |

**Blocking problems, all of them provenance rather than method:**
1. `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl`, `test_label_independence.py`, `test_gold_set_holdout_isolation.py` are **not committed**. The independence guarantee is currently unauditable.
2. §5's claim that `seb1_exp5_confusion_matrix.py::run()` raises `SystemExit` is **false** — the file is byte-identical to `main`.
3. **An additional tell this audit found that the doc does not list:** in `bench/human_label_sample.csv`, `agent_justification` frequently contains the elapsed-days arithmetic *and a conclusion* — e.g. `gs-005`: *"Delivered 2026-08-09. 5 days later is still within policy; issuing INR 11,000.00."* An annotator need not compute anything. This is not a gold-label leak (the agent is wrong in the BLOCK slices), but it does reduce annotator independence and should be added to §6's residual-tells list.

---

## I.7 Summary

| Benchmark | Reproducible? | Valid? |
|---|---|---|
| Exp 3 | YES | **NO** — tautology |
| Exp 5 | YES | **NO** — tautology |
| Mutation | YES | **Valid only as framed** (regression signal) |
| Bias probe | YES | **Valid only as an independence sanity check** |
| Negative control | Partially (fixture replay; stale index gitignored) | **YES**, n=1, and it is the real one |
| Gate condition | **NO** (script broken, D-R1) | would be YES at n=5 |
| Gold set (branch) | not yet | **design is sound; artifacts absent** |

**A reproducible metric is not automatically a valid metric.** Four of the repository's metrics are perfectly reproducible and carry no information about the system's performance.
