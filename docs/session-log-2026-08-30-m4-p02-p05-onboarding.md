# Session log — M4, P07, P02 hardening, onboarding measurement, P04/P05 audit

**Date of work:** 2026-08-30 (all timestamps below are from this conversation).
**Repository:** `phase 2/controlplanestarter/controlplane`.
**Git HEAD throughout this conversation's work:** `8a48bf7ac4a20d8d57c9fc86ac47de6eb784971e` (unchanged from start to the final check performed in this conversation).

> **Important — read before trusting anything below as "current state."** This
> log was compiled at the end of a single continuous conversation. Immediately
> after that conversation's last check, the repository's HEAD moved to
> `b4ef009ab309372d1cd683145684a313696fa06a` and several files this
> conversation had verified and pinned as "P02-frozen" —
> `schemas/manifest.schema.json`, `controlplane/decide.py`,
> `tests/test_manifest_hardening.py` — were changed by what appears to be a
> **separate session**, working on unrelated P06 (tau2-bench C2) integration
> plus a "P02 minimal generic repair" (adding a `tau2_retail` resolver name
> and an `ORDER_STATUS_SUPPORTS_ACTION → status_supports_action` mapping).
> That other session left its own handoff at
> `docs/session-handoff-2026-08-31.md`; this log is entirely independent of
> it and was not informed by it. **Everything below describes the repo state
> as verified during this conversation's own work, up to HEAD `8a48bf7`. It
> is not a live/current-state document.**

---

## 1. M4 — human-label instrument repair and final close-out

**Problem found (first pass, pre-existing before this conversation):** a
prior human labeling pass (30 cases, κ = 0.5454545454545454, 20/30 exact
agreement) had an instrument defect — a corrupted/unresolvable
`call_order_id` could still render a complete-looking order-fact block,
letting the reviewer act on a fabricated record.

**Repair performed:**
- Preserved the first pass immutably at `bench/human_label_sample_pass1.csv` (SHA-256 `919627b0e3ec1b6fc5d5e71f46561ed767a7aea4fd2961717cf5684e5c0ab729`, verified byte-identical at every subsequent check in this conversation).
- Added `record_lookup_status` (FOUND/NO_MATCH) to the reviewer sheet; NO_MATCH rows now show no order-record columns at all.
- Wrote `docs/gold-set-annotation.md`, an explicit annotator rubric (ALLOW/BLOCK/ESCALATE/AMBIGUOUS definitions, no answers).
- Separated the deterministic generator's blank-template hash from the human-edited sheet's hash in `tests/test_gold_set_determinism.py` (previously conflated).
- Fixed 3 latent bugs in `tests/test_human_label_sample_blind.py` (a stale header assertion, a NO_MATCH row incorrectly required to match a real order record, an undefined-name crash) and added tests proving pass-1 immutability and non-copying into pass-2.
- Produced a fresh, blank, repaired second-pass sheet — same 30 case_ids, same order, `human_label`/`human_notes` blank.

