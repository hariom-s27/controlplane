# D. G2 — external-validation assessment

## The brief's τ² decomposition, applied to what exists

The brief asks for a component-by-component third-party audit of a τ²-bench integration. **No τ² integration exists in any commit** (`03_premise_reconciliation.md`). The same decomposition is therefore applied to the benchmarks that *are* committed. The result is uniform.

| Component | Third-party? | Project-authored? | Evidence (exact location) | Claim consequence |
|---|---|---|---|---|
| Task definitions | NO | **YES** | `bench/seb1_exp3_cross_validation.py::_make_case`; `bench/seb1_exp5_confusion_matrix.py::_generate` | No claim of task-distribution realism is supported |
| Policy / clause corpus | NO | **YES** | `data/seed/clauses.json`, hand-authored — README concedes the Firecrawl scrape returned `401 Unauthorized` and was abandoned | Policy realism is asserted, not sourced |
| Database | NO | **YES** | `data/build_db.py` from `data/seed/*.json`; 3 demo orders + deterministic filler | No external state |
| Evaluator / scorer | NO | **YES** | the `run()` functions in both bench scripts; `controlplane/mutation.py`; `controlplane/bias_probe.py` | Prediction and score share a module |
| Gold labels | NO | **YES, and computed from the same variable as the prediction** | `_make_case()` sets `gold_verdict` and `resolved_category` from one variable | **Fatal to the accuracy claims.** See `11` |
| Model | third-party weights, **but replayed** | fixture harness is project-authored | `agents/llm.py::chat` + `data/fixtures/*.json`; default `CP_MODE=fixture` | Qwen3-8B is third-party; its *responses in the shipped configuration* are 15 committed JSON files |
| Adapter / interception layer | NO | **YES** | `controlplane/intercept.py` | — |
| Manifests | NO | **YES** | `manifests/*.yaml` | — |
| Resolvers | NO | **YES** | `controlplane/registry/*.py` | — |
| Predicate graph | Zen Engine (third-party **runtime**, MIT) | **graph content project-authored** | `zen-engine>=0.30`; `predicates/graphs/*.json` | Using a third-party rule *engine* is not third-party *evidence* |
| Grounding model | **YES** — HHEM-2.1-Open (Vectara, Apache-2.0) | invocation project-authored | `controlplane/ground.py` | The only genuinely external checker in the repo. Off by default (`CP_GROUNDING=off`), exercised by 2 fixtures |
| ControlPlane decision logic | NO | **YES** | `controlplane/decide.py` | — |

**Count of genuinely external components on the evidence path: one (HHEM-2.1-Open), disabled by default.**

## The one real external anchor, and why it does not carry the weight placed on it

`controlplane/ladder.py`'s docstring makes the repository's central honesty argument:

> "it is what lets the pitch say 'C1/C2 are ~100% because SQL and arithmetic are exact; C3 is bounded by published NLI SOTA (77.4%) and that is the actual bottleneck'"

Verified against the primary source (LLM-AggreFact leaderboard, fetched 2026-08-30): **77.4 is the top average score, held by Bespoke-MiniCheck-7B.** That is correct.

But the deployed checker is **HHEM-2.1-Open**, which **does not appear on that leaderboard**, and Bespoke-MiniCheck-7B is the model `requirements.txt` explicitly *excluded* on CC BY-NC licence grounds. The bound is therefore borrowed from a model the project deliberately does not run, and HHEM-2.1-Open's own LLM-AggreFact score is **NOT ESTABLISHED** anywhere in the repository or by this audit.

→ **Safe restatement:** *"C3 is probabilistic. The best-reported score on LLM-AggreFact is 77.4 (Bespoke-MiniCheck-7B); we deploy HHEM-2.1-Open, whose score on that benchmark we have not established, so C3 is treated as moderate confidence and never blocks."* That is both true and stronger, because it is checkable.

## Can any current evidence support an "external validation" claim?

**No.** Applying §5's rule ("Never call project-authored integration third-party evidence"):

- `docs/evidence/negative_control.txt` — project-authored scenario, project-authored agent, replayed fixture, hand-written transcript. It is a **demonstration**, not validation.
- `docs/evidence/gate_condition_check.txt` — the only artifact that used a live third-party model. It is n=5 and its generating script does not run against the committed code (`15`, D-R1).
- Exp 3 / Exp 5 — fully internal, tautological.

## Safe wording *today*

> "ControlPlane is a prototype runtime gate demonstrated on two synthetic use cases built by the authors. It has not been evaluated on any external benchmark, and no component of its evaluation is third-party. Reported accuracy figures are properties of the synthetic generators and are reported as implementation checks, not performance measurements."

## Stronger wording, and exactly what would earn it

| Wording | Requires |
|---|---|
| "…evaluated against an independently-derived gold set of 150 cases whose labels were produced by a labeller sharing no code with the gate" | Commit `bench/label.py`, `bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`, `tests/test_label_independence.py`, `tests/test_gold_set_holdout_isolation.py`; then run Exp 5 against those labels. **All five are described as already written in `docs/gold-set.md`.** This is the single highest-value action in the whole audit |
| "…human-validated (Cohen's κ = …)" | 30 human labels in `bench/human_label_sample.csv`. `bench/agreement.py` correctly refuses to print κ until all 30 are filled, and `docs/gold-set.md` §6 correctly forbids the phrase "human validated" until then. **Do not weaken this discipline** |
| "…externally validated" | An off-repo benchmark (τ²-bench-verified and BFCL are the obvious candidates, both used by arXiv 2607.07405). This is a genuinely different and much larger piece of work, and it is **not** the next thing to do |

## G2 status

**NOT ESTABLISHED.** One external model, disabled by default, whose accuracy bound is imported from a different model. Everything else on the evidence path is project-authored, and the label and the detector share a variable.
