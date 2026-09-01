# Experiment audit — the four circular results

Five experiments were reported. Four of them cannot fail. Their headline
numbers are forced by how the test inputs are built, not by anything the
system does. This document records exactly where the circularity is, why
each number could not have come out differently, and what input would have
produced a different one. The fixes applied are summarised in
`docs/retired-figures.md`.

A circular experiment is worse than a missing one. A reviewer who reads one
of these generators and sees the result is arithmetically pre-determined
has no reason to trust any other number in the repo. That is the risk being
retired here.

File-name note: `docs/ROADMAP.md` planned these as `bench/exp3_orderid.py`,
`bench/exp5_confusion.py`, `bench/mutation.py`,
`controlplane/responsibility/bias_probe.py`. They shipped as
`bench/seb1_exp3_cross_validation.py`, `bench/seb1_exp5_confusion_matrix.py`,
`controlplane/mutation.py`, `controlplane/bias_probe.py`.

Line numbers below are against the versions of those files that produced the
retired numbers.

**Release-state note (applies to this whole document):** the public baseline is
`6ec4261` (`origin/main`). The verified local release candidate is represented
by the audited HEAD; it is not public until integrated and pushed. Its ancestor
`986b65e` contains the original C/I/D reconciliation, `dce2e4c` contains the
later recipient-authorization correction, and `aac3bea`, the Step 6B endpoint
and immediate engineering parent, synchronizes the threat model. The candidate
chain adds engineering, focused-test and public-documentation changes but no
benchmark or research artifacts, so the benchmark and research state described
here is identical in both trees.

In both the public baseline and candidate,
`bench/seb1_exp3_cross_validation.py`,
`bench/seb1_exp5_confusion_matrix.py`, and `controlplane/mutation.py` are
unchanged from the circular versions analysed below. `controlplane/bias_probe.py`
also still exists; its docstring and output report a minimum detectable effect
alongside the p-value, but the structural limitation identified here (the
group label never reaching `decide()`) is unchanged. Corrective rewrites — a
held-out gold set, a ground-truth-file design for Exp 3,
specification-derived mutation operators, and deletion of the bias probe in
favor of a structural test — were developed in off-release commit `b4ef009`,
which is not an ancestor of the baseline or candidate. They are not part of
either release state. Step 2's engineering verification did not run or
validate these experiments.

---

## EXP 5 — per-verdict confusion matrix (reported: accuracy 1.000, every off-diagonal 0)

**File:** `bench/seb1_exp5_confusion_matrix.py`

### The exact lines that make it circular

- **Lines 78–88, `_generate(rng, gold)`** — the "gold" case for each class
  is produced by calling `_decide(...)` with arguments hand-picked to make
  `decide()` return that class:
  - `gold == "ALLOW"` → `_decide(days_ago 0–7, ..., CORROBORATED, HIGH)` (every predicate passes)
  - `gold == "BLOCK"` → `_decide(days_ago 8–30, ...)` (window predicate fails)
  - `gold == "ESCALATE"` → `_decide(..., Confidence.NONE)` (routes to UNVERIFIABLE)
  - `gold == "SOURCE_UNRELIABLE"` → `_decide(..., Reliability.INFERRED, ...)` (below the reliability floor)
- **Line 73** — `predicate_result = {"within_window": days_ago <= 7, "entity_match": customer_ok}`.
  The "predicate engine" is re-implemented inline in the generator, fed the
  same constructed facts, so there is no independent check anywhere in the loop.
- **Lines 96–98** — `decision = _generate(rng, gold)` then
  `predicted = _outcome_label(decision)`. The "prediction" is `decide()`
  evaluated on the identical inputs that were chosen by working backwards
  from `gold`.
- **Line 108** — `correct = sum(matrix[g][g] for g in CLASSES)`. The
  diagonal is the only cell that can ever be non-zero.

### Why the outcome could not have been different

