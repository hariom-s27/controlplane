# M4 chat handoff — human-agreement sample, instrument repair, pass 1 + pass 2

Generated from the project conversation covering task **M4** (P03 human-label
validation) end to end: building the blind sample, fixing a BOM bug, auditing
the first labeling pass, and repairing the annotation instrument. This is a
repository-facing summary so the work in this conversation is visible in
GitHub — it is not a system-prompt dump and no credentials are included.

---

## 1. Task M4 — build a genuinely blind human label sheet

**Ask:** `bench/human_label_sample.csv` (30 P03 gold-set cases for human
review) exposed a `slice` column whose name stated the intended verdict for
five of seven construction slices — a direct answer leak. Preserve the same
30 cases; remove every construction/answer-bearing field; keep only what a
real refund reviewer would legitimately see; never touch `bench/gold_set.jsonl`
or `bench/ground_truth_holdout.jsonl`; make `bench/agreement.py` withhold
Cohen's kappa until all 30 rows are labelled.

**What was done:**

- Audited every column of the sheet. Only `slice` was answer-bearing; every
  other column (`case_id`, `session_customer_id`, `call_order_id`,
  `refund_amount_paise`, order facts, policy text, `agent_justification`) was
  legitimate reviewer-visible context and was kept.
- Removed `slice` from `bench/human_label_sample.csv` and from
  `gold_set_build.py::_write_human_sample()` (the generator), so regenerating
  the blank template reproduces the fix.
- Verified the **same 30 `case_id`s**, same order, same seed (`SEED =
  20260814`) — all 10 `ambiguous_under_policy` cases plus the same 20 others.
- Confirmed `bench/gold_set.jsonl` and `bench/ground_truth_holdout.jsonl`
  byte-identical before/after (`09deaecb…d48c8e` / `204e4a8e…a24e3cb`).
- Rewrote `bench/agreement.py` to join on the opaque `case_id` →
  `bench/gold_set.jsonl` → `gold_label` (never the holdout, never row
  position), and to refuse a Cohen's kappa until every one of the 30 rows has
  a `human_label`.
- Updated `docs/gold-set.md` and the determinism pin in
  `tests/test_gold_set_determinism.py` (the human-sample hash necessarily
  changed when the leaking column was removed).
- Added `tests/test_human_label_sample_blind.py` proving: exact row count,
  exact case-id set/order, no leaking column, blank `human_label` /
  `human_notes`, case-id-based join, no holdout access, no system
  prediction generated.

**Result:** a blind, blank 30-row sheet, committed as `8a48bf7 P03/M4: make
the human label sheet genuinely blind`.

---

## 2. Git help — creating the M4 branch and commit

Walked through creating branch `p03-m4-blind-human-label-sheet` and staging
exactly the six M4 files (not the large set of unrelated pre-existing
modifications already sitting in the working tree from other sessions).
PowerShell doesn't support `\` line continuation the way bash does, so the
multi-line `git add` / `git commit -m ... -m ...` commands had to be
collapsed to single lines before they would run. Also separately answered:
`git add -A` would additionally sweep in P01/P02/P04/P05/P08/P09 work from
other sessions, including intentional deletions
(`controlplane/bias_probe.py`, `controlplane/mutation.py`,
`controlplane/predicates/graphs/*.json` → moved to `manifests/graphs/`) —
flagged so it wasn't committed blind.

---

## 3. BOM compatibility fix

**Symptom:** after a human filled all 30 labels and re-saved the CSV, the
file gained a UTF-8 BOM. `python bench/agreement.py` raised `KeyError:
'case_id'`, because under plain `encoding="utf-8"` the BOM attaches to the
first header field, so `csv.DictReader`'s first key becomes `"﻿case_id"`.

**Fix:** changed the two human-sheet reads in `bench/agreement.py`
(`_sheet_case_ids()`, `_human_labels()`) from `encoding="utf-8"` to
`encoding="utf-8-sig"` — strips a BOM if present, no-op otherwise. No change
to join logic, label vocabulary, kappa math, or holdout isolation.

**Regression test added:** `test_agreement_tolerates_a_utf8_bom_in_the_sheet_header`
— writes a temp BOM-prefixed sheet, shows the plain-`utf-8` read produces the
broken key and the `utf-8-sig` read produces the correct one, then confirms
`agreement.py` joins all 30 cases and computes a kappa against it.

**First real result once unblocked:**

```
n_expected: 30   n_human_labels: 30   complete: true
n_compared: 30   n_agree: 20   percent_agreement: 0.667
cohens_kappa: 0.5454545454545454
```

10 disagreements, all the annotator choosing **BLOCK** where `label.py`
returned something softer (`ESCALATE` or `AMBIGUOUS`) — see the audit below.

