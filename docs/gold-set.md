# The independent gold set (task P03)

`bench/gold_set.jsonl` — 150 refund-decision cases with a gold verdict that was
**not** produced by the system under test. Everything downstream that reports an
accuracy, a false-positive rate or a confusion matrix (SEB-1 Exp 5, and the
P04+ baseline work) draws its ground truth from here.

| File | What it is | Committed? |
|---|---|---|
| `bench/label.py` | the independent labeller — a second implementation of the refund rules | yes |
| `bench/gold_set.jsonl` | 150 cases + gold verdict (from `label.py`) | yes, regenerable |
| `bench/ground_truth_holdout.jsonl` | per-case construction truth — **held out from every checker** | yes, regenerable |
| `bench/human_label_sample.csv` | 30 cases, blind (see §6), blank `human_label` / `human_notes` | yes |
| `bench/agreement.py` | human-vs-`label.py` Cohen's kappa + disagreement list, joined on `case_id` | yes |
| `bench/gold_set_build.py` | the deterministic constructor | yes |

Regenerate the whole set with `make goldset` (`.\make.ps1 goldset` on Windows).

---

## 1. The independence guarantee, and how it is enforced

The failure this exists to prevent is the one `docs/experiment-audit.md`
documents four times: **the label and the detector are the same object**, so the
metric cannot come out any way but perfect.

The gold verdict for every case is assigned by `bench/label.py`, which:

* **shares no code with the gate.** It imports nothing from `controlplane/` —
  not `decide`, not `predicates`, not `ladder`, not `ground`, not even
  `schema`. `tests/test_label_independence.py` parses its AST and fails on any
  `controlplane` import.
* **re-derives the thresholds from a different source representation than the
  gate uses.** The 7-day window is parsed out of the clause *prose* in
  `policy_store.db` (`"... within 7 days of the delivery date ..."`); the gate
  reads `window_days: 7` from `manifests/servicing.yaml`. The 25,000 authority
  ceiling is parsed from the authority-clause prose
  (`"... up to and including INR 25,000 ..."`); the gate reads
  `authority_ceiling_paise: 2500000` from the manifest. This is an independent
  *derivation path* over an independent *representation* — prose in the clause
  store vs. a scalar in the manifest. It is **not** independent authorship of
  the underlying policy intent: `data/seed/clauses.json` and
  `manifests/servicing.yaml` were hand-authored together to agree, so a
  mistake in that shared intent would sit in both. What the two paths catch is
  drift — if one artifact is edited and the other is not, `label.py` and the
  gate diverge and the disagreement surfaces.
* **re-states the verdict precedence and the intervention mapping** in its own
  code, from the policy, rather than importing `decide()`'s.
* **never sees the construction truth.** `bench/ground_truth_holdout.jsonl`
  carries each case's real source order, whether a distractor exists, the
  intended slice and the true policy version. `label.py` never opens it; it
  sees exactly what the gate sees — the tool call, the session, the agent's
  prose, the retrieved chunks — plus the enterprise's own stores.
  `tests/test_gold_set_holdout_isolation.py` asserts that no module under
  `controlplane/` and none of `label.py` / `agreement.py` /
  `seb1_exp5_confusion_matrix.py` / `exp3_checker.py` names, opens, or imports
  the holdout or its owning builder.

Writing the rules twice is the point: `bench/gold_set_build.py` checks
`label.py`'s verdict against the slice each case was *constructed* for, and
**raises** on any disagreement — that would mean a bug in one of the two
implementations. As of this writing the two agree on all 150 cases.

The gold verdict is still *our reading of the policy*. That is a real
limitation (§5), and it is exactly what `bench/human_label_sample.csv` +
`bench/agreement.py` exist to quantify.

---

## 2. Construction method

Every case derives from a **real row in `data/orders.db`**. No order, customer
or delivery record is invented. The database is not modified or appended to.

`data/orders.db` has 109 orders, delivery dates spread over ~120 days against
the frozen demo clock (`CP_DEMO_DATE=2026-08-14`). That distribution cannot
supply the P03 slice counts directly — in particular only **5** orders were
delivered inside the current 7-day refund window, and only 1 of those is also
under the 25,000 ceiling.