`decide()` is a pure, deterministic function. The gold label is defined as
"the output of `decide()` on inputs selected to produce that output," and
the prediction is "the output of `decide()` on those same inputs." Label
and prediction are the same function call. Accuracy is exactly 1.000 for
every seed, every `n`, forever. The experiment measures whether a pure
function is deterministic, dressed up as an accuracy metric.

### What input would have produced a different number

A gold set whose labels are assigned by a process independent of `decide()`
— a human annotator, or a separate reference implementation — and whose
facts are resolved by the production registry + Zen predicate pipeline rather
than chosen to hit a target verdict. Until such an artifact is used, Exp 5
has no honest number.

**OFF-RELEASE DEVELOPMENT HISTORY — NOT PART OF THE PUBLIC BASELINE OR
VERIFIED CANDIDATE (task P03):** in later development at `b4ef009`,
`bench/gold_set.jsonl` was built — 150 cases from `orders.db` rows, labelled
by `bench/label.py`, a second implementation of the refund rules that imports
nothing from `controlplane/` and parses its thresholds from clause prose —
with independence and determinism tests and `docs/gold-set.md`. None of
`bench/gold_set.jsonl`, `bench/label.py`, `docs/gold-set.md`,
`tests/test_label_independence.py`, `tests/test_gold_set_holdout_isolation.py`
or `tests/test_gold_set_determinism.py` exists in the baseline or candidate.

**BASELINE/CANDIDATE STATE:** `bench/seb1_exp5_confusion_matrix.py` is
unchanged from the circular version analysed above. `run()` does not raise
`SystemExit` for a missing gold set — the only `SystemExit` in the file is an
unrelated `dateparser` import guard. It executes to completion and still
reproduces the circular matrix. The held-out set and the later BLOCKED state
pending a non-executing pipeline driver are off-release development history.

---

## EXP 3 — order_id cross-validation (reported: 100% verdict accuracy with the check, 75% without)

**File:** `bench/seb1_exp3_cross_validation.py`

### The exact lines that make it circular

- **Line 51** — `resolves_to_distractor = has_distractor and agent_picks_distractor`.
  One boolean, drawn from two coin flips.
- **Line 53** — `resolved_category = distractor_category if resolves_to_distractor else target_category`.
- **Line 66** — `"gold_verdict": "CONTRADICTED" if resolves_to_distractor else "VERIFIED"`.
  The gold label is *defined as* `resolves_to_distractor`.
- **Lines 62–63** — `resolved_colour` is always set equal to the claimed
  colour; `claimed_category` is always `target_category`.
- **Lines 102–104** — `predicate_result["attributes_match"] =
  (case["claimed_colour"] == case["resolved_colour"] and
  case["claimed_category"] == case["resolved_category"])`. Substituting the
  construction above, this reduces to `attributes_match == (not
  resolves_to_distractor)`. The detector recomputes the label from the same
  fields the label was written from.
- **Lines 118–119** — `place_distractor = rng.random() < 0.5;
  agent_picks_distractor = place_distractor and rng.random() < 0.5`, so
  `P(resolves_to_distractor) = 0.25` exactly.
- **Line 54** (`days_ago` 0–7), **line 55** (`amount` ≤ 2.0M, ceiling
  2.5M), **line 95** (`entity_match = True`) — every other fact is
  constructed to pass, so `decide()` without the attributes check always
  returns `VERIFIED`.

### Why the outcome could not have been different

*With the check:* the gold label and the `attributes_match` predicate are
the same boolean expression over the same three fields. Agreement is 100%
by identity, not by measurement.

*Without the check:* `decide()` returns `VERIFIED` for every case (all
other facts pass by construction), and the gold label is `CONTRADICTED` for
exactly the 25% of cases where `resolves_to_distractor` is true. Accuracy
is therefore `1 − 0.25 = 0.75` — the generator's coin-flip rate, read back.
The "75% baseline" carries the identical defect as the 100% figure; it is
not an independent control.

