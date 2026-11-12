# Extraction reliability (P3-A — kind level)

**Scope of this document.** It describes only what P3-A actually implements: a
kind-level check that each manifest binds the load-bearing `ClaimKind`s an
independently authored reference says its governed tool requires. The
per-action, instance-level extraction benchmark remains **HELD** — see
[Not implemented](#not-implemented-held).

---

## The problem P3-A addresses

P1 verification coverage (`docs/verification-coverage.md`) measures:

```
verification_coverage = verified modelled load-bearing eligible claims
                        ─────────────────────────────────────────────
                             modelled load-bearing eligible claims
```

The denominator is *the claims the manifest modelled* — one per
`claim_binding`. Claim construction is entirely manifest-driven
(`controlplane/extract.py::build_claims` iterates only the manifest's
`claim_bindings`); free-form agent text cannot add a claim, and
`ModellingState.UNMODELLED` is structurally `0` in production.

So if a manifest **omits a binding** for a load-bearing fact, that fact never
becomes a `Claim`, never enters the P1 denominator, and coverage is
unaffected. A whole load-bearing dimension can be missing while the receipt
reads "100% covered". `docs/threat-model.md` **T32 — "Extraction differs from
agent intent"** names this (status: NOT TESTED); `docs/verification-coverage.md`
concedes it in its Limitations section.

P3-A supplies the missing half: an **independent statement of what should be
checked**, so an omission shows up as a number instead of staying a buried
YAML comment.

---

## The two metrics, kept separate

| | **P1 — verification coverage** | **P3-A — manifest claim-coverage (kind level)** |
|---|---|---|
| question | "of the claims we modelled, how many did we actually verify?" | "of the load-bearing checks this tool *requires*, how many does the manifest bind?" |
| formula | `verified modelled claims / eligible modelled claims` | `bound required load-bearing kinds / independently required load-bearing kinds` |
| denominator source | the manifest's own `claim_bindings` | `bench/extraction_reference.py` (independent — see below) |
| granularity | per decision, runtime outcome | per manifest/tool, static |
| `0 / 0` | `coverage: null`, `coverage_na: true` | `status: "not_assessed"`, `coverage: null` |
| lives in | the signed receipt + telemetry + `Decision.verification_ledger` | `reports/manifest-claim-coverage.md` + the bench JSON only |

These are **orthogonal**. A manifest can score **100% on P1 verification
coverage and still have unbound required kinds here** — that is exactly the
silent-pass case. Concretely:

- **Case A** — extraction complete, verification coverage 80%: 4 of 5 modelled
  load-bearing claims verified; the 5th was contradicted or unavailable. The
  gap is visible in P1.
- **Case B** — extraction incomplete, verification coverage 100%: every
  *modelled* claim verified, but a required check was never modelled. P1 shows
  100%; only P3-A shows the gap.

**P3-A does not change P1's number, its ledger, the receipt block, or
`decide()`.** It is a separate, read-only measurement.

---

## The independent reference — `bench/extraction_reference.py`

For each governed tool the reference lists the load-bearing `ClaimKind`s a
correct verifier must check, each with a rationale and a `basis` trail.

**How it is authored (and what "independent" means here).** The required-kind
sets are written **only** from:

1. the **tool argument schema** — the parameters each tool implementation
   takes (`agents/*.py`; for the tau2 tools, the retail domain's own tool
   contracts);
2. **policy prose** — the refund-window / authority / validity rules stated in
   words, in `manifests/*.yaml` comments and clause text — **never** the
   `claim_bindings` list;
3. **`docs/threat-model.md`** — the enumerated threats to executed arguments
   (T1, T2, T3, T13, T33, T34, T35).

The module **imports nothing from `controlplane/`** and **reads no file** — it
is static Python data. `tests/test_extraction_reference.py` parses its AST and
fails on any `controlplane` import, any file access, or any mention of
`claim_bindings` / `manifests` / `.yaml` in code. This is the same
anti-circularity discipline that `bench/label.py` /
`tests/test_label_independence.py` apply to the gold verdict labeller (P03):
the reference must not be a function of the system it audits.

**How claims are matched.** At the kind level only: the reference's required
`ClaimKind` names are compared, as sets, against the `claim_kind` values in
the manifest's `claim_bindings`. There is **no** instance-level or semantic
matching — no subject comparison, no decomposition analysis, no per-action
recall. Those need the corpus that does not exist yet.

**Two auxiliary lists, neither in the ratio:**

- `DELIBERATELY_NOT_REQUIRED` — kinds a reader might expect but the reference
  intentionally omits, with the reason (e.g. `EXCERPT_CONTAINS_THIRD_PARTY_PII`
  for `send_document`: PII presence does not by itself make a send wrong if the
  recipient is entitled; detection is a signal, not a gate). Recorded so an
  absence is seen to be a choice.
- `UNREPRESENTABLE_REQUIRED` — load-bearing checks that **have no `ClaimKind`**
  to carry them (loss point L2): currency/field integrity for the money-moving
  tools; an independent user-authentication channel for the tau2 retail
  integration. Advisory only — there is nothing to bind, so they cannot enter
  a coverage ratio, but they are listed so the gap is not invisible.

---

## Error taxonomy — what is and is not measured

From the P3 investigation's taxonomy (`docs/threat-model.md` T32 and the P3
report):