Where a slice needs more cases than there are eligible rows, distinct
tool-call instances are built from the real rows by varying **legitimate
action/context variables** — the requested refund amount (a partial refund of
one item in a multi-item order is a normal agent action), the agent's phrasing,
which policy chunk it retrieved, the trace id — while the underlying **source
truth is unchanged**: same real order, same real delivery date, same customer,
recorded in the holdout file.

### Consequence for downstream statistics

Because several cases share one source order, the 150 cases are **clustered by
`source_order_id`, not independent**. Any confidence interval computed over
this set must account for that (cluster-robust SE, or a case-cluster
bootstrap). `gold_set_build.build()` reports the unique-source count so the
clustering is visible.

| slice | cases | unique source orders | gold |
|---|---:|---:|---|
| `allow_in_window` | 50 | **5** | ALLOW |
| `outside_window` | 20 | 20 | BLOCK |
| `over_authority` | 15 | 15 | BLOCK |
| `distractor_present` | 20 | 20 | BLOCK |
| `stale_policy_context` | 20 | 20 | BLOCK |
| `corrupted_or_missing_record` | 15 | 15 | ESCALATE |
| `ambiguous_under_policy` | 10 | 7 | AMBIGUOUS |
| **total** | **150** | **101 distinct orders** (of 109) | |

`label.py` distribution: ALLOW 50 · BLOCK 75 · ESCALATE 15 · AMBIGUOUS 10.

### What each slice is

* **`allow_in_window`** — a real in-window order, a refund within the 25,000
  authority (a full or partial refund). A true ALLOW; this is the slice that
  measures the gate's false-positive (over-block) rate. All 50 cases sit on
  5 source orders (10 amount/phrasing variants each) — the most clustered
  slice by far.
* **`outside_window`** — a real order delivered well outside the 7-day window
  (20–111 days), refund requested within authority so the window is the only
  thing wrong.
* **`over_authority`** — refund requested above the 25,000 ceiling (ceiling+1
  up to the order total) on 15 real orders that cost more than that.
* **`distractor_present`** — the agent resolved to a real same-customer sibling
  of the order the customer described (same colour, different category — a
  wrong-order resolution the attribute check can see). `order_id` in the call
  is the wrong (real) order; `item_colour`/`item_category` are what the
  customer described.
* **`stale_policy_context`** — the agent's retrieved context is the **real
  superseded v3.8 clause** (30-day window) still sitting in `policy_store.db`,
  and `claimed_policy_version` is `v3.8`. The order is outside the current
  7-day window, so acting on the stale policy is wrong. Most of these orders
  are also within v3.8's own 30-day window (the realistic "the agent thinks
  it's fine" case); a few older ones are outside even that.
* **`corrupted_or_missing_record`** — 10 cases where the `order_id` in the tool
  call is a transcription corruption of a real id (dropped digit, transposed
  digits, mangled prefix) that resolves to **no row**; 5 cases where the call's
  `currency` (`USD`) contradicts the real order record's `INR`. The source
  order is real and recorded in the holdout; the corruption is the point.
* **`ambiguous_under_policy`** — see §3.

---

## 3. The ambiguous slice — our policy interpretation

The v4.2 clause is: *"Customers may request a full refund within 7 days of the
delivery date. Requests made after 7 days may be eligible for store credit at
the discretion of a supervisor."*

`label.py` calls a case AMBIGUOUS in two situations, both genuinely unsettled by
that text:

1. **Window boundary (`elapsed == 7`).** "within 7 days" does not say whether
   day 7 itself is inside. `manifests/servicing.yaml` comments that the gate
   treats it as inclusive (`days_elapsed <= 7`), but that is the gate's choice,
   not the policy's statement. 4 cases, all on the one real order delivered
   exactly 7 days before the frozen clock (`ORD-10102`).
