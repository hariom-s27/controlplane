# Session log — P01, P02, P07 Fix 7

Summary of the work done in this chat session, written so it can be committed
and pushed to GitHub alongside the code changes it describes. Covers three
pieces of work, in the order they happened. Other task files (P03–P06, P08)
show up as changes in the working tree from other sessions and are **not**
covered here — this log is scoped to what this conversation actually did.

---

## 1. P01 — Remove or rebuild the four circular experiments

**Spec:** `phase 2/doc/task/P01-fix-circular-experiments.txt`

An audit found that four of the project's five self-reported experiments
could not fail — their headline numbers were forced by how the test inputs
were constructed, not by anything the system did.

| Experiment | Was | Defect | Fix |
|---|---|---|---|
| Confusion matrix (Exp 5) | accuracy 1.000 | Gold cases were generated *by* `decide()`, then scored *against* `decide()` on the same inputs | Generator deleted. `bench/seb1_exp5_confusion_matrix.py` now raises `SystemExit` — **BLOCKED** until task P03 supplies a held-out gold set |
| order_id cross-validation (Exp 3) | 100% with check / 75% without | Gold label was *defined as* "resolves to the distractor"; the detector recomputed the same boolean from the same fields | Rebuilt: true order id recorded at construction time in a held-out file (`bench/exp3_ground_truth.jsonl`) the checker (`bench/exp3_checker.py`) never opens (AST-asserted). Added "hidden" distractors the check can't see. New numbers: **0.92 with the check, 0.755 without** — genuinely capable of failing |
| Mutation score | 1.000, all 6 operators 1.000 | Operators were derived from the same 6 checks `decide()` implements | Rewritten (`bench/mutation.py`) so operators come from the **spec** (tool JSON schema + `manifests/servicing.yaml`), including elements the gate can't enforce. New score: **0.60** (9/15 operators catchable), full per-operator breakdown |
| Bias probe | "no detectable difference" | Group label (`rng.choice(["A","B"])`) was never passed to `decide()` — no causal path, so it could only ever pass | **Deleted.** Replaced with `tests/test_no_protected_attributes.py` (structural: `decide()` has no protected-attribute parameter) + `bench/bias_proxy_probe.py` (clearly-labelled proxy analysis) + a paragraph in `docs/limitations.md` |
| Coverage ratio | 1.0 | Every `ClaimKind` a governed tool can emit is C1/C2/C3 by construction, so the ratio was deterministically 1.0 | Retired as a reported number; per-tier claim **counts** kept as descriptive telemetry; "every ClaimKind is mapped" is now an enforced invariant in `tests/test_ladder.py` |

**Deliverables:** `docs/experiment-audit.md` (line-by-line why each was circular),
`docs/retired-figures.md` (what was removed and what replaced it),
`docs/limitations.md` (bias framing), rewritten `bench/mutation.py`,
`bench/exp3_corpus.py` / `exp3_checker.py`, deleted `controlplane/bias_probe.py`.

**Result:** 91 tests passing at the end of P01 (baseline was 77 before the task).

---

## 2. P02 — Make evidence builders manifest-driven

**Spec:** `phase 2/doc/task/P02-manifest-driven-evidence.txt`

**Problem:** `intercept.py::_EVIDENCE_BUILDERS` was a Python dispatch table
keyed by manifest name — adding a use case meant writing Python in the
engine, which falsified the project's central "same engine, different
manifest" governance claim.

**Findings before changing anything:** six places in `controlplane/`
branched on which use case was running: `_EVIDENCE_BUILDERS`,
`extract._CLAIM_KINDS_BY_TOOL`, `extract._POLICY_ID_FOR_KIND`,
`registry._RESOLVER_FOR_KIND`, `compensation._TABLE`, and the predicate
graph's location (inside `controlplane/`, picked by a hardcoded
`"servicing"` default).

