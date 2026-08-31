# Premise reconciliation — the brief vs. the repository

> **Publication note (added for public release; not part of the original audit).** This document reflects the repository state as independently audited on **2026-08-30**, at commit `main@42143cf`. That commit is an ancestor of the current public release, `6ec4261`. Two public documents — [`docs/experiment-audit.md`](experiment-audit.md) and [`docs/retired-figures.md`](retired-figures.md) — were added to this repository *after* this audit snapshot and are not accounted for anywhere below, including in the file-presence table under "The `p03-m4` branch is the only bridge," where `docs/experiment-audit.md` is recorded as absent from the branch inspected at the time. That row describes the audited snapshot, not the current repository — a file of that name exists in the current public repository, added afterward. Throughout this document, "absent," "EXPLICITLY ABSENT," and "NOT PRESENT" describe what was found in the repository as it existed at the audit snapshot. They are not claims that the referenced material never existed, was abandoned, or has not since been added — only that it was not present in the commits inspected at that time.

*Read this before any section that references P0x, C1/C2/C3, τ², or A1–A5.*

Per §1D, the brief's introductory framing is a **hypothesis**. This file tests it.

## Method

For each term the brief treats as an existing artifact, a case-insensitive content search was run over the worktrees of both branch tips, plus `git log --all -S` / `-G` probes over the full 4-commit history. `.git` was excluded from content search; history was probed separately.

## Result

| Brief term | Hits, all branches, all commits | Status |
|---|---|---|
| `tau2`, `tau-bench` | 0 | EXPLICITLY ABSENT |
| `AgentLTL` | 0 | EXPLICITLY ABSENT |
| `AEGIS`, `Open Agent Passport`, `LedgerAgent`, `AgentCore`, `Automated Reasoning`, `Langfuse`, `Phoenix`, `LangSmith` | 0 each | EXPLICITLY ABSENT |
| `A1 MessageOnly` … `A5 LiveQuery` (any arm name) | 0 | EXPLICITLY ABSENT |
| `P02`, `P04`, `P05`, `P06` | 0 | EXPLICITLY ABSENT |
| `P03` | 1 file — `docs/gold-set.md`, **branch only** | PARTIALLY PRESENT |
| `M4` | 5 files — but as metamorphic invariant **M4 (idempotence)** and as branch task "P03/M4", two different referents | AMBIGUOUS |
| `NL_ASSERTION`, `GPT-4.1`, `evaluate-trajs` | 0 | EXPLICITLY ABSENT |
| frozen benchmark artifacts | `reports/`, `decisions.jsonl`, `decisions_privileged.jsonl` all in `.gitignore`; `docs/evidence/` contains 2 hand-written `.txt` transcripts and nothing machine-readable | EXPLICITLY ABSENT |

## The vocabulary collision that matters

**`C1`/`C2`/`C3` mean something entirely different in the repository than in the brief.**

- **Brief:** experimental *conditions* in P06 — C1 baseline, C2 ControlPlane governance, C3 stale policy context.
- **Repository:** `Tier.C1`…`Tier.C5` in `controlplane/schema.py` — the **Checkability Ladder**: C1 computable, C2 look-up-able, C3 document-grounded, C4 consensus, C5 unverifiable.

Any statement of the form "C1 is frozen, C2 is prepared, C3 is not started" is **unintelligible against this repository**, where C1/C2 are claim tiers assigned at every decision by `ladder.py::classify`. This audit uses `Tier.Cn` whenever the repository sense is meant.

## The `p03-m4` branch is the only bridge

The unmerged branch `origin/p03-m4-blind-human-label-sheet` @ `8a48bf7` adds 6 files / 1,730 lines and speaks the brief's dialect: it references **P03**, **P04**, **P08**, arms called **"B3 the LLM-judge"**, "the trace-grounded and live-query pipelines", and `docs/experiment-audit.md`. This is strong evidence that the larger programme the brief describes **exists as a plan**, and that `P03` is its first landed increment.

But the branch is also where the premise gap is sharpest. `docs/gold-set.md` documents an **independence guarantee enforced by tests over a labeller**, and *none of those files is committed on that branch*:

| File the doc relies on | Present on `8a48bf7`? |
|---|---|
| `bench/gold_set_build.py` | **YES** (763 lines) |
| `bench/agreement.py` | **YES** (175 lines) |
| `bench/human_label_sample.csv` | **YES** (30 rows, `human_label` blank) |
| `bench/label.py` — *the independent labeller, the whole point* | **NO** |
| `bench/gold_set.jsonl` — the 150 labelled cases | **NO** |
| `bench/ground_truth_holdout.jsonl` | **NO** |
| `bench/exp3_checker.py` | **NO** |
| `docs/experiment-audit.md` | **NO** |
| `tests/test_label_independence.py` — the AST check that enforces independence | **NO** |
| `tests/test_gold_set_holdout_isolation.py` | **NO** |

So on the pushed branch: `bench/agreement.py` reads `bench/gold_set.jsonl`, which does not exist; and the doc's central claim — "`tests/test_label_independence.py` parses its AST and fails on any `controlplane` import" — **cannot currently be checked by anyone**.

`docs/gold-set.md` §5 also asserts that `bench/seb1_exp5_confusion_matrix.py::run()` "raises `SystemExit`". `git diff origin/main origin/p03-m4-blind-human-label-sheet -- bench/seb1_exp5_confusion_matrix.py` is **empty**; the function is unchanged and returns a matrix. (Contradiction C-2 in `01_method_scope_and_limits.md`.)

## Consequences for the rest of this audit

1. **§20 (P06 boundary) is answered as: NOT STARTED — no P06 artifact of any kind exists in the repository.** Not "prepared", not "frozen". Per §20's own rule, C2/C3 are not treated as results; here neither is C1, because there is no C1 either.
2. **§5 (τ² component decomposition)** is reframed: the same decomposition is applied to what does exist — the servicing and knowledge-assistant benchmarks — and the answer is that *every* component is project-authored. See `05_G2_external_validation.md`.
3. **§7 (AgentLTL)** is executed on the primary-source side only, and the comparison column is "ControlPlane as implemented in this repository", not "as described in the brief". See `07`.
4. **§6 (G3 / "A5 100% by construction")** is *not* discarded. The brief's worry is exactly right — it is simply pointed at the wrong artifact. The 100%-by-construction defect is present, four times over, in what is committed. See `06`.

## What would close this gap

Not an experiment. **Push the rest of the branch.** `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl` and the two isolation tests are, on the doc's own account, already written. Until they are in the repository, every independence claim in `docs/gold-set.md` is **NOT DOCUMENTED** in the §2A sense — asserted, not inspectable.
