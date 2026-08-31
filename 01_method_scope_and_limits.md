# Method, scope, and the limits of this audit

## What was actually inspected

| Item | Value |
|---|---|
| Remote | `https://github.com/hariom-s27/controlplane.git` |
| Clone time | 2026-08-30 ~23:32 IST |
| `main` HEAD | `42143cf55fd7e314a735f5e05807519b8e6efb44` — "Add multi-account API key fallback for Featherless and Firecrawl", 2026-08-29 16:43 +0530 |
| Other ref | `origin/p03-m4-blind-human-label-sheet` @ `8a48bf7`, 2026-08-30 17:44 +0530 |
| Full history | 4 commits: `29936c4` (2026-08-28, scaffold) → `c653b7f` (2026-08-29, "Implement S4-S18") → `42143cf` → `8a48bf7` (branch only) |
| Tracked files on `main` | 92 |
| Author | one: `Hariom Singh <harioms22@iitk.ac.in>` |

> **Historical-state qualifier:** This audit was performed at `main` @
> `42143cf55fd7e314a735f5e05807519b8e6efb44`. That commit is now an ancestor
> of public `main` @ `6ec4261d374904f55bf5dff1a9855854f1b94819`.
> The later public commit reconciled the README and audit disclosures but did
> not change the core code paths analyzed here, so the relevant findings remain
> applicable unless explicitly superseded. Branch observations, including
> `8a48bf7`, describe refs visible at audit time; they do not establish that
> later or off-release work is merged, current, or public.

## §1A repository-history discipline — what this audit can and cannot see

| State | Visible here? | Consequence |
|---|---|---|
| Committed (all branches) | **YES** | All historical claims below are anchored to a commit SHA. |
| Staged | **NO** | A clone carries no index from the author's machine. |
| Unstaged / untracked / current-worktree-only | **NO** | Anything the author has locally but has not pushed is invisible. |
| Generated artifacts | **NO, by design** | `.gitignore` excludes `data/*.db`, `data/stale_index/`, `reports/`, `decisions.jsonl`, `decisions_privileged.jsonl`. |

**Every statement in this audit is therefore scoped to the pushed repository.** Where the brief's premise refers to artifacts not present, the finding is stated as `EXPLICITLY ABSENT FROM ALL COMMITS` — which is a stronger and narrower claim than "does not exist".

The dominant history-discipline finding: **`c653b7f` is a single commit containing S4 through S18** — extraction, ladder, registry, predicates, grounding, decide, receipt, telemetry, manifests, second agent, PII, bias probe, invariants, mutation, both benchmarks, the reviewer console and the report generator. Almost no chronology inside the build is reconstructable. `git log --all -S "unreliable_and_would_violate"` and `git log --all -G "SOURCE_UNRELIABLE > CONTRADICTED"` both return only `c653b7f`.

→ For §10 (the M5 bug): **EXACT COMMIT NOT RECONSTRUCTED.** The pre-fix version of `decide()` never existed in any commit. See `06_G3_falsifiability.md`.

## The §0 read-only constraint, and what it costs this audit

§0 forbids running benchmarks or experiments. This was honoured: **no `pytest`, no `make bench`, no `bench/*.py`, no agent, no provider call, no DB build.** The clone is in an isolated ephemeral container and could not have touched the author's worktree in any case.

The cost is precise and worth stating rather than hiding:

- Every numeric claim in this audit sourced from the repository is labelled **REPORTED** (the repo asserts it) or **DERIVED** (this audit computed it analytically from the generator source), never **MEASURED**.
- Where a number is labelled **DERIVED**, the derivation is shown in full in `13_quantitative_estimand.md` so a reader can check it by hand. In every case the derivation is short, because the generators are short — which is itself the finding.
- **This audit did not need to run anything to conclude that the headline numbers are tautologies.** That conclusion follows from reading ~120 lines of generator code. Running them would confirm, not establish.

If independent re-execution is wanted, say so and it takes minutes; §0 currently forbids it.

## §1B primary-source discipline — what was researched fresh

Today is 2026-08-30. The relevant literature is dated Mar–Jul 2026, i.e. **after this auditor's reliable knowledge cutoff (2026-05-05)**. Nothing about it was answered from memory. Every literature claim below was fetched during this audit and carries a URL, a date, and the exact element relied on. Where only an abstract or partial render was retrievable, the finding says so.

Sources fetched and their status are listed in `08_prior_art_matrix.md` and `07_G4_agentltl_primary_source.md`.

## §1E no-false-consensus

No sentence in this audit says "the literature generally agrees", "prior work shows", "this is standard" or "reviewers would expect" without either (a) a named source, or (b) the tag **INFERRED (reviewer-style expectation, not published evidence)**.

## §1F contradiction handling actually invoked

Three substantive repository-internal contradictions were found and are preserved with both statements, ranked by the §1F priority `source > tests > frozen evidence > reports > README`:

| # | Statement A | Statement B | Resolution |
|---|---|---|---|
| C-1 | `README.md`: "`make report` regenerates `reports/` … **never from hand-typed numbers**" | `bench/report.py` lines 41–43: `MEASURED_GROUNDING_LOAD_MS = 13_209.0`, `MEASURED_GROUNDING_CALL_MS = 109.8`, `TYPICAL_PREDICATE_MS = 0.6` — the entire promotion-cost chart is drawn from these three constants | **Source wins.** README claim is FALSE as written. The file's own comment concedes they are hand-carried. |
| C-2 | `docs/gold-set.md` §5 (branch `8a48bf7`, as observed at audit time): "`bench/seb1_exp5_confusion_matrix.py::run()` raises `SystemExit`" | At that audit point, `git diff origin/main origin/p03-m4…  -- bench/seb1_exp5_confusion_matrix.py` was **empty**; `run()` on the branch was byte-identical to main and returned a matrix | **Source wins for the audited ref.** The doc described an intended state, not the branch's code. The branch's post-audit state was not reverified for this publication correction. |
| C-3 | `controlplane/registry/entitlements.py` docstring: "nothing calls it yet since … the knowledge-assistant agent doesn't exist" | `agents/knowledge_assistant.py` exists and `controlplane/registry/__init__.py` routes two ClaimKinds to `EntitlementsResolver` | **Source wins.** Stale docstring surviving the S13 build. Cosmetic, but it is a docstring asserting a fact about the system. |

## What this audit is not

- It is **not** a security review of a deployed system. There is no deployment.
- It does **not** evaluate the Accenture submission on the challenge's own criteria. Against those criteria the artifact looks strong. The brief asked for a *research* audit, and research standards are what is applied.
- It makes **no** claim about work the author holds locally.