Human labelling had, by construction, already invalidated a few of the M4
tests that assumed a blank sheet (`test_human_label_blank_for_every_row`,
the pinned determinism hash, etc.). These were updated to be lifecycle-aware
(blank **or** valid-vocabulary, isolated fixtures for the kappa-gating
tests) without weakening any blindness assertion — documented in
`docs/gold-set.md` §6 and the updated `tests/test_gold_set_determinism.py`
pin.

---

## 4. Read-only disagreement + ontology audit (pass 1)

**Question:** M4's own acceptance bar was ">2 disagreements → STOP +
investigate." Ten disagreements meant M4 was not closed. This task was
explicitly read-only — diagnose, do not fix, do not touch any label or the
gold set.

**Findings, condensed:**

- **Ontology (from `controlplane/decide.py`, `bench/label.py`,
  `docs/ROADMAP.md`):** the gold label is the *recommended gate
  intervention*. **BLOCK** = a reliable record fact contradicts the action
  (stop it). **ESCALATE** = a required fact/record can't be verified (hold it
  for a human) — `docs/ROADMAP.md`: *"'escalate' is weaker risk coverage than
  'block'."* **AMBIGUOUS** is gold-set-only vocabulary meaning *the P03
  authors' own reading of the policy text doesn't settle the case* — not a
  real gate verdict.
- **4 disagreements** (`gs-129/130/133/134`, the `corrupted_or_missing_record`
  slice): the tool call's `order_id` didn't resolve to any record.
  `label.py` → ESCALATE ("can't verify"). The human → BLOCK, reasoning from a
  fully-populated order-fact block the sheet *also showed* for that row
  (delivery date, total, customer — all pulled from the real, hidden
  underlying order for construction reasons). **This was a genuine instrument
  defect**, not a bad human judgement — the sheet made an unresolvable
  record look resolvable.
