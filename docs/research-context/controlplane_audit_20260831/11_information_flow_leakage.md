# J. Information-flow / leakage audit

Shared dependencies among data, labels, predictions, decisions, scoring and other arms. **Separate files do not guarantee independence — and here they are not even separate files.**

## J.1 Dependency graph, Exp 3

```
        rng(seed=20260814)
              │
              ▼
   place_distractor, agent_picks_distractor
              │
              ▼
      resolves_to_distractor          ← ONE VARIABLE
        ╱                    ╲
       ▼                      ▼
  resolved_category      gold_verdict
       │                      │
       ▼                      │
  attributes_match ───────────┤
       │                      │
       ▼                      ▼
   decide() ──► prediction ══ SCORE
```
Label and prediction descend from the same node with no intervening independent process. **Total label leakage.**

## J.2 Classification per experiment

| Leakage class | Exp 3 | Exp 5 | Mutation | Bias probe | Negative control |
|---|---|---|---|---|---|
| **Label leakage** (label derivable from prediction input) | **YES — identical bit** | **YES** — gold class *is* the input setting | N/A (no labels; "caught" = "≠ ALLOW") | N/A | NO (no label) |
| **Evaluator leakage** (scorer sees construction truth) | **YES** — `run()` reads `case["gold_verdict"]` and `case["resolved_category"]` from the same dict | **YES** — `run()` holds `gold` while calling `_generate(gold)` | N/A | N/A | NO |
| **Hidden-label access** | YES | YES | N/A | N/A | NO |
| **Generation/scoring coupling** | **YES** — `_make_case` and `_decide_for` are in one module and share `case` | **YES** — one module | YES by design (intended) | YES by design | NO |
| **Post-treatment contamination** | **YES** — `resolved_category`, an outcome of the simulated resolution, is used to define the label | **YES** — reliability/confidence are set to force the label | N/A | NO | NO |
| **Cross-arm contamination** | **YES** — the with-check and without-check arms are two calls to `_decide_for` on the *same* `case` objects; not merely paired, but sharing the label-defining variable | N/A (single arm) | N/A | NO — groups share the RNG stream but not the outcome | N/A |

## J.3 The mechanism that *does* prevent leakage, and deserves credit

`ProposedAction.facts_for_predicate()` (`controlplane/schema.py`) is a genuine information-flow control on the **production** path: it returns a whitelist of 8 structural fields, and `predicates/__init__.py::evaluate()` accepts nothing else from the action object. `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine` guards it. `controlplane/registry/policy.py` goes further — the resolver's *signature* cannot receive the agent's assertion.

**This is a well-designed leakage control, and it is the strongest engineering idea in the repository.** It is also, precisely, the discipline that the *benchmark* code abandons. The production path forbids the claim from reaching the check; the evaluation path lets the label reach the prediction.

## J.4 The branch's design, assessed

`docs/gold-set.md` describes the correct architecture:

- `bench/label.py` imports nothing from `controlplane/`, enforced by an AST-parsing test
- thresholds re-derived from clause **prose** in `policy_store.db`, not the manifest scalar
- `ground_truth_holdout.jsonl` never opened by any checker
- join on opaque `case_id`, never row position

Residual coupling the doc **itself** names, correctly:
1. `data/seed/clauses.json` and `manifests/servicing.yaml` were hand-authored together — so the two derivation paths catch **drift**, not shared misinterpretation. The doc says this explicitly and does not overclaim.
2. Slice confounding: because few orders are recently delivered, most `over_authority` / `distractor_present` / `stale_policy_context` cases are *also* outside the window, so "outside window → BLOCK" passes them without exercising the intended check.

Residual coupling the doc does **not** name (added by this audit):
3. `agent_justification` in `human_label_sample.csv` often states the elapsed-days computation and a conclusion (`gs-005`, `gs-009`). Reduces annotator independence; belongs in §6's residual-tells list.

## J.5 Verdict

**Every committed accuracy number in this repository is contaminated.** Not through subtle correlation — through direct sharing of the defining variable.

The remedy is architectural and already specified by the project: **score against labels the gate did not produce.** That is one merge and one re-run, not a research programme.
