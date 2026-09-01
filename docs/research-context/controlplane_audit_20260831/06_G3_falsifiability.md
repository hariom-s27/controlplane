# E. G3 — falsifiability assessment

The brief's G3 question is *"A5 can be 100% accurate by construction."* There is no A5. **The concern is nevertheless correct, and lands on four artifacts that do exist.**

## E.1 The 100%-by-construction defect, four times

| Artifact | The construction | Consequence |
|---|---|---|
| `bench/seb1_exp3_cross_validation.py` | `_make_case()` sets `resolved_category = distractor_category if resolves_to_distractor else target_category` **and** `gold_verdict = "CONTRADICTED" if resolves_to_distractor else "VERIFIED"`. `_decide_for()` then computes `attributes_match = (claimed_colour == resolved_colour and claimed_category == resolved_category)`, and `claimed_colour == resolved_colour` **always**, by line 61's comment ("the wrong order still shares the colour — that's the whole trap") | `attributes_match` is `not resolves_to_distractor`. Label and prediction are the same bit. Accuracy = 1.000 **identically**, for every seed, every n |
| `bench/seb1_exp5_confusion_matrix.py` | `_generate(gold)` sets exactly the input that `decide()` maps deterministically to `gold`: `days_ago ∈ [8,30]` for BLOCK, `Confidence.NONE` for ESCALATE, `Reliability.INFERRED` for SOURCE_UNRELIABLE | The matrix is diagonal unless `decide()` is broken. It is a **unit test rendered as a confusion matrix** |
| `controlplane/mutation.py` | All 6 operators each flip exactly one input that `decide()` is defined to react to | Mutation score = 1.000 by construction |
| `controlplane/bias_probe.py` | `group = rng.choice(["A","B"])` is drawn *after* the scenario and **never passed to `decide()`** | The null is structural. There exists no execution in which this probe reports a difference other than by sampling noise |

**None of these four can produce evidence against the system.** §17's classification for all four: **NOT FALSIFIABLE WITH CURRENT EVIDENCE.**

The repository is partly aware of this. `docs/invariants.md` frames the mutation score correctly ("a rigorous lower bound and a regression signal … not a real-world catch rate"). `bias_probe.py`'s docstring reasons carefully about what a null does and does not mean. But `README.md` presents Exp 3's numbers as a finding — *"Exp 3's result is real and worth stating: 100% verdict accuracy … 75% without it — exactly matching the 25% wrong-order-resolution rate the generator produces."* The clause after the dash **is the proof that it is a tautology**, presented as corroboration.

## E.2 Source-of-truth correctness, evidence independence, and degradation

The brief asks to separate current-state accuracy from source-of-truth correctness, evidence independence, staleness, incorrect authoritative state, and adversarial corruption. Applied to the repository:

| Question | Current evidence | Unanswered part | Best test |
|---|---|---|---|
| Is the gate correct **when the record is right**? | `tests/test_decide.py` (11 unit tests), Exp 5 (tautological) | Nothing, at unit level. This is established | — |
| Is the gate correct **when the record is stale**? | The v3.8/v4.2 supersession scenario — `data/seed/clauses.json`, `registry/policy.py`, `docs/evidence/negative_control.txt` | This is the project's genuine, real demonstration. **Established for n=1 scenario**, replayed from fixtures | Broaden to the branch's `stale_policy_context` slice (20 cases) once `label.py` lands |
| Is the gate correct **when the record itself is wrong**? | `Reliability.INFERRED` / `SOURCE_UNRELIABLE` machinery exists in `decide.py` | **The rule that produces it from real data is dead code.** `registry/freshness.py::escalation_for()` is called by nothing except `tests/test_registry.py:71,76`. `decide()` re-implements the floor independently. The only `inferred` field in the seed data is `orders.order_status`, which **no servicing claim reads** | Wire `escalation_for()` in, or delete it and say the floor is the mechanism |
| Is the gate correct **under adversarial corruption**? | None | No adversarial evaluation exists in any commit | See `09_G5_threat_model.md` |

**The repository's own `docs/gold-set.md` §5 states the first two of these findings before this audit did.** It names `escalation_for()` as dead code and states that the `corrupted_or_missing_record` slice's 15 gold verdicts "have no mechanism to fire" and that missing-record cases "currently **crash**, not escalate". That is an unusually honest register and it is the correct one.

## E.3 The M5 bug — §10 research significance

`README.md`, `controlplane/decide.py`'s docstring and `c653b7f`'s commit message all describe the same finding:

> "M5 (source-degradation monotonicity) failed on the very first Hypothesis run, twice, at two different scenarios. An earlier version applied the verdict precedence … *globally*: degrading ONE claim's evidence reliability could suppress a completely unrelated, still-fully-reliable claim's hard contradiction, turning what should stay BLOCK into the strictly more permissive ESCALATE."