### What input would have produced a different number

The gold label must come from construction-time ground truth — the *true*
order id recorded when the case was built — stored in a file the checker
never opens, with the verdict derived as `resolved_order_id !=
true_order_id`. And the corpus must contain distractors the attribute check
*cannot* see (same colour and category, differing on a field the check does
not read), so that a wrong-order resolution can slip past `attributes_match`
and produce a miss.

**BASELINE/CANDIDATE STATE:** neither change is present.
`bench/seb1_exp3_cross_validation.py` remains the circular version analysed
above: `resolved_colour` is always the claimed colour and
`claimed_category` is always `target_category`, so `attributes_match` still
reduces to `not resolves_to_distractor`. Neither
`bench/exp3_ground_truth.jsonl` nor `bench/exp3_checker.py` exists.
`tests/test_seb1_experiments.py` asserts
`accuracy_with_attributes_check == 1.0`; it pins the circular result rather
than testing ground-truth-file independence. The rebuilt checker-blind design
is **OFF-RELEASE DEVELOPMENT HISTORY**, not part of the baseline or candidate.

---

## MUTATION SCORE (reported: 1.000, all six operators at 1.000)

**File:** `controlplane/mutation.py`

### The exact lines that make it circular

- **Lines 22–35, `_base_scenario`** — every field is set to a value that
  passes its corresponding check.
- **Lines 38–75** — six `_mutate_*` functions. Each corrupts exactly one
  field, and each field is one that `decide()` / the Zen predicates already
  test:
  | operator | check it targets |
  |---|---|
  | `order_id_nonexistent` | confidence → NONE → UNVERIFIABLE path in `decide()` |
  | `amount_above_ceiling` | `within_authority` predicate |
  | `delivered_at_outside_window` | `within_window` predicate |
  | `clause_version_superseded` | `clause_match` in `decide()` |
  | `customer_id_mismatched` | `entity_match` predicate |
  | `order_status_inconsistent` | `reliability_floor` in `decide()` |
- **Lines 77–84, `MUTATORS`** — the operator set. `tests/test_mutation.py`'s
  own docstring states it: "one operator per `docs/invariants.md`'s table,"
  and that table mirrors the checks in `decide.py`.
- **Line 133** — `was_caught = intervention is not Intervention.ALLOW`.

### Why the outcome could not have been different

The operators were derived from the checks that exist. Every mutant
corrupts a fact that a check already reads, so every mutant is caught, so
the score is 1.000. This measures "does each check react to a corruption of
its own input" — a restatement of the unit tests — not "what fraction of
spec violations does the gate catch." A mutation score is only meaningful
when the operator set is drawn from a source the detector did not define.

### What input would have produced a different number

Operators derived from the **specification** — every field in the
`issue_refund` tool JSON schema (`agents/servicing_agent.py`) and every
threshold and posture in `manifests/servicing.yaml` — including the ones
pure `decide()` does **not** check: `currency` enum, `latency_budget_ms`,
`risk_tier_default`, `evidence_retention_days`,
`fail_posture`. Corrupting those produces misses, and a score below 1.0 is
the expected, desirable result.

**BASELINE/CANDIDATE STATE:** `controlplane/mutation.py` still defines the
same six operators analysed above (`order_id_nonexistent`,
`amount_above_ceiling`, `delivered_at_outside_window`,
`clause_version_superseded`, `customer_id_mismatched`, and
`order_status_inconsistent`), and `was_caught` remains `intervention is not
Intervention.ALLOW`. The specification-derived operator set and its non-1.0
result are **OFF-RELEASE DEVELOPMENT HISTORY**, not part of either release
state.

---

## BIAS PROBE (reported: "no detectable difference", p ≈ 0.62, MDE 0.17)

**File:** `controlplane/bias_probe.py`

### The exact lines that make it circular

