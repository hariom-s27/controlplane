# Research Files 10–15 — Publication Eligibility & Quantitative Validity Audit

**Date:** 2026-08-31
**Mode:** Strict read-only / forensic research reconciliation
**Public release baseline:** `6ec4261d374904f55bf5dff1a9855854f1b94819` (= `origin/main` = `origin/HEAD`, confirmed identical, no divergence)
**Worktree used:** `controlplane-research-10-15-public-audit` (branch `research-10-15-public-audit`, created via `git worktree add` from the pinned SHA, left checked out for reference — nothing in it was modified)
**Files audited:** `10_benchmark_construct_validity.md`, `11_information_flow_leakage.md`, `12_causal_identification.md`, `13_quantitative_estimand.md`, `14_statistical_multiseed.md`, `15_reproducibility.md` (source: `D:\sem_iitk\sem9\comp\accenture\controlplane_audit_20260831\`)

This document consolidates the full audit conversation: what was checked, what was independently re-verified against the actual public source (not just trusted from the docs), and the follow-up discussion on Exp 3 / Exp 5 status. Intended to be pushed to GitHub as a standalone reviewer-facing record.

---

## 1. Setup / identity verification

```
git rev-parse --show-toplevel   → .../controlplane-research-10-15-public-audit
git branch --show-current       → research-10-15-public-audit
git status --short              → (clean)
git rev-parse HEAD               → 6ec4261d374904f55bf5dff1a9855854f1b94819
git rev-parse origin/main        → 6ec4261d374904f55bf5dff1a9855854f1b94819
git ls-remote origin refs/heads/main → 6ec4261d374904f55bf5dff1a9855854f1b94819	refs/heads/main
```
No fetch performed. No STOP condition triggered — HEAD, local worktree, and `origin/main` all agree.

Source package inventory confirmed exactly the six target files present in `controlplane_audit_20260831/` alongside files 00–09 and 16–24/99/INDEX (not opened, out of scope for this batch).

---

## 2. What was independently re-verified against source (not taken on the docs' word)

| Claim (from files 10–15) | How it was checked | Result |
|---|---|---|
| Exp 3: `attributes_match` label = prediction, same boolean | Read `bench/seb1_exp3_cross_validation.py` directly: `resolved_colour = colour` (unconditional), `resolved_category`/`gold_verdict` both keyed on `resolves_to_distractor` | **Confirmed exactly** — `attributes_match ≡ not resolves_to_distractor` |
| Exp 5: gold classes are `decide()`-deterministic | Traced ladder → predicate mapping for each of the 4 classes | **Confirmed** |
| File 10's claim that `seb1_exp5_confusion_matrix.py::run()` does NOT raise `SystemExit` for missing independent labels (branch doc's claim is false) | Grepped the file: only `SystemExit` present is an unrelated `dateparser`-missing guard (line 31) | **Confirmed** — branch doc's claim is false, file 10 is right |
| D-R1: `gate_check.py` unpack breaks against current `propose()` signature | `agents/servicing_agent.py:150-152` — `propose()` typed as 4-tuple; `scripts/gate_check.py:42` — `call, message, _ = propose(phrasing)`, 3-target unpack | **Confirmed live at public HEAD** — will raise `ValueError` on first call |
| D-R2: no frozen result artifact | `.gitignore` lines 6–11 exclude `data/*.db`, `data/stale_index/`, `reports/`, `decisions.jsonl`, `decisions_privileged.jsonl` | **Confirmed** |
| C-1: `report.py` hard-codes numbers despite README saying it never does | `bench/report.py:42-44` — `MEASURED_GROUNDING_LOAD_MS=13209.0`, `MEASURED_GROUNDING_CALL_MS=109.8`, `TYPICAL_PREDICATE_MS=0.6`; `README.md:106` — "never from hand-typed numbers" | **Confirmed, contradiction is live today, not historical** |
| Two different things both called `coverage_ratio` | `controlplane/schema.py:310` → `(C1+C2+C3)/total`; `bench/report.py:63-68` → `coverage_ratio_c1_c2 = (C1+C2)/claims_total` | **Confirmed** — real naming collision, both present |
| `docs/invariants.md` correctly frames mutation score as a lower bound (Just & Ernst FSE'14), not a headline number | Grepped lines 85-87 | **Confirmed** |
| `bench/reviewer_console.py --auto-approve` is explicitly labelled "not a measurement" | Grepped source | **Confirmed**, disclosure present and honest |
| `telemetry.py` returns `"not_measured"` rather than fabricating numbers when data is absent | Grepped `controlplane/telemetry.py` | **Confirmed** (lines 11, 40, 55) |

---

## 3. New findings beyond what files 10–15 themselves state

This is the part worth flagging most, because it goes further than the audit files' own claims:

1. **The "unmerged gold-set" branch the files call `8a48bf7`** is `origin/p03-m4-blind-human-label-sheet` — genuinely **pushed to the public GitHub remote**, but **not merged into `main`**. Correctly treated by the files as "unmerged," not "public main."

2. **The independence artifacts the files say are "not committed" are absent even from that pushed branch tip (`8a48bf7`).** Checked via `git ls-tree -r --name-only 8a48bf7`:
   - Present: `bench/gold_set_build.py`, `bench/human_label_sample.csv`, `docs/gold-set.md`, `tests/test_gold_set_determinism.py`
   - **Absent:** `bench/label.py`, `bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`, `tests/test_label_independence.py`, `tests/test_gold_set_holdout_isolation.py`

3. **Those missing artifacts exist in exactly one further commit, `b4ef009`** (commit message: *"P02 hardening, P04-P05 baselines/ablation, P07 fixes, P08 robustness, P09 latency, onboarding measurement, and P06 preflight"*), reachable from local branches `p03-m4-blind-human-label-sheet` and `p11-readme-reconciliation`.

4. **`b4ef009` has never been pushed — no remote ref points to it anywhere:**
   ```
   git branch -r --contains b4ef009   →  (empty)
   git for-each-ref refs/remotes      →  origin/HEAD, origin/main, origin/p03-m4-blind-human-label-sheet only
   ```
   So the independence guarantee for the gold set is not merely "unaudited" — it is **not publicly retrievable in any form today**, local-machine-only.

5. **P06/tau2/A1-A5 firewall check:** `grep -rli "tau2|p06"` across the entire public HEAD tree → **zero matches**, no `external/` directory. Fully off-release, consistent with file 14's "no P06 exists," and consistent with the "P06 preflight" work being bundled into the same never-pushed `b4ef009` commit.

6. **Excluded from every conclusion above, per the task's own firewall instruction:** `f782d32` (cid-modify-safety-followup), `e7110b4` (cid-engineering-fix), `d9a6773` (public-doc-fix), `c35a60d` (final-public-doc-reconciliation), and the various `research-*` worktree branches. All confirmed to sit beyond `6ec4261`; none were imported into any public-state verdict.

---

## 4. Verdicts by file

| File | Verdict |
|---|---|
| 10 (construct validity) | Exp 3 / Exp 5 **CIRCULAR / TAUTOLOGICAL** (re-derived from source, not trusted); mutation & bias-probe **valid only as framed** (regression signal / independence check); negative control is the one **genuinely valid** artifact, n=1, fixture-replay |
| 11 (leakage) | **CONFIRMED LEAKAGE** — label is algebraically identical to (Exp 3) or defines (Exp 5) the prediction input → **CONSTRUCTION-TAUTOLOGICAL** by the task's own classification rule |
| 12 (causal ID) | Gate-ON-vs-OFF: **IDENTIFIED, n=1**. Exp 3: **CONFOUNDED (degenerate — treatment and outcome are literally the same variable)**. Exp 5: **NOT A CAUSAL DESIGN**. General "independent source" claim: **PARTIALLY IDENTIFIED** (true for policy path, false for orders/entitlements — those are re-derivation, not independence) |
| 13 (estimands) | Two quantities **MISLABELLED** under the same name (`coverage_ratio`); four **DEGENERATE** (Exp3/Exp5/mutation/bias, all forced constants); latency **NOT DEFENSIBLE** (hard-coded n=1, contradicts the project's own no-hand-typing rule, confirmed still true today) |
| 14 (statistics) | Adding seeds to the four degenerate experiments is **MISGUIDED** — mathematically a constant, not a random variable, so seeds add zero information. The gold-set doc's clustering disclosure (50 ALLOW cases / 5 source orders → effective n≈5, not 50) is **real and endorsed** as the single most important present statistical caveat |
| 15 (reproducibility) | **D-R1 and D-R2 both CONFIRMED LIVE** at the public HEAD by direct code inspection — the strongest, most concretely falsifiable finding in the whole batch |

---

## 5. Publication recommendation

| File | Recommendation |
|---|---|
| 10 | **Add**, but pair with 13 §L.9-style framing ("numbers correctly withheld") so it doesn't read as purely self-flagellating |
| 11 | **Add**, consider merging into 10 (overlapping content) |
| 12 | **Add as-is** — the E1-E4 evidence ladder design is a genuine forward-looking contribution |
| 13 | **Add as-is** — single most reviewer-useful artifact in the batch (number-by-number reconciliation); promote §L.9 nearer the top |
| 14 | **Add as-is** — "seeds can't fix a constant" is a non-obvious, correct, publishable insight |
| 15 | **Add as-is, unconditionally** — D-R1 is falsifiable by any reader in 30 seconds |

---

## 6. Strongest claims (final quantitative verdict)

- **Strongest defensible claim:** the negative control demonstrates, for one committed fixture replay, that enabling the gate changes a refund decision from EXECUTE to BLOCK, and the causal mechanism (unfiltered retrieval surfacing a superseded policy clause) is real and independently verifiable in committed source.
- **Strongest unsupported claim:** any reading of "100% with the check / 75% without" (Exp 3) as a performance measurement. It's a re-derivable identity of two `rng.random() < 0.5` draws — confirmed exact by direct source re-derivation, independent of the audit docs' say-so.
- **Single largest methodological weakness:** the independence artifacts that would make Exp 5 scoreable against a real oracle exist nowhere on the public remote — not on `main`, not even on the unmerged-but-pushed branch. Every quantitative claim in the repo currently either scores against its own generator, or is unmeasured.
- **Minimum closure:** push (or cherry-pick) `b4ef009`'s `bench/label.py` + `bench/gold_set.jsonl` + `bench/ground_truth_holdout.jsonl` + the two independence tests to the public remote, merge `docs/gold-set.md`'s design into `main`, and re-score Exp 5 against it. No new experiment design needed — the design already exists and audited sound.

---

## 7. Follow-up: what Exp 3 / Exp 5 actually are and how to use them (Q&A from this session)

**Q: Are Exp 3 / Exp 5 "not implemented," or is it a different problem?**

They **are implemented and they run** — not missing, not broken as code. The problem isn't implementation, it's what the resulting numbers mean:

- **Exp 3** (`bench/seb1_exp3_cross_validation.py`) generates cases, then defines the gold label from the exact same variable (`resolves_to_distractor`) that the `attributes_match` predicate checks. "100% with the check, 75% without" is an algebraic identity of two hard-coded `rng.random() < 0.5` draws in the generator — not a measured accuracy.
- **Exp 5** (`bench/seb1_exp5_confusion_matrix.py`) picks each gold class (ALLOW/BLOCK/ESCALATE/SOURCE_UNRELIABLE) by constructing inputs that `decide()` is *defined* to map to that exact class. The confusion matrix cannot have an off-diagonal entry — accuracy = 1.000 is forced by construction, not earned.

**What they're legitimately good for:** both are real integration/regression tests. They prove the predicate wiring reaches BLOCK correctly (Exp 3) and that the ladder→`decide()` mapping hasn't drifted (Exp 5). Keep running them for that purpose. Just never report the accuracy/precision/recall figures as evidence the system "works" — they can't fail by construction, so they carry zero information about real performance.

**How to get a real number instead:** the fix already exists in design form — `docs/gold-set.md` (on the unmerged branch), which re-derives gold labels independently via `bench/label.py` (reads refund-window/authority rules from policy **clause prose** in `policy_store.db`, not the manifest's scalar fields, and imports nothing from `controlplane/`). Score Exp 5 against those independently-derived labels instead of its own generator's `gold_verdict`, and off-diagonal entries become possible for the first time — a real confusion matrix instead of a tautological one.

**Why that fix isn't usable yet:** not just "it's on an unmerged branch" — the artifacts that would make it independent (`bench/label.py`, `bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`, and the two tests that would prove the independence: `test_label_independence.py`, `test_gold_set_holdout_isolation.py`) aren't even on the *pushed* branch tip (`origin/p03-m4-blind-human-label-sheet` @ `8a48bf7`). They only exist in one further local commit (`b4ef009`) that has never been pushed to any remote ref (see §3 above). So right now, nobody outside this machine can even inspect whether the independence claim holds — closing that is the single highest-leverage next step (§6).

---

## 8. Explicitly out of scope for this batch

Per the task's STOP condition: files 16–24 and 99 were **not** opened in this pass. No experiment, benchmark, or model call was run. Nothing in the `controlplane` repository (any branch, any worktree) was modified, staged, committed, or deleted. This document itself lives outside the git repository (`D:\sem_iitk\sem9\comp\accenture\controlplane_audit_20260831\`), so writing it did not touch any tracked repository state.
