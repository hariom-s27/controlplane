# ControlPlane Plan Package `_2` — Final Reconciliation Report

**Date:** 2026-08-31
**Mode:** strict read-only forensic plan audit. No repository files were edited, no commits made, no `fetch`/`pull`/`push`, no tests or experiments run, no `R05` prompt executed. All repository claims rest on `git show`/`git diff`/`git log`/`git ls-remote` against **committed objects only**. The worktree's uncommitted P06-C2 changes and `reports/tau2-bench.md` were identified by name only (`git status --short`) and not read further, in case a live tau2-bench run was still in flight there.

Audited package: `D:\sem_iitk\sem9\comp\accenture\controlplane_plan_20260831_2` (`R00`–`R06`), against the current public baseline and everything completed or attempted since.

---

## 1. Package path
`D:\sem_iitk\sem9\comp\accenture\controlplane_plan_20260831_2` — 7 files, all read completely (`R00` 15.2KB, `R01` 12.1KB, `R02` 11.1KB, `R03` 10.1KB, `R04` 9.5KB, `R05` 21.0KB, `R06` 3.1KB; all `mtime` 2026-08-31 16:18–16:24).

## 2. Public release HEAD
`origin/main` = **`6ec4261d374904f55bf5dff1a9855854f1b94819`**, verified via `git ls-remote origin refs/heads/main` (no fetch performed) — matches the expected anchor exactly. No STOP condition triggered.

**Critical calibration finding, governs everything below:** local branch `main` itself is still at `42143cf` (one behind). `6ec4261` = `42143cf` + one commit, **"Reconcile public audit disclosures and retire circular claims,"** touching only `README.md`, `docs/experiment-audit.md`, `docs/retired-figures.md`. `R00`'s entire premise ("public repo unchanged since 29 Aug, 4 commits total, nothing pushed") was true when `R00` was fetched but is **now stale** — `6ec4261` was pushed to `origin/main` after this package was authored.

## 3. Worktree identity
`D:/sem_iitk/sem9/comp/accenture/phase 2/controlplanestarter/controlplane`, branch `p03-m4-blind-human-label-sheet`, local `HEAD b4ef009` (1 commit ahead of its own remote tracking branch, not present on `origin/main`). Uncommitted: `decide.py`, `reports/tau2-bench.md`, `schemas/manifest.schema.json`, `tests/test_manifest_hardening.py` modified; 12 untracked `tau2_*` files — consistent with the P06-C2 governance integration + P02 fixes recorded in project memory. Not inspected further (working-tree-only, possibly live).

## 4. Files inspected
All 7 package files (full read) · 17 local branches enumerated (`git branch -a -v`) · full diffs of `f782d32`, `e7110b4`, `d9a6773`, `c35a60d`, `1e8b7fc`, `6089862` against their parents · `README.md`, `docs/experiment-audit.md`, `scripts/gate_check.py`, `bench/report.py`, `agents/servicing_agent.py` at `6ec4261` · same files' state on `b4ef009` for comparison · `08_prior_art_matrix.md`, `19_claim_positioning_corrections.md`, `20_contribution_statement.md`, `INDEX.md` from the first package (`controlplane_audit_20260831`, confirmed **not a git repo** — plain files) · cross-checked against project memory (P01–P09, P06 C1/C2).

## 5. R00 findings
`R00`'s 15 "you were right" items and 9 "I'd correct you" items are internally sound reasoning with no logic errors found on re-check. But its **evidentiary foundation is now partly obsolete**:

