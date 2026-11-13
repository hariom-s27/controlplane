# Limitations

The running list of build limitations lives in `README.md` ("Honest
limitations"). This file holds the ones that need more than a bullet: the
bias-measurement framing, the retired figures, the P08 robustness findings
(we inherit the record's errors, and the boundaries of SOURCE-UNRELIABLE),
external validation, and the judge dashboard's own scope boundaries.

## Known test-suite state

The full suite (`python -m pytest tests/`) runs in CI on every push, on
Linux and Windows (see `README.md`, "Continuous integration"). Test counts
are quoted only together with the CI run they come from; this file holds
none, because counts change with every commit.

- **The grounding tests skip without `torch`.** `tests/test_ground.py` calls
  `pytest.importorskip("torch")` at module level, so the module is reported
  as one skip when `torch` is absent. Grounding (S8, `CP_GROUNDING`) is
  optional and default-off, and `torch` is deliberately not in
  `requirements.txt` (it needs its own CPU-wheel install command, documented
  next to the commented-out line). Whether the module runs depends on
  whether a machine has installed `torch`, not on the operating system.
- **The old archival-integrity check is replaced.** The test that used to
  fail here
  (`tests/test_tau2_c2_controlplane_side.py::test_post_p02_integrity_record_accounts_for_one_authorized_change`)
  no longer exists. Since commit `3b536d8` the integrity record is
  `docs/m1-integrity-v2.sha256`, checked by `tests/test_integrity_v2.py`;
  the v1 record `docs/p06-post-p02-integrity.sha256` is kept unchanged as
  history (see `docs/m1-integrity-v2.md`).
- **Public fixture-mode demo behaviour has been independently verified** —
  see the Live demo section of `README.md`.
- **The two human-label-sheet hashes** pinned in
  `tests/test_human_label_sample_blind.py`
  (`bench/human_label_sample.csv`, `bench/human_label_sample_pass1.csv`)
  were previously recorded from a CRLF working copy and have now been
  corrected to their canonical git-blob (LF) hashes, with
  `/bench/human_label_sample.csv text eol=lf` and
  `/bench/human_label_sample_pass1.csv text eol=lf` added to
  `.gitattributes`. The suite therefore behaves consistently across
  Windows, Linux and macOS instead of depending on which platform last
  checked the files out.

This is reported as-is: CI runs without `torch`, so the grounding module is
a skip there, never a pass.

## Public demo scope

- The public demo (https://controlplane-qvr2.onrender.com/) runs in
  deterministic fixture mode and does not require external LLM provider
  credentials.
- It is a prototype/demo deployment, not a production deployment.
- Optional grounding (S8, HHEM-2.1-Open) is not part of the base demo path
  and is not exercised by the public demo.
- The demo should not be read as evidence of production-scale performance —
  see "Measured results" and "Where it fails" in `README.md` for what is and
  is not measured.

## There is no external validation

Every quantitative result in `README.md` ("Measured results") and
`reports/baselines.md`/`reports/robustness.md` is our own internal evidence —
a single synthetic gold set (`bench/gold_set.jsonl`, single retail-servicing
domain), plus one latency evidence pack measured on one laptop. The attempt
at validation on the third-party `sierra-research/tau2-bench` benchmark is
retired as evidence: no tool call reached the gate, and the runs are not in
this repository (`docs/errata.md`). No claim here should be read as
externally validated, and the B4/B5 result should not be read as
generalizing beyond the evaluated failure mode (retrieval staleness) on this
gold set.

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
boundary, runs the real gate over the non-ambiguous P03 gold cases at each
rate of a fixed grid, and compares binary-direction accuracy against the
frozen P04 B4 TraceGrounded baseline (B4 right on 123/140 cases).
Recompute: `python bench/failure_injection.py`; both numbers below are in
`docs/claims.yaml`.

- **Crossover: ≈10.6%** (`reports/summary.json['p08_robustness']
  ['record_error_crossover']`). At roughly one date-bearing record in ten
  wrong, ControlPlane's accuracy on the gold set drops below what a
  trace-grounded checker achieves without touching the record at all. Cluster
  bootstrap over public source-order ids: 95% interval [10.6%, 44.7%].
- Below that rate, live-record grounding is still ahead. Above it, the
  record's own error rate is the thing to fix — no verifier architecture
  helps.
- The curve is steep near the crossover because the gold cases sit on far
  fewer distinct date-bearing orders than there are cases, so a single
  corrupted record can flip several cases. The crossover is therefore a
  property of *this gold set's* order reuse, not a universal constant; the
  method, not the number, is the transferable part.
- Context: real carrier scan-error rates are an external question. A USPS
  OIG audit is the usual reference; this repository does not hold that
  source, so no external rate is quoted here.

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
  fails **closed** (BLOCK); the knowledge assistant (`entitlements.db`,
  tier 0) **escalates** — the action is held for review, and BLOCKed once
  the escalation budget is exhausted. Neither executes (D-M1-01; the former
  fail-open posture was removed).
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

## The judge dashboard is a fixture-mode demonstration, not a deployed service

`demo/web.py` (Product-03, hardened by Product-04A) is a single-process
FastAPI app with no authentication and no per-browser session identity.
`_RUN_LOCK` accepts exactly one RUN or RESET at a time process-wide and
**rejects** a concurrent request (HTTP 409) rather than queueing it — that
single in-flight slot is the whole demo's session boundary, correct for one
judge looking at one screen, and would need real multi-tenant isolation
before it could serve more than that. `CP_MODE=fixture` by default: every
scenario replays a committed LLM-response fixture, never a live model call.
The earlier P09 measurement of the gate under a worker pool
(`reports/latency.md`, section H) is retired with the rest of that report's
timing figures (`docs/errata.md`); nothing here measures concurrent load.

**The signed receipt does not contain what happened after the decision.**
`receipt_verification` (`VERIFIED`/`TAMPERED`/`VERIFICATION ERROR`/
`RECEIPT / RESULT MISMATCH`) is a check of the receipt's own HMAC-SHA256
signature and that its stored verdict/intervention match the call that just
produced it — it attests to the *decision record*, not to what happened
afterward. `execution_state` (`EXECUTED`/`PREVENTED`/`REFUSED`/`REPLAYED`)
is a separate field, derived from the real try/except outcome of whether
the tool actually ran. The dashboard renders these as two distinct panels
(RECEIPT vs. EXECUTION) on purpose: a verified signature is not evidence of
post-decision execution outcome, and nothing here claims otherwise.

**MODIFY is subtractive/additive only — redact, caveat, constrain — never
substitutive** (`docs/threat-model.md`, threats T14-T17): a missing or
non-dict modified payload never falls back to the agent's original
arguments (dispatch raises `Pending` / refuses instead), and an explicit
dict is passed through exactly as given, never merged with the original.
What is *not* proven: that the dictionary's contents are semantically valid
for the tool being called, or match its schema — `docs/threat-model.md`
records this as an open gap, not a solved one.

**discount_approval (the third use case) is not one of the dashboard's two
profiles.** It is engineering-validated at the manifest/agent/test level
(`tests/test_third_use_case.py`, `make demo3`) — proof the engine
generalizes to a use case it wasn't originally written for — not a
publicly demonstrated dashboard scenario, and no broader claim should be
read into it.

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
On small samples it can fail often when there is no true difference, and
miss a real gap on large ones; no simulation of this is committed here, so
no rates are quoted. Any real bias probe must report
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
