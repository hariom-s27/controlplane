# Verification coverage (P1)

**Goal.** Make the scope of factual verification behind one executable
enterprise-agent action explicit, measurable, and auditable — without
changing what the gate enforces.

This is the coverage number the roadmap once called "the most persuasive
single number in the submission", rebuilt so it can actually fail. The
earlier `coverage_ratio = (C1+C2+C3) / total_claims` was retired for being
circular: every claim a governed tool emits is C1/C2/C3 by construction, so
the ratio was deterministically `1.0` and measured nothing
(`docs/experiment-audit.md`). The P1 metric is a **runtime outcome** instead
of a static tier property — a claim only counts if authoritative evidence
actually supported it on *this* decision.

---

## The claim lifecycle

Every claim that reaches the ledger carries two orthogonal states.

### Modelling state — could the engine represent this claim at all?

```
EXTRACTED  = every claim that reached the ledger
   ├── MODELLED    — has a ClaimKind and a tier (ladder.py placed it)
   └── UNMODELLED  — classification produced no tier; recorded anyway, never dropped
```

Invariant: `MODELLED + UNMODELLED == EXTRACTED`.

Today the pipeline is manifest-driven — one claim per `claim_binding`, every
one MODELLED — so `UNMODELLED` is `0` in normal operation. The state exists
so that a future free-text claim miner cannot make a claim vanish silently:
an unmapped claim becomes an explicit `UNMODELLED` row, not a gap. See
**Limitations** below.

### Load-bearing / eligibility / verification status

- **load-bearing** — would the action be wrong if this claim were false?
  (1–3 per action; `controlplane/ladder.py::_LOAD_BEARING`.)
- **verification-eligible** — is there an authoritative way to check this
  ClaimKind at all? True for tiers C1/C2/C3, false for C4 (no consensus
  resolver in this build) and C5 (unverifiable by definition).
- **verification status** — the outcome of the check on this decision:

  | status | meaning |
  |---|---|
  | `VERIFIED` | authoritative evidence was resolved, was at/above the manifest reliability floor, and **supports** the claim's check |
  | `CONTRADICTED` | authoritative evidence was resolved and **refutes** the claim |
  | `UNVERIFIED` | eligible, evidence present, but no conclusive check ran (predicate unavailable, optional C3 checker off, or the source was below the reliability floor) |
  | `UNAVAILABLE` | the authoritative fact could not be obtained (no evidence resolved, or the lookup returned nothing) |
  | `NOT_ELIGIBLE` | C4/C5, or an `UNMODELLED` claim — no authoritative check path |

  Only `VERIFIED` counts toward coverage. Per PART 6:
  `UNMODELLED ≠ UNVERIFIED ≠ UNAVAILABLE ≠ CONTRADICTED ≠ RESOLVED ≠ VERIFIED`.
  A resolver returning a value is not verification — only *supporting*
  authoritative evidence is.

The ledger's per-claim status mirrors `decide()`'s own loop exactly (same
dispatch on predicate flag / clause match / grounding score), so the ledger
can never disagree with the verdict.

---

## The metric

```
verification_coverage = verified_load_bearing_eligible_claims
                        ────────────────────────────────────
                             load_bearing_eligible_claims
```

On the **signed receipt** — only the numbers a reader cannot recompute from
the per-claim `verification` rows on `claims[]`:

```json
{
  "verification_coverage": {
    "verified": 4,
    "eligible": 5,
    "coverage": 0.8,
    "coverage_basis": "load_bearing_verification_eligible_claims",
    "coverage_na": false
  }
}
```

The full per-status counters (`contradicted`, `unverified`, `unavailable`,
`unmodelled`, `claims_modelled`, `load_bearing_claims`,
`verification_eligible_claims`, …) are reconstructable from the per-claim
rows, and are also kept verbatim on the in-memory
`Decision.verification_ledger` and in the `decisions.jsonl` telemetry block
`telemetry.coverage.verification_coverage`.

- `coverage_basis` names the denominator population **explicitly**. It is the
  load-bearing claims that had an authoritative check path — **not** "every
  claim that should have existed". The metric does not know what claims a
  perfect extractor would have produced.
- **Zero denominator ⇒ `coverage: null`, `coverage_na: true`.** Never `1.0`,
  never `100%`. `0 / 0 = N/A` (PART 7).

### What it is *not*

- Not a probability that the action is correct. Coverage says how much was
  checked, not how likely the checks are right. (C3 entailment SOTA is 77.4%,
  not certainty; a VERIFIED C1/C2 claim can still sit on a wrong-but-
  well-formed record — see `docs/limitations.md`.)
- Not a risk-coverage curve. `bench/verification_coverage_bench.py` validates
  that the *number* is computed correctly for known claim mixes; it does not
  disable verification to draw a curve, and no curve is claimed.

---

## Enforcement — none, yet (PART 10)

Coverage is an **observability / audit measurement**. It does **not** feed
back into verdict or intervention:

- no `coverage < threshold → BLOCK`
- no `coverage < threshold → ESCALATE`
- adding it did not change what `VERIFIED` means anywhere else

`decide()` computes the ledger from the same facts it used for the verdict
and attaches it; `tests/test_invariants.py` (M1–M5) and the mutation harness
are unaffected because the verdict/intervention logic is untouched. First
validate the measurement; a promotion path can come later.

---

## Where it lives

| file | role |
|---|---|
| `controlplane/schema.py` | `ModellingState`, `VerificationStatus`, `ClaimVerification`, `VerificationCoverage`, `VerificationLedger`; `Decision.verification_ledger` |
| `controlplane/ladder.py` | `verification_eligible(kind)` — C1/C2/C3 only |
| `controlplane/decide.py` | `build_verification_ledger(...)` (pure); `resolved_verification_ledger(decision)` reconstructs it for the operational-failure path |
| `controlplane/receipt.py` | compact `verification_coverage` block + per-claim `verification` on `claims[]`, inside the signature |
| `controlplane/telemetry.py` | `telemetry.coverage.verification_coverage` sub-block |
| `bench/verification_coverage_bench.py` | deterministic metric-correctness check → `reports/verification-coverage.md` |
| `tests/test_verification_coverage.py` | the PART 11 matrix + PART 8 invariants |

---

## Limitations

- **Extraction completeness is not measured.** `EXTRACTED` is the count of
  claims the manifest-driven builder produced, not the count a perfect
  extractor would have. If the agent asserts something no `claim_binding`
  covers, that assertion is not currently turned into a claim and so is
  invisible to coverage. `UNMODELLED` is the representation ready for when a
  free-text claim miner exists; until then it is structurally `0`.
- **`VERIFIED` inherits the record's own errors.** Coverage measures whether
  a claim was checked against the system of record, not whether that record
  is true. The ≈10.6% wrong-record crossover in `reports/robustness.md`
  still applies.
- **C3 coverage depends on `CP_GROUNDING`.** With grounding off (the
  default), a `CLAUSE_SEMANTICS_MATCH` claim is `UNVERIFIED`, not `VERIFIED`
  — honestly reflected in the number.
- **Receipt size.** The block plus per-claim `verification` strings add a
  measured ≈400 B median to the signed receipt (`bench/receipt_size.py`,
  n=120 across all three manifests: median 2,282 B → 2,696 B, p95 3,763 B →
  4,793 B). The receipt was already over its ≈2 KB design target
  (`docs/limitations.md`); this is a further, documented increase, kept
  because the block is load-bearing audit evidence. The per-claim form is a
  bare status string except where more must be said, and the receipt block
  drops every counter recomputable from the rows. The minimal single-claim
  receipt stays under 2 KB.
