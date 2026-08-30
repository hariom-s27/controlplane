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
runs are byte-identical, and asserts each file against a pinned SHA-256:

```
gold_set.jsonl              09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e
ground_truth_holdout.jsonl  204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb
human_label_sample.csv      48f069133e63ef87fb7f6027e1b259ab5ae534016f41ca1640a375d74130d3c9
```

The `human_label_sample.csv` hash changed in task M4 when the `slice` column
was removed from the sheet (§6). The same 30 cases are selected by the same
seed; `gold_set.jsonl` and `ground_truth_holdout.jsonl` are byte-for-byte
unchanged.

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

**Not yet available — no human validation has been performed.** No person has
filled the sheet; nothing in this repo has a human label.

`bench/human_label_sample.csv` holds exactly **30 cases**: **all 10** of the
`ambiguous_under_policy` cases plus **the same 20** other cases the seeded
sample has always drawn (`SEED = 20260814`, unchanged). `human_label` and
`human_notes` start **blank** for every row and are never auto-populated.

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
against `label.py` and every disagreement. **Do not quote a kappa, and do not
describe this data as "human validated", before that point.** Record the
number here when it exists.