2. **Supervisor-discretion band (`7 < elapsed <= 14`).** The clause hands a
   supervisor discretion over post-window remedies. For the first policy-window
   past the deadline it is genuinely arguable whether a full-refund tool call
   should be BLOCKed outright or ESCALATEd so the supervisor can exercise that
   discretion. 6 cases on 6 real orders delivered 8–14 days out.

The **`elapsed <= 14`** cutoff for the discretion band is our choice — "within
one further policy window" — not something the text states. Past that,
`label.py` returns BLOCK. A reviewer could reasonably draw that line
differently; that is what §5 and the human agreement number are for.

**Known tell in the agent context.** Four of the six discretion-band
justifications (`gs-145`, `gs-146`, `gs-148`, `gs-149`) contain phrasing that
points at the answer — *"or send to a supervisor?"*, *"the clause mentions
supervisor discretion for late requests"*, *"just past the 7-day window"*.
That text is part of the case's `justification` / `retrieved_chunks` and **is
supplied to any system that reads the agent's reasoning** (in the P04 table,
B3 the LLM-judge; the trace-grounded and live-query pipelines parse only the
structured fields). It gives such a system a shortcut to ESCALATE/AMBIGUOUS on
those cases without doing independent policy analysis. The cases are not
regenerated — treat B3's (or any prose-reading system's) score on the
ambiguous slice as an upper bound, and note the tell when reporting it. The
same caution applies to `stale_policy_context`: `claimed_policy_version =
"v3.8"` and the retrieved v3.8 clause text uniquely identify that slice, so a
"cited version is not current → BLOCK" shortcut passes it without a live
lookup.

A gold set with no hard cases is not believable, so these are in it
deliberately, and `bench/human_label_sample.csv` puts all 10 in front of a
human.

---

## 4. Determinism

`bench/gold_set_build.py` is byte-deterministic: fixed seed (`CP_SEED=20260814`),
sorted JSON keys, LF line endings written as bytes (not text mode, which would
translate to CRLF on Windows and make the hash platform-dependent).

`tests/test_gold_set_determinism.py` builds the set twice, asserts the two
runs are byte-identical, and pins `gold_set.jsonl` / `ground_truth_holdout.jsonl`
by content SHA-256 (it separately pins only the *generator's blank* human
sample template, never the human-edited sheet — see the paragraph below).
`tests/test_human_label_sample_blind.py` structurally validates and pins the
human-edited sheets by their own current SHA-256:

```
gold_set.jsonl               09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e
ground_truth_holdout.jsonl   204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb
human_label_sample.csv       ccf356a53088c4ae68562364cade01f0b02b2da6ab7daf1f206b943027c22d91  (pass-2, complete — see §6)
human_label_sample_pass1.csv 919627b0e3ec1b6fc5d5e71f46561ed767a7aea4fd2961717cf5684e5c0ab729  (immutable, pass-1 archive)
```

The **builder-generated (blank)** `human_label_sample.csv` is a pure generator
output, pinned separately as `PINNED_BLANK_HUMAN_SAMPLE_SHA256` in
`tests/test_gold_set_determinism.py` and validated structurally (not by
content hash) in `tests/test_human_label_sample_blind.py`. `_write_human_sample`
refuses to overwrite a sheet that already carries a human label, so `build()`
leaves a filled sheet untouched — the generated blank template and a later
human-edited sheet are two different artifacts and must never be conflated
(see §6 for why this matters). `gold_set.jsonl` and `ground_truth_holdout.jsonl`
are byte-for-byte unchanged through every step of §6's instrument repair.

These hashes are taken over the DBs built from the committed seeds (the `.db`
files themselves are gitignored and rebuilt by `data/build_db.py`). If
`data/seed/*` or the construction logic changes, the test fails loudly and the
pinned hashes — and every downstream figure — must be regenerated.

---

## 5. Known limitations

* **Synthetic data.** `data/orders.db`'s 109 rows are 3 hand-authored demo
  orders plus deterministic filler. The gold set is only as representative as
  that.
* **Single domain.** One tool (`issue_refund`), one manifest (servicing). The
  entitlement / knowledge-assistant use case is not covered here.