**Second pass (completed by a human between tasks in this conversation), then verified:**
- n = 30, exact agreement = 24/30 (80.0%), **Cohen's κ = 0.7321428571428572**.
- 6 disagreements, all `human=BLOCK` vs `label.py=AMBIGUOUS`: `gs-145`–`gs-150` — all in the documented supervisor-discretion band (`bench/label.py:279-286`'s own generated rationale: *"BLOCK vs ESCALATE-to-supervisor is genuinely arguable"*).
- The 4 previous NO_MATCH disagreements (`gs-129/130/133/134`) now agree exactly: human ESCALATE, gold ESCALATE — direct evidence the instrument repair fixed what it targeted.
- A follow-up "residual ontology clarification" task independently re-verified the BLOCK-vs-AMBIGUOUS semantics from `bench/label.py` source directly and confirmed `docs/gold-set.md` already documents this neutrally and accurately — no further doc changes were needed.

**Final status:** `M4 — PASS WITH DISCLOSED SYSTEMATIC AMBIGUITY`.

**Files touched:** `bench/human_label_sample_pass1.csv` (new, immutable), `bench/human_label_sample.csv` (repaired schema, then human-filled), `docs/gold-set-annotation.md` (new), `docs/gold-set.md` (updated), `tests/test_human_label_sample_blind.py`, `tests/test_gold_set_determinism.py`.

---

## 2. P07 Fix 7 — final read-only verification

Verified `docs/round2-runbook-block0.md` (the captured Runbook §02 citation)
exists, computed its SHA-256 (`18a83378ee2a5fd416214235ad345644e5b947882b8ab436c0449daf3f14a8fa`,
no pinned hash existed elsewhere to compare against), and programmatically
diffed (whitespace-normalized) the "Safe reformulation" block quote in
`docs/ROADMAP.md:80` against the source paragraph — **byte-for-byte
identical** aside from markdown emphasis markup. Ran
`tests/test_deming_reformulation.py`: **13/13 passed**. Found and reported
(without fixing) a minor stale line-number citation inside the immutable
citation file's own provenance table.

**Final status:** `P07 FIX 7 — PASS`.

---

## 3. P02 hardening — manifest as a governance contract

Added, on top of the pre-existing P02 manifest-driven architecture:

1. **`schemas/manifest.schema.json`** — JSON Schema (draft 2020-12) for the manifest's *structural* contract only (types, closed `claim_kind`/`resolver` vocab, dotted-reference shape, `additionalProperties: false` on `claim_bindings` so no `query`/`exec` key can be smuggled in). Semantic validation stays authoritative in `controlplane/manifest.py`.
2. **`python -m controlplane.manifest lint <name>`** — a read-only CLI report (manifest id, schema version, governed tool, claims, config, tool-contract check, dead-binding scan, READY/INVALID).
3. **Cross-contract checks**, two genuinely new: a static AST-only tool-contract check (does each binding's `subject` match the governed tool's own declared parameters — a real gap `bindings.validate_ref` alone can't see) and a textual dead-binding scan — both correctly fall back to `"not statically checkable"` rather than overclaiming.
4. **`schema_version: 1`** required on all 3 shipped manifests; unsupported/missing version rejected at load.
5. **28 new tests** (`tests/test_manifest_hardening.py`), plus docs in `docs/architecture.md` and `docs/policy-manifest.md`.

**Scope disclosure:** 189 new production lines (target ≤100), 526 total changed lines excluding schema/generated text (target ≤150) — both guidelines exceeded and disclosed transparently, not hidden. A dedicated **P02 final scope adjudication** task independently re-derived these exact figures via git's index/worktree split (since nothing was committed at a clean boundary), ran a minimization audit (found only ~1–3%-scale trims, e.g. argparse→manual parsing; nothing material), and judged the overage a **justified scope exception** — four required features with an 8-item cross-contract checklist and 15 required proof points is inherently more than 150 lines of honest implementation.

**Final status:** `P02 HARDENING — PASS WITH DISCLOSED SCOPE EXCEPTION` (confirmed twice: once at completion, once at independent adjudication).

**Files touched:** `schemas/manifest.schema.json` (new — since modified by the other session, see banner above), `controlplane/manifest.py` (extended), `manifests/{servicing,knowledge_assistant,discount_approval}.yaml` (+`schema_version: 1`), `requirements.txt` (+`jsonschema>=4.20`), `tests/test_manifest_hardening.py` (new — since modified by the other session), `docs/architecture.md`, `docs/policy-manifest.md`.

---

## 4. Onboarding-time measurement — service credit approval

**Purpose:** measure, mechanically and reproducibly, how long it takes to
onboard one genuinely new governed use case onto the final P02-hardened
architecture.

**Locked use case:** `service_credit_approval` — a goodwill service credit
for a delivery/service complaint (no return, no delivery-window gating —
distinct from every existing manifest). Governed tool:
`approve_service_credit(order_id, amount_paise, currency)`. Reuses the
`orders` and `authority` resolvers and the `ORDER_BELONGS_TO_CUSTOMER` /
`AMOUNT_NOT_EXCEEDING_ORDER` / `AMOUNT_WITHIN_AUTHORITY` claim kinds — zero
new resolvers, zero new claim kinds. Independence verified by a repo-wide
grep (zero pre-existing matches) before locking.

**Frozen acceptance sequence (pre-registered before START):**
1. `pytest tests/test_service_credit_approval.py -v`
2. `pytest tests/test_engine_is_use_case_agnostic.py -v`
3. `sha256sum -c` over 9 protected files
4. `git diff --check`

**Timing:**
- START: `2026-08-30T15:33:51.080Z` (first action: `Write manifests/service_credit_approval.yaml`)
- END: `2026-08-30T15:35:30.599Z` (immediately after all 4 acceptance commands passed)
- **Elapsed: 99.519 seconds (1 minute 39.519 seconds)** — computed directly, not estimated
- All 4 acceptance commands passed on the first run; no retries, no debugging cycle

**Scope:** manifest YAML 56 lines, predicate graph 24 lines, tool schema 18 lines (inside the agent file), agent/demo file 153 lines, test file 118 lines. **New use-case-specific Python in `controlplane/`: 0 lines.**

**Verification (two independent passes, both in this conversation):**
- Re-ran all 4 frozen acceptance commands — identical results.
- Independently recomputed the elapsed time from the raw timestamps: 99.519 s, exact match.
- Cross-checked against **filesystem mtimes** (converted IST→UTC) as evidence independent of the conversation transcript: manifest 15:34:00.972Z, graph 15:34:07.108Z, agent 15:34:44.593Z, test 15:35:03.214Z (all inside the START–END window), and `docs/onboarding-measurement.md` 15:36:38.103Z — **after** END, consistent with "write the report only after END."
- Re-hashed all 9 protected artifacts and the P02-relevant file set — all unchanged.

**Final status:** `ONBOARDING MEASUREMENT — VERIFIED AND FROZEN` (confirmed at three separate points in this conversation: initial completion, a dedicated verification task, and a final launch-gate re-verification).

**Buyer-facing claim actually supported:** *"In our prototype measurement, service credit approval was onboarded in 99.5 seconds, with 0 new use-case-specific Python lines added to the shared controlplane engine."* Explicitly **not** claimed: that any tool can be onboarded this fast, that every future use case needs zero Python, that this reflects human onboarding time, or that P02 hardening specifically caused the speed (no pre-hardening baseline was measured for comparison).

**Files touched:** `agents/service_credit_agent.py`, `manifests/service_credit_approval.yaml`, `manifests/graphs/service_credit_approval.json`, `tests/test_service_credit_approval.py`, `docs/onboarding-measurement.md` — all new, none modified since.

---

## 5. P04/P05 prior-art and methodology audit

**Purpose:** a research-integrity audit against primary sources, repairing
only concretely-proven defects.

**Primary sources read directly** (via live fetch of the arXiv HTML, not
memory or secondary summaries):
- **LedgerAgent** (arXiv:2606.20529) — confirmed its verifier checks only
  state the agent itself already observed via prior tool calls, never an
  external store at decision time; confirmed its control-variable discipline
  ("same policy, tools, decoding settings, number of model calls"); 298
  tasks across 4 domains, 4 trials/cell for pass^k, mixed results across
  domains (one domain got *worse* under the treatment, honestly not
  cherry-picked here).
- **AEGIS** (arXiv:2603.12621) — confirmed 6/500 = 1.2% FPR, but the sampling
  frame, procedure, population size, and time window are all **not
  specified** in the paper, and the "six cases" share **one** documented root
  cause (OR-predicate SQL flagged as injection-like), not six distinct ones.
- **OAP** (arXiv:2603.20953) — confirmed **no comparable benign-call FPR
  experiment exists** in this paper at all.

**P04 finding:** a full-repo search found **no existing claim anywhere**
comparing our FPR to AEGIS's — AEGIS is cited in this repo only for latency
(P09), already carefully caveated as "not like-for-like." Nothing needed
fixing. `docs/p04-prior-art.md` was written as a **preventive** reference
(so nobody writes an unsupported FPR comparison later), not a correction.

**P05 finding:** the existing A1–A5 evidence-source ablation was audited
against a strict validity matrix (can A3 access what A5 can; can A5 access
the trace; can A4 genuinely diverge from A5; are gold labels independent of
every arm and of the perturbation; etc.) — **every property verified
directly from source code** (`bench/evidence_ablation.py`,
`bench/baselines.py`), not from the report's own prose. A3 provably opens
zero databases and is source-token-banned from referencing any other
channel; A4 queries a genuinely separate replica file and is proven capable
of diverging from A5 at ≥14-day replication lag (11.4-point accuracy drop);
A5 is literally the same Python object as P04's B5 (no override). All 43
P04+P05 tests pass. **No defect was found; no repair was made; the existing
P05 results were not regenerated.** `docs/p05-methodology-audit.md` records
the full audit trail.

**Final status:** `P04/P05 — PASS WITH DOCUMENTED METHODOLOGY`.

**Files touched:** `docs/p04-prior-art.md` (new), `docs/p05-methodology-audit.md` (new). No experiment code, no report, no result file was changed.

---

## Summary table — every task, every final status

| # | Task | Final status |
|---|---|---|
| 1 | M4 instrument repair | fresh blank sheet prepared for pass-2 |
| 2 | M4 final close-out | **M4 — PASS WITH DISCLOSED SYSTEMATIC AMBIGUITY** |
| 3 | M4 residual ontology clarification | status retained, no changes needed |
| 4 | P07 Fix 7 verification | **P07 FIX 7 — PASS** |
| 5 | P02 hardening | **P02 HARDENING — PASS WITH DISCLOSED SCOPE EXCEPTION** |
| 6 | P02 scope adjudication | verdict confirmed independently |
| 7 | Onboarding measurement | **ONBOARDING MEASUREMENT — COMPLETE** |
| 8 | Onboarding verification | **VERIFIED AND FROZEN** |
| 9 | P04/P05 audit | **P04/P05 — PASS WITH DOCUMENTED METHODOLOGY** |
| 10 | Final onboarding launch-gate re-verification | **VERIFIED AND FROZEN** |

## Protected artifacts confirmed unchanged throughout (every task, every check)

`bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`,
`bench/human_label_sample_pass1.csv`, `reports/baselines.md`,
`reports/evidence-ablation.md`, `reports/robustness.md`,
`reports/latency.md`, `reports/summary.json` — SHA-256 verified identical at
every checkpoint across this entire conversation, right up through HEAD
`8a48bf7`.

## Open item for the user

The other session's `docs/session-handoff-2026-08-31.md` and the file
changes it describes (P06/tau2-bench C2, plus a "P02 minimal repair" that
touches `controlplane/decide.py` and `schemas/manifest.schema.json`) were
**not reviewed, verified, or endorsed by this conversation** — they simply
weren't part of it. If you want those changes cross-checked against
everything summarized here, that needs a fresh, explicit task.