| Code | Category | Measured by P3-A? |
|---|---|---|
| **A** | MISSED CLAIM — a required load-bearing check is not bound | **Yes, at kind level** — `unbound_load_bearing_kinds` per manifest |
| **B** | EXTRACTION SPURIOUSNESS — a bound kind is not in the reference | **Partly** — `bound_not_in_reference_load_bearing` flags it for review (could be a reference gap or a real over-bind) |
| **C** | DECOMPOSITION ERROR — one reference claim split, or several merged | **No** — needs per-instance gold |
| **D** | CLASSIFICATION ERROR — right claim, wrong kind/tier/subject | **Partly** — a kind mismatch vs the reference shows; a wrong *subject* on a correctly-kinded claim does not |
| **E** | MODELLING FAILURE — a claim exists but is unrepresentable | **Represented** — `UNREPRESENTABLE_REQUIRED` lists the L2 cases; P1's `UNMODELLED` state is the runtime representation (currently always 0) |
| **F** | SILENT PASS — a required check never enters the P1 denominator | **Kind level yes** — every `unbound_load_bearing_kinds` entry is a silent-pass channel. A silent-pass **rate** needs the per-instance corpus. |

---

## Silent-pass analysis — the live case

```
missing load-bearing claim_binding
  → build_claims never creates the Claim
  → build_verification_ledger never sees it (it iterates `claims`)
  → the load-bearing eligible denominator is smaller than reality
  → verification_coverage stays high (can read 100%)
  → the signed receipt shows a clean, "fully covered" decision
```

**In the repo today:** every `manifests/tau2_*.yaml` binds only
`ORDER_STATUS_SUPPORTS_ACTION` and does **not** bind
`ORDER_BELONGS_TO_CUSTOMER`. The reference marks
`ORDER_BELONGS_TO_CUSTOMER` as required for every order-acting tool (you
cannot correctly cancel / modify / return an order without establishing it is
the requester's — T2, T34). So `bench/manifest_claim_coverage.py` reports each
tau2 manifest at **coverage 0.5, `unbound_load_bearing_kinds:
["ORDER_BELONGS_TO_CUSTOMER"]`**.

The binding carries a `binding_note`: tau2's retail domain exposes no
structural authenticated-identity channel independent of the agent
conversation (tau2's own task data documents this as an open issue). Binding
the check would require disallowed evidence (previous tool output) or circular
evidence (the evaluator's hidden ground truth). **The check stays required;
the domain as integrated cannot satisfy it.** P3-A does not route around the
gap — it makes the gap a number and keeps the reason attached.

`discount_approval` also surfaces: it does not bind `AMOUNT_NOT_EXCEEDING_ORDER`
though the structurally identical `service_credit_approval` does (coverage
0.75). Flagged for review — a deliberate goodwill exception or an oversight.

---

## The extraction-failure telemetry event (L5)

`controlplane/extract.py::extract_action` falls back to all-`None`
`_ClaimedFields` when the provider / schema-retry loop gives up. The fallback
is safe (all-`None` routes to `UNVERIFIABLE` downstream) but was **silent** —
`docs/threat-model.md` T32 notes provider failure and extraction failure
"collapse to the same result".

P3-A adds one structured event on the existing `controlplane.data_quality`
logger:

```json
{"event": "extraction_failure", "stage": "extract", "tool": "issue_refund",
 "cache_key": "…", "error_type": "…", "max_retries": 2,
 "fallback": "all_none_claimed_fields"}
```

It does **not** change the fallback, the return value, verdict, intervention,
or verification coverage — `tests/test_extraction_failure_telemetry.py`
asserts all of that, including that a failed extraction still cannot come out
`VERIFIED`.

---

## What this does NOT establish

- **Kind-level coverage does not establish instance-level extraction recall.**
  "The manifest binds every kind the reference lists" is not "every load-bearing
  fact of every actual action was extracted and checked."
- **The absence of a missing-claim finding does not prove no claims were
  missed.** The reference is human-authored and bounded by its author's reading
  of the schema, the prose and the threat model. A fact none of those three
  surfaces is invisible to P3-A too.
- **`UNMODELLED == 0` does not imply extraction completeness.** Nothing
  currently attempts to model beyond the `claim_bindings`, so there is nothing
  for that counter to catch. It is evidence of nothing.
- **No probability, no risk-coverage curve, no confidence interval.** P3-A is a
  correctness/reliability check over a fixed set of manifests, not a
  statistical estimate.

---

## Not implemented (HELD)

The per-action, instance-level extraction benchmark — recall (missed claims),
precision (spurious claims), decomposition accuracy, and a silent-pass **rate**
— is **not implemented**. It requires an **independent per-action reference
claim corpus**: for each of N actions, the exact set of load-bearing facts a
correct verifier must check, authored **without** reading `manifests/*.yaml`
`claim_bindings` or `controlplane/` extraction code (human annotation, or a
rule-based reference extractor in the spirit of `bench/label.py`).

No such corpus exists. `bench/gold_set.jsonl` and
`bench/ground_truth_holdout.jsonl` are verdict / record-identity gold;
`bench/human_label_sample.csv` annotators judge the gate intervention, not
claim sets. `bench/manifest_claim_coverage.py` reports these quantities as
`NOT_MEASURED`, never estimated.

---

## Files

| file | role |
|---|---|
| `bench/extraction_reference.py` | the independent per-tool required-`ClaimKind` sets; imports nothing from `controlplane/`, reads no file |
| `bench/manifest_claim_coverage.py` | the deterministic kind-level metric → `reports/manifest-claim-coverage.md` |
| `controlplane/extract.py` | the L5 extraction-failure event on the `controlplane.data_quality` logger |
| `tests/test_extraction_reference.py` | reference validity + AST independence |
| `tests/test_manifest_claim_coverage.py` | metric behaviour + P1-undisturbed check |
| `tests/test_extraction_failure_telemetry.py` | the L5 event fires; fallback unchanged; failure ≠ VERIFIED |