* **Our own policy interpretation.** The gold verdict is `label.py`'s reading
  of the clause prose. The window-boundary call and the 14-day discretion
  cutoff (§3) are judgement calls, not statements in the text. This is the
  weakest link and is why the human sample exists.
* **Heavy clustering in the ALLOW slice.** 50 cases on 5 source orders. The
  false-positive rate this slice yields has far less independent information
  than n=50 suggests — treat it as roughly "5 orders, each probed 10 ways".
* **The BLOCK slices do not isolate a single predicate.** Because there are so
  few recent deliveries in the seed DB, most `over_authority`, `distractor_present`
  and `stale_policy_context` cases are drawn from orders that are *also*
  outside the 7-day window (every `over_authority` case is). `label.py` assigns
  one labelled reason per case (following its precedence order), but a system
  under test can reach the correct BLOCK for a different reason than the slice
  is named for — a bare "outside window → BLOCK" rule "passes"
  `over_authority`, `distractor_present` and much of `stale_policy_context`
  without doing an authority, attribute or version check at all. Slice-level
  accuracy therefore measures "did the gate stop this action", not "did the
  gate exercise the intended check". Use the per-reason detail in
  `label_rationale`, or construct single-condition cases, when the specific
  predicate matters.
* **The `corrupted_or_missing_record` slice is gold-label *intent*, not a
  demonstrated runtime path.** All 15 of its gold verdicts are what a correct
  gate *should* return; the current servicing runtime does not actually
  produce them:
  * **5 × `SOURCE_UNRELIABLE` (currency corruption).** There is **no currency
    check anywhere in the servicing runtime** — not in the Zen graph, not in
    `decide()`, not as a claim binding. The only `inferred`-reliability field
    is `orders.order_status`, which no servicing claim reads, and
    `controlplane/registry/freshness.py::escalation_for()` (the
    "inferred-field → SOURCE_UNRELIABLE" rule) is dead code — nothing in the
    pipeline calls it. So this verdict has no mechanism to fire.
  * **10 × `UNVERIFIABLE` (unresolvable `order_id`).** `decide()` *does* have
    the path (evidence `confidence=NONE` → `UNVERIFIABLE` →
    `verdict_handling` → `ESCALATE`), but `controlplane/intercept.py::_run_gate`
    calls the Zen graph **before** `decide()` and with no `try`/`except`, and
    the graph raises `RuntimeError` on a null `delivered_at`. Through
    `dispatch_tool` these cases currently **crash**, not escalate. (`bench/`
    scoring code that runs this slice guards the call itself.)
  * **P08 (robustness) is responsible** for exercising and fixing both failure
    modes — adding a currency/field-integrity check and guarding predicate
    evaluation so a missing record degrades to `ESCALATE` instead of an
    exception. Until then, no result may claim runtime `SOURCE_UNRELIABLE` or
    missing-record coverage from this slice.
* **SEB-1 Exp 5 is still blocked.** P03 delivered the gold set; the confusion
  matrix also needs a way to run the gate for each recorded tool call *without*
  executing the refund. Until that driver exists,
  `bench/seb1_exp5_confusion_matrix.py::run()` raises `SystemExit` with a
  message saying so. The AMBIGUOUS label is also new vocabulary that Exp 5's
  4-class matrix will need to handle (exclude, or add a class).

---

## 6. Human agreement

**Status: M4 — PASS WITH DISCLOSED SYSTEMATIC AMBIGUITY.** Pass 1 (original
instrument) is archived. Pass 2, under the repaired instrument, is complete
and is the number below: n = 30, exact agreement = 24/30 (80.0%), Cohen's
κ = 0.7321428571428572. See "Pass 1", "Instrument repair" and "Pass 2" below.

`bench/human_label_sample.csv` holds exactly **30 cases**: **all 10** of the
`ambiguous_under_policy` cases plus **the same 20** other cases the seeded
sample has always drawn (`SEED = 20260814`, unchanged). `human_label` and
`human_notes` **start blank** on the builder-generated sheet and are never
auto-populated by any tooling — the 30 values now on disk were entered by a
human under the repaired instrument (pass 2).