| §10 question | Answer | Basis |
|---|---|---|
| Invariant | M5: a staler / lower-reliability source must never yield a more permissive intervention | `docs/invariants.md`; `tests/test_invariants.py::test_m5_source_degradation_monotonicity` |
| Triggering state | ≥2 load-bearing claims; one below the reliability floor, another with a reliable hard contradiction | `decide.py` precedence block |
| Old behaviour | global `SOURCE_UNRELIABLE > CONTRADICTED` precedence | **REPORTED only.** No commit contains it |
| Why incorrect | it lets a caller relax the outcome by *degrading its own evidence* — monotonicity in the wrong direction | Sound reasoning; the mechanism is real |
| Detection chronology | **EXACT COMMIT NOT RECONSTRUCTED.** `git log --all -- controlplane/decide.py` and `-- tests/test_invariants.py` both return exactly `c653b7f`. `git log --all -S "unreliable_and_would_violate"` returns only `c653b7f` | Fix, test and bug narrative all arrive in one commit |
| Did detection precede repair? | **NOT ESTABLISHED.** No failing-run log, no Hypothesis `.hypothesis` example database, no pre-fix commit. Per §1, retrospective wording is not proof | — |
| Repair | per-claim precedence + an intervention floor decoupled from the verdict label | `decide.py` lines 175–215 |
| Regression test | **YES, present and genuine** | `tests/test_invariants.py:112` |
| Frozen-result impact | none — no frozen results exist | — |

**Does M5 support "adversarially relevant soundness failure" or only "robustness/implementation defect"?**

**Implementation defect, with a real adversarial *shape*.** The honest formulation:

- ✅ Supported: *"A property-based invariant caught a monotonicity violation in our verdict-precedence logic, in which degrading one claim's evidence reliability could suppress an unrelated claim's contradiction and relax BLOCK to ESCALATE. It is fixed and carries a Hypothesis regression test."*
- ❌ Not supported: any framing as an *attack*, an *exploit*, or a *security result*. There is no threat model in the repository, no attacker capability is defined, no adversary can currently reach `decide()`'s `reliability_class` field (it is set by `registry/freshness.py` from a DB table, not by input), and no exploit was demonstrated. `decide.py`'s own wording — "exploitable by an agent (or a bug) that simply degrades its own evidence quality" — **overshoots**: nothing in the pipeline lets an agent choose its evidence's reliability class.
- ❌ Not supported: that the bug was found before the fix, as a matter of repository evidence. The claim is likely true and is worth making — but it must be sourced to the author's testimony, not to the repo.

**This is a legitimate, publishable-in-a-limitations-section engineering finding, and it should not be inflated past that.** §10's own instruction applies: *do not inflate a software defect into a formal security result.*

## E.4 What is genuinely falsifiable today

| Contribution | Falsifiable? | What would falsify it | Can current evidence produce that? |
|---|---|---|---|
| "No `claimed_*` field reaches the predicate engine" | **FALSIFIABLE** | any predicate reading a `claimed_*` field | **YES** — `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine` is a real test that could fail |
| "The policy resolver returns v4.2 regardless of what the agent retrieved" | **FALSIFIABLE** | resolver returning v3.8 | **YES** — `tests/test_registry.py::test_policy_resolver_returns_v42_even_when_agent_retrieved_v38` |
| "The DB build is byte-deterministic" | **FALSIFIABLE** | differing bytes across runs | **YES** — `tests/test_data.py::test_build_is_byte_deterministic` |
| "`decide()` is monotone in evidence quality" | **PARTIALLY FALSIFIABLE** | an M1/M5 counterexample | **YES for `decide()` alone.** M3 varies only `order_id`; M4 calls a pure function twice — both near-vacuous. And the invariants use a **test-local harness** with hand-supplied `predicate_result`, so they say nothing about extract → resolve → predicate |
| "The gate catches wrong refunds" | **NOT FALSIFIABLE WITH CURRENT EVIDENCE** | a wrong refund the gate allows | **NO** — every benchmark case's label is derived from the same variable the gate's input is derived from |
| "Independent current-source adjudication changes decisions" | **NOT FALSIFIABLE WITH CURRENT EVIDENCE** | a case where the fresh query and the agent's context agree yet the fresh query is wrong, or where independence provides no lift | **NO** — no arm of any experiment varies the evidence source. There is no A/B on independence anywhere in the repository |

**The last row is the most important gap in the project.** The README's thesis is *"Most AI checkers ask another AI for a second opinion. We ask the company's own systems for the actual answer."* Nothing in the repository compares those two conditions. The branch's plan (a B3 LLM-judge arm vs. trace-grounded vs. live-query pipelines) is exactly the right design and does not exist yet.