| R00 claim | Then | At `6ec4261` now |
|---|---|---|
| "public repo unchanged since 29 Aug, only `main`+`p03-m4` refs" | TRUE at fetch time | **SUPERSEDED** — `origin/main` advanced to `6ec4261` |
| "`docs/experiment-audit.md` on no pushed ref" | TRUE | **FALSE now** — public, at repo root of `6ec4261` |
| "README still carries the retired 100%/75% figure" | TRUE (was reading `42143cf`) | **FALSE now** — README §"What we retracted" discloses it as retired, doesn't assert it |
| "`b4ef009` doesn't exist in public history" | TRUE | **STILL TRUE** — confirmed not an ancestor of `6ec4261` |
| "P02/P04/P05/P08/tau2/`bench/label.py` — no trace on any pushed ref" | TRUE | **STILL TRUE** — none are ancestors of `6ec4261`; exist only on `b4ef009` |
| §2.1 "C1/C2 FROZEN → downgrade to SEALED LOCALLY" | correct call | **STILL TRUE** — `reports/p06-c1-freeze.json` is explicitly `.gitignore`d, confirmed; no `docs/evidence/p06/` exists on any branch |
| §2.4 "fault not localised, run the 10-min P1–P4 probe first" | correct call | **OBSOLETE** — see §21 |

Classification: `R00` §1 (15 items) = **HISTORICAL, correct reasoning, still valid guidance**. `R00` §2.1, §2.7 (freeze integrity, bug-table discipline) = **CURRENTLY TRUE, still open**. `R00`'s headline finding ("nothing pushed") = **PARTIALLY TRUE → now FALSE for docs, TRUE for engineering**.

## 6. R01 findings
Two self-corrections, both hold up under my own check of the primary-package source file:

- **AEGIS**: `R01` says the correct paper is `arXiv:2603.12621` (pre-execution firewall, Ed25519+SHA-256 chained receipts, 48/48 adversarial), not `2603.16938`. I confirmed `08_prior_art_matrix.md` in the *first* package (`controlplane_audit_20260831`) **still cites `2603.16938`**, and `20_contribution_statement.md` still says only "Aegis: Immutable Logging Kernel" with no corrected identifier. **The correction is right and has not propagated anywhere** — not into the source research files, not into any repo doc (no related-work file exists in the repo on any branch).
- **LedgerAgent** (`2606.20529`): same status — genuinely new, not previously in `08_prior_art_matrix.md`, not yet anywhere in the repo.

Status: **ENGINEERING = N/A; DOCUMENTATION/RESEARCH = correction verified sound, not yet applied anywhere it would matter (no related-work doc exists to apply it to yet).**

## 7. R02 findings
`R02_PRIOR_ART_V2.md` is a superset/correction of `08_prior_art_matrix.md`. Cross-checked its central positioning paragraph against `08`'s: R02's distinction ("evidence re-queried from the current system of record at adjudication, vs. every peer using trace/context-derived evidence") is consistent with `08`'s surviving §8A row ("adjudicating the claim against the versioned business record... CLEARLY DISTINGUISHED"). **No conflict** — R02 sharpens `08`, doesn't contradict it. R02's added rows (LedgerAgent, LEDGER, Auditable Agents, provenance survey, Safe-agents survey) are net-new and don't appear in `08` at all. **R02 supersedes `08_prior_art_matrix.md` cleanly; `08`/`20` should be treated as stale once a real related-work doc is written (CC-12).**

## 8. R03 findings
| Gap R03 raises | Classification |
|---|---|
| §1 fault localisation (model/provider/harness/adapter) | **OBSOLETE** — see §21; superseded by empirical resolution (model switch + live C2 run) |
| §2 request-side tool-call evidence | **OBSOLETE**, same reason |
| §3 preregistration for the next track | **STILL OPEN in principle, but N/A to P05** — see §16 CC-8 |
| §4 two deadlines (submission vs. research) managed as one | **STILL A VALID FRAMING DEVICE**, non-material to reconcile further |
| §5 "strategic reframe" — build the A1–A5 ladder over the gold set | **FIXED / ALREADY COMPLETED** — this is exactly P05 (`bench/evidence_ablation.py`), done 2026-08-30, off-release on `b4ef009`. R03 presents this as the biggest undone thing; it is not undone. |
| §6.1–6.4 (non-native action protocol, tau2-verified, empty-completion vs. no-tool-call, `max_tokens`) | **PARTIALLY OBSOLETE** — moot for the now-archived Kimi-K2 C1; possibly still relevant if C2's live run hits the same issue, unknown without reading the live run |
| §8 items to drop (P13-B, same-config C3, retro P12, 5–6h P02 refactor, multi-seed on deterministic pipelines) | **CORRECT, and independently corroborated** — memory confirms P05 explicitly rejected multi-seeding a deterministic pipeline for exactly this reason |