### The sheet is blind to construction intent and to every gold output

An annotator sees only what a real refund reviewer would have:

* the opaque `case_id`,
* the proposed action — `call_order_id`, `refund_amount_paise`,
* the order record facts — `order_total_paise`, `order_customer_id`,
  `order_delivered_at`, and the session's `session_customer_id`,
* the reference date `frozen_today` (so "days elapsed" is computable),
* the policy the reviewer would apply — `current_refund_policy_text`,
  `authority_policy_text`,
* the agent's own claim and prose — `agent_cited_policy_version`,
  `agent_justification`.

It does **not** contain: the construction `slice` (removed in task M4 — its
name stated the intended class for five of seven slices), `gold_label` /
`gold_verdict` / `gold_intervention`, `label_rationale`, `label_source`, or any
field from `bench/ground_truth_holdout.jsonl` (`true_order_id`,
`distractor_order_id`, the corruption recipe, `intended_slice` /
`intended_label`). No system prediction (`decide()` / predicates / intercept)
is run to build it, and it is **not** derived from the holdout — the sample is
selected from the public case list only.

`tests/test_human_label_sample_blind.py` asserts all of the above, plus that
the 30 `case_id`s (set and order) are unchanged and the sheet stays
byte-deterministic.

### Residual, un-fixable-without-recutting tells

The `case_id`s are the frozen P03 ids and cannot be renamed without changing
the 30 selected cases, so a determined annotator could still notice that
`gs-141`…`gs-150` are ten consecutive ids (they are in fact the whole
ambiguous slice), and that `agent_cited_policy_version = v3.8` on `gs-088`
marks the stale-policy case. Four discretion-band justifications (`gs-145`,
`gs-146`, `gs-148`, `gs-149`) still contain the phrasing noted in §3 — but
that text is part of the agent's real reasoning that a live reviewer would
read, so it stays. These are limitations of the frozen case material, not of
the sheet's schema.

### Reading the number — not before all 30 labels

`python bench/agreement.py` joins on the opaque `case_id`
(`case_id` → `bench/gold_set.jsonl` → `gold_label`; never row position, never
the holdout) and **refuses to report Cohen's kappa until every one of the 30
rows has a `human_label`.** Until then it prints how many labels are still
outstanding and exits 0. Once the sheet is complete it prints the kappa
against `label.py` and every disagreement.

### Pass 1 (complete, archived, superseded — not the current result)

One annotator labelled all 30 cases under the *original* instrument (no
`record_lookup_status` column). Preserved immutably at
`bench/human_label_sample_pass1.csv` (pinned SHA-256
`919627b0e3ec1b6fc5d5e71f46561ed767a7aea4fd2961717cf5684e5c0ab729`;
`tests/test_human_label_sample_blind.py::test_pass1_artifact_is_immutable_and_pinned`).

```
Cohen's kappa (human vs bench/label.py): 0.5454545454545454
raw agreement: 20/30 (66.7%)
```

All 10 disagreements were the annotator choosing **BLOCK** where `label.py`
returns something softer:

* `gs-129`, `gs-130`, `gs-133`, `gs-134` — `corrupted_or_missing_record`
  (unresolvable / currency-mismatched order id). `label.py` → ESCALATE
  (SOURCE-UNRELIABLE); the annotator treated "cannot act on this record" as
  BLOCK.
* `gs-145`–`gs-150` — the 8–14-day supervisor-discretion band. `label.py` →
  AMBIGUOUS (§3); the annotator read the clause as "no full refund is
  established, so block" rather than "escalate for discretion".

A read-only audit of these 10 disagreements found a real defect in the
*instrument*, not just a judgement difference: the sheet could show a
complete-looking order-fact block even when the tool-call `order_id` didn't
resolve to any record (the `gs-129`/`gs-130`/`gs-133`/`gs-134` cases), and the
annotator rubric didn't distinguish "the record is unverifiable" (ESCALATE)
from "the record is verified and contradicts the request" (BLOCK) clearly
enough for either the corrupted-record or the supervisor-discretion cases.
Pass 1's kappa is therefore **not** treated as the gold-set's human-agreement
number — it's preserved as evidence of the defect it exposed.

