# P1 — verification coverage: metric check

Harness: `bench/verification_coverage_bench.py` (regenerate with `python bench/verification_coverage_bench.py --write`). Every row is built by hand with a known expected coverage, run through the real `controlplane.decide.decide()`, and the ledger it produces is compared against the expectation. No model call, no database, fully deterministic.

**What coverage is:** verified load-bearing verification-eligible claims / load-bearing verification-eligible claims. A claim only counts as *verified* if authoritative evidence was resolved, was at or above the manifest reliability floor, and actually supported the claim's check on this decision. `CONTRADICTED`, `UNVERIFIED`, `UNAVAILABLE`, `NOT_ELIGIBLE` and `UNMODELLED` are all explicitly *not* verified. See `docs/verification-coverage.md`.

**What it is not:** a probability that the action is correct, and not a risk-coverage curve. The denominator is the load-bearing claims that had an authoritative check path — not "every claim that should have existed".

| case | verdict | intervention | verified / eligible | coverage | extracted / modelled / unmodelled | v / c / u / na | pass |
|---|---|---|--:|--:|--:|--:|:--:|
| `coverage_100pct` | VERIFIED | ALLOW | 5 / 5 | 100% | 5 / 5 / 0 | 5 / 0 / 0 / 0 | pass |
| `coverage_80pct` | CONTRADICTED | BLOCK | 4 / 5 | 80% | 5 / 5 / 0 | 4 / 1 / 0 / 0 | pass |
| `coverage_60pct` | CONTRADICTED | BLOCK | 3 / 5 | 60% | 5 / 5 / 0 | 3 / 1 / 1 / 0 | pass |
| `coverage_40pct` | CONTRADICTED | BLOCK | 2 / 5 | 40% | 5 / 5 / 0 | 2 / 1 / 1 / 1 | pass |
| `coverage_20pct` | CONTRADICTED | BLOCK | 1 / 5 | 20% | 5 / 5 / 0 | 1 / 2 / 1 / 1 | pass |
| `coverage_0pct` | CONTRADICTED | BLOCK | 0 / 5 | 0% | 5 / 5 / 0 | 0 / 2 / 1 / 2 | pass |
| `missing_evidence` | UNVERIFIABLE | ESCALATE | 4 / 5 | 80% | 5 / 5 / 0 | 4 / 0 / 0 / 1 | pass |
| `contradiction` | CONTRADICTED | BLOCK | 4 / 5 | 80% | 5 / 5 / 0 | 4 / 1 / 0 / 0 | pass |
| `source_unavailable_all` | UNVERIFIABLE | ESCALATE | 0 / 5 | 0% | 5 / 5 / 0 | 0 / 0 / 0 / 5 | pass |
| `below_reliability_floor` | SOURCE_UNRELIABLE | ESCALATE | 0 / 1 | 0% | 1 / 1 / 0 | 0 / 0 / 1 / 0 | pass |
| `unmodelled_claim` | VERIFIED | ALLOW | 2 / 2 | 100% | 3 / 2 / 1 | 2 / 0 / 0 / 0 | pass |
| `mixed_states` | CONTRADICTED | BLOCK | 2 / 5 | 40% | 5 / 5 / 0 | 2 / 1 / 1 / 1 | pass |
| `zero_eligible` | VERIFIED | ALLOW | 0 / 0 | N/A | 1 / 1 / 0 | 0 / 0 / 0 / 0 | pass |

All cases pass: **True**.

Invariants checked on every case (PART 8):

- `MODELLED + UNMODELLED == EXTRACTED` — no claim is dropped without a state.
- `VERIFIED + CONTRADICTED + UNVERIFIED + UNAVAILABLE <= VERIFICATION_ELIGIBLE`.
- `coverage == verified / eligible` recomputed from the per-claim rows.
- `0 / 0` is reported as `N/A` (value `null`), never `100%` (PART 7).
- the signed Decision Receipt carries a `verification_coverage` block whose `verified`/`eligible`/`coverage` match the ledger (PART 9 / PART 11 case 10).

