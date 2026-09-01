# U. Top three resource decisions

## 1. Highest-value next action — **push the gold set and re-score Exp 5 against `bench/label.py`**

**Do this before anything else, including the bug fixes.**

*Evidence-based reason.* Objection #1 in `16_hostile_reviewer_objections.md` — *every reported accuracy is a tautology of its own generator* — is the objection that removes all empirical support from the project, and it is visible to any reviewer who opens `bench/seb1_exp3_cross_validation.py::_make_case` and notices that `gold_verdict` and `resolved_category` are computed from one variable. Nothing else on the list matters while that stands.

The fix is not an experiment to design. `docs/gold-set.md` (branch `8a48bf7`) describes it as already built: `bench/label.py` shares no code with the gate, re-derives the 7-day window from clause **prose** in `policy_store.db` rather than the manifest scalar, re-states the verdict precedence in its own code, and never opens the construction holdout — with two tests (`test_label_independence.py`, `test_gold_set_holdout_isolation.py`) enforcing it. **None of those five files is committed.** `bench/agreement.py` on that branch reads `bench/gold_set.jsonl`, which does not exist.

So the action is: `git push` the five missing files, then run Exp 5 against `label.py`'s labels instead of its own generator.

*What it buys.* The first non-tautological number in the project. The confusion matrix gains the ability to have off-diagonal entries. The false-positive rate becomes meaningful — over the `allow_in_window` slice, with the cluster caveat the doc already states. The word "independent" becomes checkable rather than asserted.

*What it costs.* Low, and mostly already spent.

*The risk, stated plainly.* **The real matrix will not be diagonal.** Some off-diagonal entries will be the project's own defects — `docs/gold-set.md` §5 already predicts several, including 15 gold verdicts with no runtime mechanism. That is the correct outcome. A benchmark that cannot embarrass you is not a benchmark, and the project's own documentation is the source of that standard.

---

## 2. Highest-value action after that — **fix the four defects the project has already documented, and freeze one artifact**

Four code defects, one methodological act, well under a day:

| | Fix | Cost |
|---|---|---|
| a | `MODIFY` executes unmodified args — under `knowledge_assistant.yaml`, `UNVERIFIABLE → allow_with_caveat → MODIFY → impl(**(None or args))` **sends the document** (`09` T-3, D-03) | ~3 lines |
| b | Missing record raises `RuntimeError` from the Zen graph instead of escalating (`09` T-5, D-04) | ~10 lines |
| c | `scripts/gate_check.py:42` unpacks 3 values from a 4-tuple, so the anti-staging evidence cannot be regenerated (D-05) | **1 line** |
| d | Remove `bench/report.py`'s three hard-coded latency constants, or stop claiming "never from hand-typed numbers" (D-07) | 15 min |
| e | Commit `reports/summary.json` and a truncated `decisions.jsonl` under `docs/evidence/`, stamped with the git SHA and environment (D-06) | ~30 min |

*Evidence-based reason.* (a) and (b) are **fail-opens on the privacy use case**, and both were found by the project itself — (b) is written out in `docs/gold-set.md` §5. A documented fail-open that survives into a submission is worse than an undocumented one, because it demonstrates that the register is not acted on. (c) costs one line and restores the only artifact that answers *"did you stage the demo?"*. (d) resolves a self-contradiction in the project's headline virtue. (e) creates the **first frozen artifact in the repository** — presently `reports/` and `decisions.jsonl` are gitignored, so no published figure is inspectable without rebuilding the world.

*What it buys.* Removes objections #4, #5, #14, #15 outright and materially weakens #11. Roughly a quarter of the hostile-reviewer surface, for under a day.

---

## 3. The most tempting action that should **NOT** be done — **run any of the brief's proposed experiments on the current benchmarks**

Specifically: **multi-seed P04/P05, A5-under-corruption, additional domains, additional policy variants, and an adversarial red-team.**

*Evidence-based reason, item by item:*

- **Multi-seed.** Exp 5 and the mutation corpus return **1.000 for every seed**; Exp 3's arms are analytic functions of two hard-coded `rng.random() < 0.5` draws (`13` §L.1–L.3). Multi-seed reporting would produce mean ± range around an analytically known constant. It would make the reporting *look* more rigorous while adding exactly zero information — §11's "no arbitrary statistical decoration", violated in the most expensive way, because it also lends false credibility to an invalid construct.
- **A5-under-corruption.** There is no A5. The isomorphic question — does the gate behave correctly when the record is wrong or missing? — is **already answered, in the negative, by the project's own documentation**: those paths crash (D-04) or have no mechanism to fire (D-10, `escalation_for()` is dead code). Measuring a known-broken path produces a number that describes a bug. **Fix the code; do not benchmark the defect.**
- **Additional domains / policy variants.** Generality is not the binding constraint. Construct validity is. A third domain multiplies an invalid measurement by three. And 5 of 9 manifest fields are already read by no code — adding manifests widens the gap between declared and actual behaviour.
- **Adversarial red-team.** OAP's 879-attempt testbed makes this tempting, and it would be genuinely valuable *later*. Run against a system with two live fail-opens, it measures the fail-opens. Fix (a) and (b) first, then it becomes worth doing.

*The general principle.* Every one of these produces another number. **None produces another piece of evidence.** §22's rule — *do not recommend work merely to increase experiment count* — is the operative one, and the temptation is strong precisely because the brief lists them.

---

## The ordering, in one line

**Push what is already written → fix what is already documented → freeze what is already computed. Only then consider a new experiment.**