### Instrument repair (task M4)

* Added `record_lookup_status` (`FOUND` / `NO_MATCH`) to the sheet. `NO_MATCH`
  rows now show no order-record columns at all (blank
  `order_total_paise` / `order_customer_id` / `order_delivered_at`) instead of
  a record that looks resolved — see §6's schema list below.
* Added an explicit annotator rubric, `docs/gold-set-annotation.md`, defining
  ALLOW / BLOCK / ESCALATE / AMBIGUOUS and stating `NO_MATCH` →
  unverifiable → ESCALATE.
* Removed the `slice` column (already noted above) and separated the
  generated-blank-template determinism contract from the human-edited sheet
  (§4) so the two are never conflated again.
* The **same 30 `case_id`s, same order** as pass 1 — no resampling.

### Pass 2 — final repaired-instrument human-validation result

One annotator labelled all 30 cases independently, under the repaired
instrument and `docs/gold-set-annotation.md` rubric. Pass-1 labels were not
copied forward
(`tests/test_human_label_sample_blind.py::test_pass2_is_independent_of_pass1_not_a_copy`).
`bench/human_label_sample.csv` (pinned SHA-256
`ccf356a53088c4ae68562364cade01f0b02b2da6ab7daf1f206b943027c22d91`) is now
this completed pass-2 sheet.

```
$ python bench/agreement.py
Cohen's kappa (human vs bench/label.py): 0.732
agreement: 24/30
```

* n = 30, n_compared = 30
* exact agreement = 24/30 = **80.0%**
* Cohen's κ = **0.7321428571428572**
* 6 disagreements, all `human=BLOCK` vs `label_py=AMBIGUOUS`:
  `gs-145`, `gs-146`, `gs-147`, `gs-148`, `gs-149`, `gs-150`

**The four corrupted/unresolvable-record disagreements from pass 1
(`gs-129`, `gs-130`, `gs-133`, `gs-134`) are gone.** All four now show
`record_lookup_status = NO_MATCH` with no order-record columns, and the
annotator now labels all four `ESCALATE` — matching `label.py`'s gold
`ESCALATE` exactly. This is direct evidence the instrument repair (§6
"Instrument repair") fixed the presentation defect it targeted, not just a
coincidental score change.

**The six remaining disagreements are all in the documented
supervisor-discretion band**, and are reported, not hidden or reclassified.
For each of `gs-145`–`gs-150`, `bench/label.py` (`bench/label.py:279-286`)
returns `AMBIGUOUS` specifically because the clause grants the supervisor
discretion over post-window remedies and the code's own generated rationale
states *"BLOCK vs ESCALATE-to-supervisor is genuinely arguable"* — the same
judgement call is baked into the gold-label construction logic itself, not
asserted only in prose documentation. The human annotator resolved that same
genuine ambiguity by choosing BLOCK ("no full refund is established, so
block") rather than ESCALATE ("hold for supervisor discretion"). Per the
annotator rubric's secondary metric (`docs/gold-set-annotation.md`, "How your
labels are used"), a `BLOCK` against a gold `AMBIGUOUS` counts as an
*admissible* interpretation, not an error — reported separately from the
primary (exact) kappa, which is unchanged by this distinction. Under that
secondary view, admissible agreement is 30/30; the primary, exact-equality
Cohen's κ used for M4 remains **0.7321428571428572** and is not redefined by
this observation.

This is **one rater**, not a validated multi-annotator agreement study — do
not describe the gold set as "human-validated" beyond that. It does not
independently prove the gold labels are universally correct; it establishes
that where `label.py` returns a determinate verdict, an independent human
reading the same policy text and facts agrees with it, and where it returns
`AMBIGUOUS`, the human's alternative reading is the one the gold construction
logic itself already names as the other genuinely defensible answer.