- **Line 88** — `group = rng.choice(["A", "B"])`.
- **Line 90** — `intervention = _twin_decision(days_ago, amount)`. `group`
  is not an argument.
- **Lines 53–70, `_twin_decision`** — its signature is
  `(delivered_days_ago, amount_paise)`. `decide()` itself
  (`controlplane/schema.py`) has no name, demographic, or any
  protected-attribute field anywhere in `ProposedAction`, `Claim`,
  `Evidence`, or `SessionContext`.
- **Lines 93–98** — outcomes are tallied by `group`, but `group` is drawn
  independently of `days_ago` and `amount`, the only inputs that move the
  outcome.
- **Line 119** — `conclusion = "no detectable difference" if p_value >=
  alpha else ...`.

### Why the outcome could not have been different

`group` never enters `decide()`, and `decide()` is a pure function of facts
that exclude it. `p_a` and `p_b` are therefore two samples from the same
distribution; their difference is sampling noise; the p-value is
approximately uniform and almost always ≥ α. There is no causal path by
which bias could occur, so there is no path by which the test could detect
it. It passes by construction.

### What input would have produced a different number

There is none for `decide()` as written — which is the actual, defensible
finding, and it should be stated structurally, not statistically.

**BASELINE/CANDIDATE STATE:** `controlplane/bias_probe.py` is not deleted. It
still assigns `group` independently of `days_ago`/`amount`, never passes it to
`decide()`, and therefore retains the structural limitation above. Its
docstring/output were narrowed to report a minimum detectable effect with the
p-value, but this does not turn the probe into bias-performance evidence. The
following replacement was developed later and is **OFF-RELEASE DEVELOPMENT
HISTORY**; none of these paths exists in the baseline or candidate:

- `tests/test_no_protected_attributes.py` — would assert `decide()`'s input
  types contain no protected-attribute field.
- a paragraph in `docs/limitations.md` explaining why a statistical test
  over a variable the function cannot read is not evidence of anything.
- `bench/bias_proxy_probe.py` (optional, clearly labelled a proxy
  analysis) — where the group label *is* correlated with an input `decide()`
  does read (group A systematically lower amounts), so the test can
  actually fail.

---

## COVERAGE RATIO (reported: 1.0)

**Files:** `controlplane/schema.py` (`Decision.coverage`),
`controlplane/ladder.py`, `controlplane/extract.py`

### The exact lines that make it circular

- **`schema.py` lines 298–311** — `coverage_ratio = checkable / total`,
  where `checkable = C1 + C2 + C3`.
- **`ladder.py` lines 25–40** — `_TIER` maps every `ClaimKind`; **lines
  96–102** fail at import time if any member is unmapped.
- **`extract.py` lines 71–88** — `_CLAIM_KINDS_BY_TOOL` hardcodes the claim
  set per tool. The `issue_refund` set is seven kinds, all C1/C2/C3. The
  only C5 kind, `CUSTOMER_INTENT`, is never in any governed tool's list.

### Why the outcome could not have been different

Every claim a governed tool can generate is C1/C2/C3, so `checkable ==
total` for every decision the system can produce, so the ratio is exactly
1.0. It restates the hardcoded claim list. It is not a measurement of
anything about traffic, coverage, or the ladder's design.

### What input would have produced a different number

A claim set containing a C4 or C5 kind — which the current tool
configuration cannot generate. The ratio is not a finding; the underlying
property ("every `ClaimKind` is mapped to a tier") is an invariant, and its
violation is a bug, not a low metric.

**BASELINE/CANDIDATE STATE:** `tests/test_ladder.py` does enforce that every
`ClaimKind` is mapped to a tier. However, `coverage_ratio` has not been
removed from `controlplane/schema.py` (`Decision.coverage`) or
`controlplane/telemetry.py`; both still compute and surface it. Per-tier
counts remain alongside the ratio, not instead of it. Full removal of the
ratio was completed only in off-release development.
