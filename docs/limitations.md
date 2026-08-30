# Limitations

The running list of build limitations lives in `README.md` ("Honest
limitations"). This file holds the ones that need more than a bullet: the
bias-measurement framing, the retired figures, and the P08 robustness
findings (we inherit the record's errors, and the boundaries of
SOURCE-UNRELIABLE).

## We inherit the system of record's errors

ControlPlane's entire argument is that it asks the company's own systems for
the answer instead of asking a model. The cost of that design is direct: **if
the system of record is wrong, ControlPlane is wrong, confidently, with a
signed receipt.** The verifier never reads a date — it reads `orders.db` — so
a corrupted `delivered_at` is not something it can detect or route around. It
is not a bug to be fixed; it is the boundary of what record-grounded
verification can do.

P08 measures where this becomes the dominant failure mode. The experiment
(`bench/failure_injection.py`, scenario 1; full method and curve in
`reports/robustness.md`) corrupts a growing, deterministically-chosen prefix
of `orders.db` delivery-date records so each flip crosses the seven-day
boundary, runs the real gate over the 140 non-ambiguous P03 gold cases at
each of 21 fixed corruption rates, and compares binary-direction accuracy
against the frozen P04 B4 TraceGrounded baseline (123/140 = 0.8786).

- **Crossover: ≈10.6%** (`reports/summary.json['p08_robustness']
  ['record_error_crossover']`). At roughly one date-bearing record in ten
  wrong, ControlPlane's accuracy on the gold set drops below what a
  trace-grounded checker achieves without touching the record at all. Cluster
  bootstrap over public source-order ids: median 10.6%, 95% interval
  [10.6%, 44.7%].
- Below that rate, live-record grounding is still ahead. Above it, the
  record's own error rate is the thing to fix — no verifier architecture
  helps.
- The curve is steep near the crossover because the 140 gold cases sit on
  only 85 distinct date-bearing orders, so a single corrupted record can
  flip several cases. The crossover is therefore a property of *this gold
  set's* order reuse, not a universal constant; the method, not the number,
  is the transferable part.
- Context: a USPS OIG audit found `delivered_at` scan errors around 2.45%,
  well under the crossover. Reused, cached, or manually-entered fields are
  routinely worse.

The honest one-liner for the pitch: *we do not claim to catch a wrong
record; we claim to be exactly as right as the record, and here is the rate
at which that stops being good enough.*

## What SOURCE-UNRELIABLE does and does not cover

SOURCE-UNRELIABLE is the fourth verdict class. It fires when the evidence
backing a load-bearing claim is **below the manifest's `reliability_floor`**
or **structurally absent / unreadable**. P08 exercises every branch
(`tests/test_failure_injection.py`, `reports/robustness.md`):

**It does cover:**

- A load-bearing field that is `NULL` in the record — resolved as
  `confidence=NONE, reliability=UNVERIFIED`, verdict SOURCE-UNRELIABLE,
  intervention ESCALATE. No exception, no date coercion crash.
- A load-bearing claim answered only by an `inferred`-class column (e.g.
  `order_status` between checkpoints) when the manifest floor is
  `corroborated` — SOURCE-UNRELIABLE then ESCALATE, with M5's intervention
  floor so a shaky apparent violation can never resolve *more* permissively
  than a hard contradiction would.
- An authoritative store that is offline or unreadable at decision time —
  raised as a typed `SourceUnavailable`, then routed by the active
  manifest's tier-specific fail posture: servicing (`orders.db`, tier 2)
  fails **closed** and does not execute; the knowledge assistant
  (`entitlements.db`, tier 0) fails **open** and executes with the receipt
  marked `verification_state="unverified"`.
- Two policy rows both marked current — raised as typed
  `AmbiguousPolicyState`, fails **closed**, emits a data-quality telemetry
  event, and never silently picks a row.

**It does not cover:**

- A record that is **present, well-formed, corroborated, and wrong** — see
  the section above. Nothing marks it unreliable because nothing about it
  looks unreliable.
- **Semantic** staleness where the effective-dated row is technically
  current but operationally out of step with reality (the store says the
  policy changed yesterday; the business started enforcing it a week ago).
- Corruption of a **non-load-bearing** claim's evidence — by design, only
  load-bearing claims can move the verdict, so a wrong value on a claim the
  user will not act on is not escalated.
- Availability failures that are **not** connection- or lock-class SQLite
  errors — a malformed query or a missing table is a programming/schema bug
  and is deliberately re-raised loudly rather than laundered into a
  fail-closed decision.
- **Durability across process restarts.** The idempotency ledger that gives
  retry-after-timeout its at-most-once guarantee (P08 scenario 8) is
  in-process only; a crash between execution and receipt persistence is an
  explicit gap.

## Bias is a population property, not a per-decision one

`decide()` (`controlplane/decide.py`) is a pure function of record facts; no
protected attribute is in scope. We verify this structurally rather than
statistically, because a statistical test over a variable the function
cannot read would pass regardless of correctness.

That is exactly what the previous bias probe did wrong. It drew a synthetic
group label with `rng.choice(["A", "B"])`, never passed it to `decide()`,
and then reported that block rates did not differ across it. With no path by
which the label could affect the outcome, "no detectable difference" was the
only result the test could ever produce — it passed by construction, not by
correctness, and reporting it as evidence of fairness was misleading. It has
been deleted (see `docs/experiment-audit.md`).

Asking "is this one response biased?" is a category error in the same way as
asking "is this one coin flip unfair?" Bias is a property of a distribution
of outcomes, not of a single decision. Anyone claiming real-time,
single-response bias detection is doing toxicity scanning and calling it
something else.

What replaces the probe:

- **`tests/test_no_protected_attributes.py`** — asserts, structurally, that
  `decide()` and every type feeding it (`ProposedAction`, `Claim`,
  `Evidence`, `SessionContext`, ...) carry no protected-attribute field, and
  that `decide()`'s signature takes no such parameter. A guarantee that the
  function *cannot read* the variable is stronger than a statistical test
  over a variable it cannot read.
- **`bench/bias_proxy_probe.py`** — a clearly-labelled *proxy analysis*, not
  a bias measurement. It correlates the group label with an input `decide()`
  does read (`amount_paise`) and confirms the statistical machinery detects
  the resulting gap. Its only purpose is to show the method has power when an
  effect exists — the deleted twin probe never could.

### On the statistical-power point, if a probe is ever run for real

The four-fifths rule is a ratio test commonly misused as a difference test.
On constructed tables it **falsely fails ~56%** of the time at n=30 with a
30% base rate and zero true bias, and **misses a real 10-point gap ~84%** of
the time at n=1,000 with a 50% base rate. Any real bias probe must report
the minimum detectable effect alongside the p-value: a null result you can
quantify is a result; a null result you cannot quantify is nothing.

## Retired figures

Four of the five reported experiments were found to be circular — their
headline numbers were forced by how the test inputs were constructed, not by
anything the system did. They are listed, with what replaced each, in
`docs/retired-figures.md`. The audit that found them is
`docs/experiment-audit.md`.

This is evidence discipline, not an apology. A benchmark that cannot fail is
worth less than no benchmark, because it teaches a reviewer to distrust the
numbers that *are* real.