## 9. R04 findings
Rebuilt against current state:

- **Phase 0** (probe, request evidence, freeze manifest, deferral note, bug-table verify): items 0.1/0.2 **obsolete**; 0.3 (freeze manifest) **still open, still P0**; 0.5 (bug-table verify) **still useful**.
- **Phase 1** (P11 reconciliation, retire figures, 4 one-line fixes, commit audit doc, narrow "same engine" wording): 1.2 and 1.4 are **already done** at `6ec4261`. 1.3 (four fixes) is **2 of 4 done, off-release, in two conflicting implementations** — see §16 CC-5, §14. 1.5 unverified but low-stakes.
- **Phase 2** (A-ladder): **already executed and validated** as P05, off-release. The remaining work is *publish*, not *build/run*.
- **Phase 3** (new C1′/C2′ track): **superseded** — a live C2 run against the archived Kimi-K2 C1 is reportedly in progress; running Phase 3 now would duplicate/conflict with in-flight paid work.
- **Phase 4** (P10 related work, Auditable Agents self-scoring, threat model, final claim pass): **entirely untouched, still needed**, correctly non-blocking per R04's own schedule.

## 10. R05 findings
See the full per-prompt table in §16.

## 11. R06 findings
`R06_INDEX.md`'s "5 things that matter" list mirrors `R00` almost verbatim, so it inherits R00's staleness on item 1 ("nothing is pushed"). Its "run order" (`CC-1 → GATE A → ... → CC-6`) is now the wrong order given that CC-6's own retirement work is already public and CC-9's A-ladder is already run — a reader following R06 literally today would re-derive work that exists. **R06 does not represent the package accurately as of today**; it needs a one-line update noting `6ec4261` is public and P05/CID-hardening exist off-release.

## 12. Completed items
- Retirement of the 4 circular experiments — **PUBLIC**, `6ec4261`.
- P02 manifest-driven engine, P03/M4 independent blind gold set, P04 baselines table, **P05 A1–A5 evidence ladder (= R03 §5's "strategic reframe")**, P08 robustness/failure-injection, P09 latency — **off-release**, `b4ef009`.
- P06 C1 (Kimi-K2-Instruct via Featherless, archived, real pass¹ measurements) — **off-release**, gitignored archive.
- P06 C2 governance integration + 2 real P02 gaps found/fixed — **uncommitted, current worktree**; live run reportedly launched.
- `MODIFY` executing unmodified args now hard-errors — **off-release**, `e7110b4`.
- `gate_check.py` arity fix — **off-release**, `b4ef009` only.
- `SourceUnavailable`/missing-evidence handling in `decide.py`/`intercept.py` — **off-release, in two independent, divergent forms** (see §14).

## 13. Obsolete items
- R00's "nothing pushed" framing (partially — docs are now pushed, engineering is not).
- R03 §1/§2 fault-localisation probe and request-side evidence capture (superseded by the model-switch-plus-live-run outcome).
- CC-6 as literally written (base commit `42143cf` is stale; its goal is already substantially achieved).
- CC-9 as a thing to *run* (it already ran, as P05).
- CC-10 as a thing to *build* — see §16, likely duplicates `bench/verify_c2_joint_environment.py`.

## 14. Still-open items
1. **Two divergent, uncoordinated implementations of the same safety module** (`decide.py` evidence-null handling, `intercept.py` MODIFY/ALLOW dispatch, `idempotency.py`, `errors.py`) — one on `b4ef009` (P08, richer: typed `AmbiguousPolicyState`, 8 failure scenarios, `sqlite_source.py`), one on `f782d32`→`e7110b4` (built directly off `6ec4261`, narrower, its own `tests/test_cid_regressions.py`). **Neither package (first or second) saw this — both fix branches postdate the second package's authoring (17:44–18:48 vs. the package's 16:18–16:24 mtimes).**
2. `bench/report.py` hardcoded `MEASURED_GROUNDING_LOAD_MS`/`MEASURED_GROUNDING_CALL_MS`/`TYPICAL_PREDICATE_MS` — confirmed still present on **both** `6ec4261` and `b4ef009`. Genuinely unfixed everywhere.
3. No P06 evidence/provenance manifest (`docs/evidence/p06/`) on any branch — C1 (and soon C2) remain unretrievable by a third party.
4. No related-work doc, no threat-model doc, anywhere in git history on any branch.
5. No `docs/prereg/*` file anywhere.
6. Nothing from `b4ef009` (P02/P03/P04/P05/P08/P09) is merged to `main`/`origin/main`.

