# Metamorphic invariants — S15

ControlPlane has no ground truth for most production traffic — nobody hand-
labels every refund decision "correctly blocked" or "correctly allowed."
Metamorphic relations solve that oracle problem: instead of asking "is this
one output right" (which needs a label), they ask "does changing the input
in a KNOWN direction change the output in the direction it must" — which
needs no label at all, and can run continuously against live, unlabelled
traffic.

All five are properties of `controlplane/decide.py::decide()`, which is
pure by hard constraint #4 specifically so these can be run thousands of
times by Hypothesis without I/O, a clock, or logging getting in the way.
"More permissive" and "stricter" are comparisons over `Intervention.rank`
(`controlplane/schema.py`) — ALLOW=0 < MODIFY=1 < OBSERVE_ONLY=2 <
ESCALATE=3 < BLOCK=4 — never a lookup table, so every invariant below is a
genuine order comparison (`Intervention.more_permissive_than`), not a
hardcoded case split.

| # | Name | Statement |
|---|---|---|
| M1 | Strictness monotonicity | Make any evidence strictly less favourable → the intervention must not become more permissive. |
| M2 | Amount monotonicity | Lower the amount, all else equal → the decision must not become stricter. |
| M3 | Policy equivalence | Two claims the policy treats identically get identical verdicts. |
| M4 | Idempotence | The same action re-submitted unchanged → same verdict, same receipt modulo timestamp and id. |
| M5 | Source-degradation monotonicity | Swap in a staler or lower-reliability source → the verdict must never become more permissive. It may become SOURCE_UNRELIABLE or ESCALATE; never ALLOW where it was BLOCK. |

Implemented in `tests/test_invariants.py` with `hypothesis`, generating
randomized (but load-bearing-fact-only) scenarios — never protected
attributes, see `controlplane/bias_probe.py` for that separate concern.

## Why these five and not others

Each is chosen because it's checkable without a label and because a
violation would mean something specific and actionable:

- **M1/M5** together are the load-bearing pair: they say the whole system
  is monotone in evidence quality. If making a fact *worse* ever made the
  outcome *more permissive*, the gate would be exploitable by degrading
  your own evidence — the opposite of what a verification layer is for.
- **M2** is the amount-specific case of M1, split out because amount is the
  one dimension with a natural total order the business itself uses
  (the ₹25,000 authority ceiling) — worth its own check rather than folding
  into the generic evidence-favourability relation.
- **M3** catches policy-equivalence bugs that unit tests miss by
  construction: two concrete inputs that *should* reduce to the same
  policy-relevant state (same days-elapsed via different date pairs, same
  predicate_result via different raw evidence) must not silently diverge
  because of something implementation-specific leaking into the verdict.
- **M4** is the receipt's own contract: a caller that retries an unchanged
  action must get back the same decision, not a coin flip — this is what
  makes the idempotency key on the receipt (S10) meaningful rather than
  decorative.

## Verify

Deliberately break a rule — flip R1's `<=` to `>=` in
`controlplane/predicates/graphs/servicing.json` — and confirm at least one
invariant fails and the mutation score (below) drops. An invariant suite
that never fails on a real regression isn't testing anything; this is the
five-minute check that it does.

---

# Mutation testing

Mutating the **inputs**, not the code: each operator below takes a genuine
ALLOW-worthy scenario and corrupts exactly one fact, then asserts the gate
now catches it (BLOCK, ESCALATE, or SOURCE_UNRELIABLE — anything other than
the original ALLOW counts as "caught").

| Operator | What it does |
|---|---|
| `order_id_nonexistent` | Points the claim at an order_id no resolver can find |
| `amount_above_ceiling` | Raises amount_paise past the manifest's authority ceiling |
| `delivered_at_outside_window` | Pushes delivered_at past the window_days boundary |
| `clause_version_superseded` | Sets the claimed policy version to a version the registry doesn't currently return |
| `customer_id_mismatched` | Makes the order's customer_id disagree with the session's |
| `order_status_inconsistent` | Sets an inferred-reliability field on a load-bearing claim, forcing SOURCE_UNRELIABLE |

`tests/test_mutation.py` generates ~200 mutants (operators applied to
randomly varied base scenarios, seeded for reproducibility) and reports
**mutation score = fraction caught**.

**The caveat the literature itself states** (Just & Ernst, FSE'14):
mutants correlate with but do not perfectly represent real faults. The
score below is reported as a rigorous lower bound and a regression signal
— proof the gate reacts to a `git diff`-sized corruption of the input it's
supposed to catch — not as a real-world catch rate, and not as a substitute
for the golden-scenario and negative-control evidence elsewhere in `docs/`.
Saying that plainly is worth more than the number is.