**What changed:**
- **New `controlplane/bindings.py`** — the declarative evidence-binding
  schema: `resolve_ref` (rejects any reference to a `claimed_*` field at
  load time — the architecture's one rule), `build_predicate_payload`
  (replaces every hand-written builder function), `claim_specs`.
- **`controlplane/manifest.py`** — validates every manifest at load:
  unknown resolver, unknown claim kind, malformed reference, missing
  predicate graph all fail loudly, naming the binding and the reason.
- **`controlplane/registry/__init__.py`** — `RESOLVER_BY_NAME`, a
  name→resolver registry the binding's `resolver:` field looks up, instead
  of a per-ClaimKind table.
- **`controlplane/intercept.py`, `extract.py`, `predicates/__init__.py`,
  `compensation.py`** — all now read from the manifest instead of branching
  on a use-case string. `compensation_for()` now takes the manifest, not the
  tool name. Predicate graphs moved from `controlplane/predicates/graphs/`
  to `manifests/graphs/` (data, not engine code).
- **`tests/test_engine_is_use_case_agnostic.py`** — the CI check: fails if
  any `.py` file under `controlplane/` contains a manifest name or tool name
  as a string literal in executable code. Forbidden tokens are discovered
  from `manifests/*.yaml`, so it also guards every future use case.
- **Third use case, added as proof:** `manifests/discount_approval.yaml` +
  `manifests/graphs/discount_approval.json` + `agents/discount_agent.py` —
  a goodwill-discount/store-credit approval, reusing the `orders` resolver
  and existing `ClaimKind`s (14-day window vs servicing's 7, ₹5,000 ceiling
  vs ₹25,000). **Added with zero lines changed under `controlplane/`.**
  `tests/test_third_use_case.py` proves it through the real gate.

**Behaviour preserved:** golden receipts for the two pre-existing use cases
diffed identical (knowledge_assistant) or differing only in two cosmetic
text fields (servicing: an evidence `query` string reflecting the flattened
manifest schema, and one `root_cause` label genericised from
`outside_refund_window` → `outside_window` so the engine names no domain).
No verdict or intervention changed.

**Line-count honesty check** (the task's own ~250-line stop condition): net
change to `controlplane/` was **≈ +130 lines** — one new ~122-line module
plus a near-even rewrite of 12 existing files (≈271 insertions / ≈263
deletions, mostly line-for-line). Reported transparently rather than
redefined to force a pass; recommended keeping the refactor since it
completed and works, rather than falling back to the task's "Option B"
(quote a ~40-line adapter size and leave the dispatch table).

**Deliverables:** `docs/policy-manifest.md` (binding schema + why the
roadmap's `query`/`params` sketch was dropped), `docs/architecture.md`
(the onboarding-time measurement: ~30 minutes to add a use case, 0 lines of
`controlplane/` Python), `.github/workflows/ci.yml`.

**Result:** 117 tests passing at the end of P02.

---

## 3. P07 Fix 7 — the Deming sentence / OC-curve reformulation

**Spec:** `phase 2/doc/task/P07-quick-fixes.txt`, Fix 7.

**The problem:** the project's sampling argument attributed to Deming the
claim that correlated defects leave no optimal sample size — inverting the
actual theorem's assumption set. Deming's kp rule / all-or-none inspection
criterion is proved for a process **in statistical control**, not for
correlated defects. `docs/ROADMAP.md` said to replace it with "the Runbook
§02 reformulation" — but that runbook was not in the repository, so Fix 7
was blocked.

**Exhaustive search performed** (current repo, full git history — 3
commits, no branches/tags/stashes/deleted files, `git log -S`/`-G` pickaxe
across every blob, the entire parent project tree including `phase 1/`,
filenames, `.pptx`/`.pdf` text extraction, the AIC zip): the authoritative
reformulation text was **not found anywhere locally**. `docs/ROADMAP.md`
only *referenced* it, pointing at an external file
`controlplane-round2-runbook.md` and a "Web version" artifact URL.

**Found:** that URL turned out to be a different artifact (the Build Spec,
i.e. ROADMAP.md itself). Listing the user's own published artifacts
surfaced the actual one — **"ControlPlane Round 2 Runbook"**
(`claude.ai/code/artifact/7337b733-8db8-4126-8f57-4d0a9ff48e23`, private,
owned by the user). Its **§02**, transcribed character-for-character from
the page's raw HTML source (not a model's rendering of it), contains:

> **Safe reformulation, which survives either reading:** Acceptance sampling
> rests on operating-characteristic curves, and OC curves assume binomial or
> hypergeometric draws at a constant proportion nonconforming — i.i.d.
> defects from a process in statistical control. A superseded policy
> document is a textbook *assignable cause*: it produces the same error on
> every retrieval that touches it, which violates the i.i.d. assumption
> directly rather than merely straining it. And Deming's own inspection
> criterion says that even in the well-behaved stable case, the
> cost-optimal policy is zero or everything — never the 1–5% that
> contact-centre QA actually runs. **Sampling theory says sampling is the
> wrong tool here, and it says so twice, for two different reasons.**

**What changed** (all in the phase-2 repo — nothing in the phase-2
controlplane repo actually asserted the prohibited claim; only ROADMAP's
own *fix-instructions* mentioned "Deming, 1986", correctly, as something to
avoid):
- **New `docs/round2-runbook-block0.md`** — the full Runbook §02 (Wix +
  Reddy et al. distinction paragraph, and the Deming subsection with the
  reformulation above), captured verbatim with full provenance, so the
  citation is no longer missing from the repo.
- **`docs/ROADMAP.md`** — 4 rows rewired from "use the Runbook §02
  reformulation" (pointing at nothing) to embedding the verbatim text and
  pointing at the new file.
- **New `tests/test_deming_reformulation.py`** (12 tests) — guards that the
  capture contains the reformulation verbatim, that ROADMAP points at it,
  and that no shippable doc asserts the retired kp-rule theorem framing or
  cites Deming with a bare year-only attribution.

**Not changed:** the Round-1 deck sources and content specs under
`phase 1/` (not a git repo, not the P07 target, some of it an append-only
decision log) still carry the old wording in several places — enumerated in
full in-chat with exact file:line, ready to fix with the same verbatim text
if/when the Round 2 deck is authored from them.

**Result:** 169 tests passing (full suite) at the end of this piece of work.

---

## Where things stand

- **Tests:** 169 passing, 0 failing, as of the last full run this session.
- **CI:** `.github/workflows/ci.yml` runs the full suite plus the
  use-case-agnostic engine check on every push/PR.
- **Uncommitted:** everything above is in the working tree of
  `phase 2/controlplanestarter/controlplane/` (a git repo with 3 commits on
  `main`, no remote push has been made from this session). Nothing here has
  been committed or pushed — that's a deliberate choice pending your go-ahead.
- **Known blockers left for later tasks:** SEB-1 Exp 5 (confusion matrix)
  stays `BLOCKED` until P03 delivers a held-out gold set; the phase-1 Deming
  wording is enumerated but unedited.
