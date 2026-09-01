# P. Experiment-value ranking

Value function: **scientific value + reviewer impact + independence + interpretability − implementation cost − methodological risk − frozen-evidence risk.**
Frozen-evidence risk is uniformly **zero**: no frozen artifact exists to invalidate (`15_reproducibility.md` D-R2).

The brief's candidate list is evaluated first, then the candidates that the repository's actual state generates.

## P.1 The brief's list

| Candidate | Value | Cost | Method risk | Classification | Reason |
|---|---|---|---|---|---|
| **P06 C2** | — | — | — | **NOT APPLICABLE** | No P06 exists in any commit (`03`) |
| **P06 C3** | — | — | — | **NOT APPLICABLE** | ditto |
| **Multi-seed P04** | — | — | — | **NOT APPLICABLE** | No P04 exists |
| **Multi-seed P05** | — | — | — | **NOT APPLICABLE** | No P05 exists |
| **Multi-seed on the committed benchmarks** | **negative** | low | **high** | **DO NOT DO** | Estimands are degenerate (`14` §M.2). Seeds would decorate a tautology and make the reporting look more rigorous while adding nothing |
| **A5-under-corruption** | medium *in principle* | — | — | **NOT APPLICABLE as posed; SUPERSEDED** | No A5 exists. The isomorphic question — "does the gate behave correctly when the record is wrong or missing?" — is **already answered in the negative** by `docs/gold-set.md` §5 and by `09` T-5/T-11: those paths crash or have no mechanism. **Fix the code; do not measure the broken path.** Running it would produce a number describing a defect the project already documents |
| **AgentLTL comparison** | **high, and cheap** | ~half a day, **no code** | low | **DO NOW (as positioning)** | Already executed by this audit (`07`). Primary source verified: κ_ground grounds in `out(τ)`; ControlPlane re-queries the record. This is the one clean, defensible distinction — but it is a *literature* action, not an experiment |
| **Adversarial evaluation** | high | high | medium | **DO IF TIME** | OAP's 879-attempt testbed sets a visible bar (`08`). But an adversarial eval over a system with two known fail-opens (`09` T-3, T-4) measures the bugs, not the design. **Fix first** |
| **Threat-model analysis** | high | **low** | low | **DO NOW** | `09_G5_threat_model.md` is the artifact; it needs merging into `docs/`, not running |
| **Additional benchmark domains** | high | **very high** | medium | **DO NOT DO NOW** | A third domain multiplies an invalid measurement. Generality is not the binding constraint; construct validity is |
| **Additional policy variants** | low | medium | low | **DO NOT DO** | 5 of 9 manifest fields are already unread. Adding manifests before wiring `fail_posture` widens the gap between declared and actual behaviour |

## P.2 What the repository's actual state generates — ranked

| # | Action | Type (§24) | Value | Cost | Risk | Classification |
|---|---|---|---|---|---|---|
| **1** | **Commit `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl`, `test_label_independence.py`, `test_gold_set_holdout_isolation.py`; re-score Exp 5 against `label.py`'s labels** | **EMPIRICAL** | **highest available** | low — `docs/gold-set.md` says all five are written | **low, but real:** the true confusion matrix will have off-diagonal entries, and some will be the project's own bugs. That is the point | **DO NOW** |
| **2** | Fix `MODIFY`-executes-unmodified-args (`09` T-3) | IMPLEMENTATION | very high | ~3 lines | none | **DO NOW** |
| **3** | Fix `scripts/gate_check.py` arity (D-R1) | IMPLEMENTATION | very high per unit cost | **1 line** | none | **DO NOW** |
| **4** | Guard predicate evaluation so a missing record → ESCALATE, not `RuntimeError` (`09` T-5) | IMPLEMENTATION | very high | ~10 lines | none | **DO NOW** |
| **5** | Commit `reports/summary.json` + a truncated `decisions.jsonl` under `docs/evidence/` with git SHA and env | **METHODOLOGICAL** | high | ~30 min | none | **DO NOW** — creates the first genuinely frozen artifact |
| **6** | Rewrite the claim set per `19_claim_positioning_corrections.md` | LITERATURE / POSITIONING | high | ~2 h | none | **DO NOW** |
| **7** | Wire `fail_posture`, or delete it from both manifests | IMPLEMENTATION | high | ~1 h | none | **DO IF TIME** |
| **8** | Wire `escalation_for()`, or delete it and its two tests | IMPLEMENTATION | medium-high | ~1 h | none | **DO IF TIME** |
| **9** | Fill the 30 human labels; run `bench/agreement.py`; record κ | **EMPIRICAL** | high — it is the only genuinely *external* judgment obtainable at this scale | ~2 h of one person's attention | **medium:** low κ would be a real, publishable finding about the labeller. `docs/gold-set.md` §6's discipline (no partial κ) is already correct | **DO IF TIME**, after #1 |
| **10** | Chaos test: kill `policy_store.db` mid-decision, assert escalate/block | EMPIRICAL | medium-high | ~half a day | low | **DO IF TIME** — the ROADMAP itself calls this "the test that separates a demo from a system" |
| **11** | Lift the metamorphic invariants from `decide()` to `dispatch_tool` | EMPIRICAL | medium | ~half a day | low — may find real bugs | **DO IF TIME** |
| **12** | Receipt hash-chaining (prev-hash field + verifier) | IMPLEMENTATION | medium | ~2 h | none | **DO IF TIME** |
| **13** | Measure HHEM-2.1-Open on LLM-AggreFact | EMPIRICAL | medium | ~half a day + download | low | **DOCUMENT ONLY** for now — restating the bound with correct attribution costs one sentence and captures most of the value |
| **14** | Multi-seed anything currently committed | — | **negative** | low | high | **DO NOT DO** |
| **15** | τ²-bench / BFCL integration | EMPIRICAL | very high **eventually** | very high | medium | **DO NOT DO NOW** — the next artifact is a competition submission, not a paper. Revisit only if the work is retargeted at publication |
| **16** | A third domain | EMPIRICAL | medium | very high | medium | **DO NOT DO** |
| **17** | Adversarial red-team | EMPIRICAL | high | high | **high while #2/#4 stand** | **DO NOT DO NOW** |

## P.3 The single sentence

**Nine of the eleven candidates on the brief's list are either inapplicable or should not be done. The highest-value action in the entire audit is a `git push` of files the project has already written, followed by one re-run of an existing script.**

## P.4 §24 — no prose as substitute

Closure types are labelled above. Explicitly:

- **Documentation cannot manufacture** external validation (#15), statistical power (#9's κ), independent evidence (#1), falsifiability (#1), or causal identification (`12` §K.5).
- **Documentation *can* legitimately close**: the AgentLTL/prior-art positioning (#6), the M5 framing (`06` §E.3), the independence-vs-re-derivation distinction (`12` §K.4), the 77.4% attribution (#13), and every overclaim in `19`. Those are *claim* defects, and a claim defect is correctly closed by fixing the claim.
- Items #2, #3, #4, #7, #8, #12 are **IMPLEMENTATION** closures. Writing "we know about this" in a limitations section is *not* closure for a fail-open in shipped code — it is disclosure of an unfixed defect, and a reviewer will say so.