## 15. Unsafe prompts
None are unsafe *as designed* — every CC prompt in `R05` carries real guardrails and the ones most likely to be misused (CC-6, CC-11) explicitly forbid the dangerous move (wholesale merge, running past a zero-gate). The unsafe condition is **contextual, not textual**: running **CC-11** (new C1′/C2′ track) right now would collide with a live paid run and duplicate work already superseded by it. Running **CC-9** verbatim would silently reproduce P05 and could tempt a "second, slightly different" result to sit next to the validated one. Running **CC-5/CC-8** verbatim, unaware of the state found in §14, risks producing a *third* divergent fix or a backdated preregistration.

## 16. Surviving useful prompts — per-prompt classification

| Prompt | Classification | Condition for safe execution |
|---|---|---|
| CC-1 fault probe | OBSOLETE | none needed — model/provider capability already empirically settled by the switch + live C2 |
| CC-2 request-side evidence | OBSOLETE | same |
| CC-3 freeze manifest | **REQUIRES FRESH AUDIT, then SAFE** | rewrite scope to cover the real archived C1 (Kimi-K2) + C2 once its live run lands, not the stale "0/80 tool calls" framing |
| CC-4 bug-table verify | SAFE TO RUN LATER | none — read-only, low risk |
| CC-5 four one-line defects | **REQUIRES FRESH AUDIT before running** | must first read the two existing CID forks (§14.1) — running blind risks a third fork |
| CC-6 P11 reconciliation | SUPERSEDED / needs rewrite | base commit must become `6ec4261` (not `42143cf`); much of its goal is already met |
| CC-7 label independence (GATE C) | REQUIRES PUBLICATION DECISION | artifacts exist and are sound on `b4ef009`; absent from public `main` — decide which base to audit before running |
| CC-8 preregister A-ladder | **UNSAFE IF APPLIED TO P05** (backdating), SAFE for a genuinely future experiment | never write it as if it precedes P05's already-run result |
| CC-9 build+run A-ladder | DUPLICATE / ALREADY COMPLETED | do not run — publish P05 instead |
| CC-10 structural tool-call proof | LIKELY DUPLICATE | check `bench/verify_c2_joint_environment.py` (already does this) before running |
| CC-11 new track C1′ | **UNSAFE NOW** | do not run while C2's live run is in flight; revisit after its result is reviewed |
| CC-12 P10 related work | SAFE TO RUN LATER, genuinely needed | source citations from `R02_PRIOR_ART_V2.md`, not the stale `08`/`20` |
| CC-13 threat model | SAFE TO RUN LATER, genuinely needed | no dependencies |

## 17. Conflicts with forensic research audits