- **6 disagreements** (`gs-145`–`gs-150`, the 8–14-day
  supervisor-discretion band): `label.py` → AMBIGUOUS by its own documented,
  acknowledged coin-flip (`docs/gold-set.md` §3 literally says *"genuinely
  arguable whether ... BLOCKed outright or ESCALATEd"*). The human → BLOCK,
  one of the two answers the docs call reasonable. **This is expected,
  documented disagreement, not a defect.**
- 16/16 agreement on every case outside those two slices — the human's
  ALLOW/BLOCK model matched `label.py` exactly on every clean contradiction.
- **Determinism-contract finding:** the BOM fix had put the *human-filled*
  CSV's hash into the "determinism" pin (`test_gold_set_determinism.py`),
  conflating "the generator is deterministic" with "the annotator's file is
  byte-frozen." Flagged for repair, not fixed in the audit itself.

**Verdict returned: BLOCKED** (not PASS, not FAIL) — the *instrument*
(no annotator rubric, misleading NO_MATCH presentation, undefined AMBIGUOUS
scoring convention) needed repair before the kappa number could be
interpreted. Next actions specified: write a rubric; add a neutral
`record_lookup_status` field and stop showing hidden record facts for
unresolvable ids; decide the AMBIGUOUS scoring convention *before* a second
pass; separate the two determinism artifacts; re-run.

Nothing was modified in this task (verified `git status --short` identical
before/after).

---

## 5. Instrument repair + fresh pass-2 sheet

**Ask:** implement the audit's fixes, but strictly *instrument repair only* —
produce a fresh **blank** sheet for an independent second human pass; do not
label it; do not compute a second kappa; preserve the first pass as immutable
history.

**What was done:**

1. **Preserved pass 1** byte-for-byte to `bench/human_label_sample_pass1.csv`
   (verified identical SHA-256, `919627b0…c0ab729`, before/after — never to
   be edited again).
2. **Wrote `docs/gold-set-annotation.md`** — an annotator rubric with
   operational definitions of ALLOW / BLOCK / ESCALATE / AMBIGUOUS, the
   explicit rule *"`record_lookup_status = NO_MATCH` ⇒ ESCALATE, not BLOCK,"*
   and the AMBIGUOUS scoring convention — no case-specific answers, no gold
   labels, no construction/holdout detail.
3. **Repaired `bench/gold_set_build.py`**:
   - `_write_human_sample()` now resolves each row's `call_order_id` directly
     against the public `orders.db` (no longer reads the holdout at all for
     this purpose) and adds a `record_lookup_status` column: `FOUND` /
     `NO_MATCH`.
   - For `NO_MATCH` rows, the three order-record columns
     (`order_total_paise`, `order_customer_id`, `order_delivered_at`) are
     left **blank** instead of showing the hidden real order's facts — the
     exact defect the audit found.
   - `build()` gained an `out_dir` parameter so determinism can be proven by
     building into a temp directory, and `regenerate_blank_human_sample()`
     was added as an explicit, separate entry point for re-emitting *only*
     the blank template.
   - Verified: `gs-129/130/133/134` (the sampled `NO_MATCH` cases) really do
     fail to resolve against `orders.db`; the other 26 rows' order facts are
     byte-identical to what pass 1 showed (only the corrupted-record
     presentation changed).
4. **Separated the determinism contract**
   (`tests/test_gold_set_determinism.py`): `gold_set.jsonl` /
   `ground_truth_holdout.jsonl` are proven deterministic by building into a
   temp dir (never rewriting the committed files); the generated *blank*
   human sheet is pinned separately
   (`PINNED_BLANK_HUMAN_SAMPLE_SHA256 = 7a41fc7b…52da6`); a human-edited
   sheet is no longer asserted against a content hash at all — it's
   validated structurally instead.
5. **Regenerated the fresh blank pass-2 sheet** into
   `bench/human_label_sample.csv` (30 rows, same case-id set and order, new
   `record_lookup_status` column, `human_label`/`human_notes` blank, no
   pass-1 label copied). Confirmed `gold_set.jsonl` / `ground_truth_holdout.jsonl`
   / `human_label_sample_pass1.csv` all byte-unchanged throughout.
6. Began updating `tests/test_human_label_sample_blind.py` to match the new
   schema and lifecycle (record_lookup_status / NO_MATCH assertions, pass-1
   preserved and not copied, fresh sheet blank) — **this was interrupted
   mid-edit** by the user (see below).

**Status when this conversation paused:** the blank pass-2 sheet and the
generator repair were on disk and verified; the test-file refactor for
`tests/test_human_label_sample_blind.py` was incomplete.

**Rule that was never crossed:** the second labeling pass was never performed
by the assistant, no second-pass kappa was computed or reported, and no
label, gold value, or `label.py` rule was changed to move the number.

---

## 6. Where things stand now (observed at handoff time, not actions taken here)

At the time of writing this file, `git log` on this branch shows one further
commit beyond the M4 blind-sheet commit:

```
b4ef009  P02 hardening, P04-P05 baselines/ablation, P07 fixes, P08 robustness,
         P09 latency, onboarding measurement, and P06 preflight
```

Its message states it *"consolidates several previously-uncommitted units of
work sitting in the working tree since the last commit (P03/M4)"* — i.e. it
appears to have picked up and committed the in-progress instrument-repair
work above (`docs/gold-set-annotation.md`, the repaired
`gold_set_build.py`/`agreement.py`, the finished test refactor, and the blank
pass-2 sheet) together with a large amount of **unrelated** P02/P04/P05/P07/
P08/P09 work from other sessions, in one combined commit.

On top of that, `bench/human_label_sample.csv` on disk right now has **all
30 `human_label` cells filled** (`ALLOW: 9, BLOCK: 13, ESCALATE: 4,
AMBIGUOUS: 4`) — i.e. a second labeling pass appears to have already been
carried out on the repaired sheet, outside this conversation. Notably
`ESCALATE = 4` exactly matches the 4 `NO_MATCH` cases, consistent with the
repaired rubric doing its job.

**This was not verified, scored, or acted on in this conversation** — no
`bench/agreement.py` run was performed here, no pass-2 kappa was computed or
reported, and `bench/gold_set.jsonl` / `bench/ground_truth_holdout.jsonl`
were confirmed still byte-identical to their long-standing pinned hashes
(`09deaecb…d48c8e` / `204e4a8e…a24e3cb`). It is flagged here only so the next
session (or the user) has an accurate picture before deciding what to do —
e.g. running `python bench/agreement.py` to get the real pass-2 kappa, and
updating `docs/gold-set.md` §6 accordingly.

---

## Files touched across this conversation

- `bench/human_label_sample.csv` — repaired, currently the (apparently
  completed) pass-2 sheet
- `bench/human_label_sample_pass1.csv` — immutable pass-1 record
- `bench/agreement.py` — BOM-safe reads, case_id join, kappa gating
- `bench/gold_set_build.py` — `slice` column removed from the template;
  `record_lookup_status` / NO_MATCH handling; `out_dir` param;
  `regenerate_blank_human_sample()`
- `docs/gold-set.md` — schema, determinism pins, §6 human-agreement narrative
- `docs/gold-set-annotation.md` — new annotator rubric
- `tests/test_human_label_sample_blind.py` — blindness + repaired-schema
  assertions
- `tests/test_gold_set_determinism.py` — determinism contract split (real
  artifacts vs. generated blank template)
- Unchanged throughout, verified repeatedly: `bench/gold_set.jsonl`,
  `bench/ground_truth_holdout.jsonl`, `reports/*`, P04/P05/P08/P09 result
  artifacts.

## Suggested next step

Run `python bench/agreement.py` against the current (apparently pass-2)
sheet, confirm it against `docs/gold-set-annotation.md`'s scoring rule, and
update `docs/gold-set.md` §6 with the real, current number — only after
someone has confirmed the 30 filled labels are in fact the intended
independent second pass and not leftover pass-1 state or another session's
test data.
