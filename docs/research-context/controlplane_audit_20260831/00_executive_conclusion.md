# A. Executive conclusion

**Audit target:** `github.com/hariom-s27/controlplane`
**Cloned at:** 2026-08-30 · `main` @ `42143cf` · also `origin/p03-m4-blind-human-label-sheet` @ `8a48bf7`
**Mode:** read-only, static. No test, benchmark, experiment, agent or provider call was executed (§0).
**Total history audited:** 4 commits, 2026-08-28 → 2026-08-30, single author (`Hariom Singh <harioms22@iitk.ac.in>`).

---

## The single most important finding

**The audit brief describes an artifact that does not exist in this repository.**

The brief instructs the auditor to reason about `tau2`, `AgentLTL` comparison arms `A1 MessageOnly / A2 RetrievedOnly / A3 TraceOnly / A4 CachedRead / A5 LiveQuery`, phases `P02`–`P09`, conditions `C1/C2/C3`, `P06`, `evaluate-trajs`, a `GPT-4.1 NL_ASSERTION` limitation, and *frozen evidence*.

A case-insensitive search of **every blob in every commit on every branch** returns **zero** hits for: `tau2`, `tau-bench`, `AgentLTL`, `AEGIS`, `Open Agent Passport`, `LedgerAgent`, `AgentCore`, `Automated Reasoning`, `Langfuse`, `Phoenix`, `LangSmith`, `P02`, `P04`, `P05`, `P06`, `MessageOnly`, `RetrievedOnly`, `TraceOnly`, `CachedRead`, `LiveQuery`, `NL_ASSERTION`, `GPT-4.1`, `evaluate-trajs`.
*(Evidence type: EXPLICITLY ABSENT. Method: `grep -ril` across the worktree of both branch tips plus `git log --all -S` probes.)*

Consequently the following brief sections are **NOT EXECUTABLE against this repository** and are reported as such rather than guessed: §5 (τ² component decomposition), §7's ControlPlane-vs-AgentLTL *implementation* column, §20 (P06 state machine), and every statement conditioned on `P04`/`P05`/`P06` results. See `03_premise_reconciliation.md`.

Per §1D, the brief's own framing is treated as a hypothesis. **The hypothesis is falsified for this repository.** Either a substantially larger private worktree exists that was not pushed, or the brief was written against a plan rather than an artifact. Both possibilities are recorded; neither is assumed.

---

## What the repository actually is

An **Accenture Innovation Challenge 2026, Round 2, Problem Track 1** submission (`README.md` line 12; `CLAUDE.md` "Deadline is roughly 6 September 2026"). It is a working, well-documented prototype of a pre-execution tool-call gate for two synthetic use cases (refund issuance; internal document sending), ~2,000 lines of Python, 16 test files, one 91 KB build spec.

It is **not currently a research artifact**, and the gap is not one of polish. It is that **every headline number in the repository is analytically forced by its own generator**, and the one artifact that would break that circularity — `bench/label.py`, the independent labeller — **is documented but not committed**.

---

## Verdict by evidence class

| Class | Verdict | Basis |
|---|---|---|
| **Engineering craft** | STRONG | Type contracts (`controlplane/schema.py`), fail-loud tables (`ladder.py`, `compensation.py`, `extract.py::build_claims`), deterministic DB build, structural claim/fact separation enforced by `ProposedAction.facts_for_predicate()`. |
| **Documented self-criticism** | EXCEPTIONAL, and it is the project's real asset | `README.md` "Honest limitations" and `docs/gold-set.md` §5 name defects an external reviewer would otherwise have to find — including dead code, a crash path, and a slice whose gold labels have no runtime mechanism. This is rarer than any result in the repo. |
| **Empirical results** | NOT ESTABLISHED | All four reported numbers (Exp 3 accuracy, Exp 5 confusion matrix, mutation score, bias-probe null) are **tautologies of their generators**, derivable on paper without running anything. See `10_benchmark_construct_validity.md`. |
| **External validation** | NOT ESTABLISHED | No third-party benchmark, dataset, evaluator or model-independent scorer exists in the repository. Every component of every experiment is project-authored. See `05_G2_external_validation.md`. |
| **Reproducibility** | PARTIALLY ESTABLISHED, with one hard break | Seeds, frozen clock and byte-deterministic DB build are real. But `reports/` and `decisions.jsonl` are **gitignored** — no result artifact is committed — and `scripts/gate_check.py`, which produced `docs/evidence/gate_condition_check.txt`, **cannot run against the committed code** (arity mismatch, see `15_reproducibility.md` D-R1). |
| **Novelty** | NOT ESTABLISHED at system level | Deterministic pre-execution gating (arXiv 2607.07405), tool-call interception + declarative policy + signed audit record (arXiv 2603.20953), and runtime governance over execution paths (arXiv 2603.16586) are all published prior art from Mar–Jul 2026. See `08_prior_art_matrix.md`. |
| **Threat model** | NOT ESTABLISHED | `fail_posture` is declared in both manifests and **read by no code**; `MODIFY` executes the *unmodified* arguments; a null from the predicate engine is treated as *pass*. See `09_G5_threat_model.md`. |

---

## The three sentences a hostile reviewer will write

1. *"Every reported metric is computed from the same variable that defines the gold label; the 100%/75% result in the README is arithmetic, not measurement."* — **VALID.** See `10`, `11`.
2. *"The paper claims independence from the agent's context, but for the orders domain the verifier reads the same SQLite file the agent read; the independence demonstrated is freshness, not source independence."* — **VALID as stated; the policy path is genuinely independent, the orders path is not.** See `12_causal_identification.md`.
3. *"Deterministic read-only pre-execution gates on tool calls were published in July 2026 with a τ²-bench evaluation and significance tests; what is new here?"* — **PARTIALLY VALID.** A defensible narrow claim survives; the broad one does not. See `20_contribution_statement.md`.

---

## The honest bottom line

The project's **research-integrity discipline is already publishable-grade and better than its evidence**. `docs/gold-set.md` §5 documents its own dead code, its own crash path, and its own clustering — findings this audit independently re-derived from source. That register of self-caught defects, not any accuracy number, is the strongest thing in the repository.

The work that converts this from a well-documented prototype into a defensible artifact is **small and specific**: commit `bench/label.py` and the gold set, and re-run Exp 5 against labels the gate did not produce. Everything else on the brief's experiment list is either premature or waste. See `21_top_three_resource_decisions.md`.

**It is not true that "no additional experiment is justified."** Exactly one is: the gold-set-scored confusion matrix. It is already 90% built on an unmerged branch.