| Second-package claim | Forensic (`controlplane_audit_20260831`) finding | Current public fact | Final decision |
|---|---|---|---|
| AEGIS = `2603.12621`, not `2603.16938` | `08_prior_art_matrix.md` still cites `2603.16938` | Neither citation is published anywhere (no related-work doc exists) | R02's correction is right; apply it whenever `08`/`20`/CC-12 are next touched — no live conflict yet since nothing's published |
| "Nothing pushed since 29 Aug" | N/A | `origin/main = 6ec4261`, includes the retracted-figures docs | R00's premise is stale; treat `6ec4261` as current public truth |
| A1–A5 ladder is the untried "strategic reframe" | 06–09/10–15 files (G3 falsifiability, benchmark construct validity) implicitly call for exactly this design | P05 already built and ran it, off-release, `b4ef009`, 2026-08-30 | Completed — the open task is *publish*, not *build* |

## 18. Current engineering plan
1. Reconcile the two CID/MODIFY/SourceUnavailable forks (§14.1) into one canonical implementation — **this is the blocking node; see §23.**
2. Fix `bench/report.py`'s hardcoded latency constants (still open everywhere) or delete the chart, per the project's own "never hand-typed numbers" rule.
3. Port the `gate_check.py` arity fix from `b4ef009` into whatever becomes the integration branch.
4. Only after 1–3: plan a real merge order for `6ec4261 → {d9a6773,c35a60d} → {reconciled CID fix} → b4ef009's P02/P03/P04/P05/P08/P09 → uncommitted P06-C2 fixes` into `main`.

## 19. Current research plan
No new experiment (§21). Remaining research-track work is **publication of already-completed results** (P05 A-ladder, P03/M4 gold set) and **awaiting the live C2 outcome** before deciding anything about a "new track."

## 20. Current documentation/publication plan
1. `docs/evidence/p06/` provenance manifest (CC-3, rescoped) — still P0.
2. `docs/related-work.md` (CC-12), sourced from `R02_PRIOR_ART_V2.md`.
3. `docs/threat-model.md` (CC-13).
4. Once C2's live result is known: update `docs/experiment-audit.md`/README's "governance efficacy NOT ESTABLISHED (N=0)" language to the real attempted-write count.

## 21. Experiment decision

**NO EXPERIMENT JUSTIFIED NOW.**

The one experiment the package treats as most valuable (the A1–A5 ladder, R03 §5) is already executed and validated as P05. The other candidate (the fault-localisation probe, R03 §1) is moot: the P06 configuration was switched to Kimi-K2/Featherless and it produced real, non-zero task outcomes (pass¹ measurements exist), and a live C2 governance run is reportedly in progress right now — that run is a stronger, real-world answer to "does the tool-calling path work" than a synthetic 10-minute probe would be. Every other candidate in the package fails the task's own rejection criteria: P13-B measures an already-known N=0 defect; a new C1′/C2′ track would duplicate in-flight paid work; multi-seeding the deterministic A-ladder was explicitly rejected by P05 itself; a broader adversarial benchmark was explicitly dropped by R03 §8 as unwinnable this week.

## 22. A1–A5 status

All five arms: **EXECUTED** (off-release, `b4ef009`, `bench/evidence_ablation.py`, 2026-08-30). Isolation independently proven via a `sqlite3.connect` spy per arm; results were self-audited across 3 rounds before being reported (a withdrawn freshness claim, a corrected A3 fixture). No formal `docs/prereg/*` file exists, though the run used SHA-pinned, locked-pre-run fixtures, which substantively (if not nominally) satisfies preregistration's intent. Not merged to `main`; not independently/externally reviewed. Classified as **VALIDATED (internally, off-release)** rather than fully `VALIDATED` in the strictest sense, since that should mean independently checked, and only self-audit has occurred so far.

## 23. Highest-value remaining action

**Reconcile the two independent CID/MODIFY/`SourceUnavailable` implementations (`b4ef009`'s P08 module vs. `f782d32`→`e7110b4`) into one canonical version before merging anything else toward `main`.**

- **Why:** every other integration step (publishing the P05/P03 gold-set work, the evidence manifest, any future `main` merge) touches `controlplane/decide.py`, `intercept.py`, `errors.py`, `idempotency.py` — and there are currently two incompatible, independently-written versions of exactly these files, built by different sessions unaware of each other, both fixing overlapping fail-open bugs (missing-record handling, `MODIFY` executing unmodified args) in different ways.
- **What it closes:** removes the single biggest silent-data-loss risk in any future merge — picking either fork blind would either lose P08's richer 8-scenario failure-injection coverage or lose `e7110b4`'s explicit `Pending` exception for un-modified `MODIFY`.
- **Evidence it is needed:** directly observed via `git diff f782d32~1 f782d32` and `git diff 6ec4261 b4ef009` — both branches independently reintroduce `controlplane/errors.py` and `controlplane/idempotency.py` from scratch, because `f782d32` forked from `6ec4261` (which predates P08) rather than from `b4ef009`.
- **Cost/scope:** small — a read-and-choose reconciliation (1–2 hours), not new design; both forks are short, well-tested diffs.
- **Why other actions rank lower:** the evidence manifest (CC-3) documents already-frozen state and doesn't get worse by waiting a day; P10/threat-model are explicitly Phase-4/non-blocking by the package's own schedule; merging `b4ef009`'s larger feature set to `main` is itself blocked until this reconciliation happens, since P02/P04/P05/P08 all sit on top of the module this finding is about.

## 24. Final stopping point

This report. No file was edited, no branch touched, no experiment or benchmark run, no R05 prompt executed. All 8 findings above (§14, §16, §21, §23) are new information relative to both packages, produced entirely by committed-object git forensics, not by re-deriving anything either package already said.

## 25. Final reconciliation table

| File | Original purpose | Current validity | Already completed | Still useful | Obsolete/stale content | Unsafe content | Recommendation |
|---|---|---|---|---|---|---|---|
| R00 | Verify status doc claim-by-claim | Reasoning sound; evidentiary base partly stale | Its top recommendation (retire figures publicly) is now done | Its §2.1/§2.7 discipline (freeze integrity, named-commit-or-not-established) | "Nothing pushed since 29 Aug" | none | Re-anchor to `6ec4261`, keep the discipline |
| R01 | Self-correct AEGIS/LedgerAgent citations | Corrections verified sound | No — corrections not yet applied anywhere | Yes, once a related-work doc is written | none | none | Use its identifiers in CC-12, retire `2603.16938` from `08`/`20` |
| R02 | Corrected prior-art matrix | Valid, supersedes `08` cleanly | N/A (a document, not a task) | Yes — best current related-work source | none | none | Treat as canonical over `08_prior_art_matrix.md` |
| R03 | Gaps + strategic reframe | Reasoning sound; central "reframe" already executed as P05 | §5 (A-ladder) yes; §1/§2 (fault probe) moot | §4 (two-clock framing), §8 (drop-list) | §1/§2 fault localisation | none | Publish P05 instead of re-deriving it |
| R04 | Schedule, two tracks, gates | Structure sound, timeline stale (assumes Phase 2 undone) | Phase 1.2/1.4 and Phase 2 done | Gate discipline (Gate B/C) | Phase 0/3 as literally scheduled | none | Rebuild the calendar around what's actually done |
| R05 | 13 Claude Code prompts | Guardrails sound; several prompts target already-done or now-moot work | CC-6's goal (partial), CC-9, CC-10 (likely) | CC-3, CC-4, CC-12, CC-13 | CC-1, CC-2, CC-9-as-a-run-target | CC-11 (timing), CC-5/CC-8 (blind execution risk) | Run only CC-3 (rescoped), CC-4, CC-12, CC-13 next |
| R06 | Index of the package | Inaccurate as of today | N/A | Low, once corrected | "Nothing is pushed" framing | none | One-line update: `6ec4261` is public; P05/CID exist off-release |

---

**SECOND RESEARCH / EXECUTION-PLAN PACKAGE FINAL RECONCILIATION COMPLETE**
