# O. Hostile reviewer round — the 20 strongest objections

Ranked by (severity × validity × likelihood × ease of attack), hardest to rebut first.
Each: **OBJECTION → EVIDENCE → VALIDITY → CURRENT RESPONSE → EVIDENCE NEEDED → fixable by documentation? by experiment? must remain a limitation?**

---

**1. Every reported accuracy is a tautology of its own generator.**
*Evidence:* `bench/seb1_exp3_cross_validation.py::_make_case` derives `gold_verdict` and `resolved_category` from one variable; `bench/seb1_exp5_confusion_matrix.py::_generate` sets exactly the input `decide()` maps to each gold class.
**VALID.** The most damaging objection, and it is unanswerable as things stand.
*Current response:* none available. *Needed:* labels the gate did not produce — `bench/label.py` + `gold_set.jsonl`, already designed on the branch.
Documentation? **No.** Experiment? **Yes — one, and it is 90% built.** Limitation? Only if the branch is abandoned.

**2. There is no external validation of any kind.**
*Evidence:* `05_G2_external_validation.md` — one third-party component (HHEM-2.1-Open), disabled by default.
**VALID.** *Current response:* honest concession. *Needed:* an off-repo benchmark (τ²-bench-verified, BFCL).
Documentation? No. Experiment? Yes, but **large** — do not attempt before #1. Limitation? **Yes, for now, and say so plainly.**

**3. Deterministic read-only pre-execution gating is published prior art.**
*Evidence:* arXiv 2607.07405 (τ²-bench airline, +12.4pp gpt-4o-mini P=0.0012, +10.4pp gpt-5.2); arXiv 2603.20953 (synchronous interception + declarative policy + signed audit record, 53 ms median).
**VALID against any novelty claim for the mechanism.** *Current response:* `docs/ROADMAP.md` §7 already cites Reddy et al. and instructs the author to "cite it generously and unprompted" — correct instinct. *Needed:* a narrowed claim (`20_contribution_statement.md`).
Documentation? **Yes — this one is genuinely a positioning fix.** Experiment? No. Limitation? No.

**4. "MODIFY" executes the original arguments — a silent fail-open on the privacy use case.**
*Evidence:* `Decision.modified_args` is never assigned anywhere in the repository; `intercept.py:173` = `impl(**(decision.modified_args or args))`; `manifests/knowledge_assistant.yaml` maps `UNVERIFIABLE: allow_with_caveat` → `MODIFY`.
**VALID and severe.** An unresolvable `send_document` **sends the document unchanged**. *Needed:* a 3-line fix.
Documentation? No. Experiment? No. **Implementation, today.**

**5. A missing record crashes the gate instead of escalating.**
*Evidence:* `docs/gold-set.md` §5 — `_run_gate` calls the Zen graph before `decide()` with no `try`/`except`; the graph raises on a null `delivered_at`. Corroborated by reading `intercept.py::_run_gate`.
**VALID, and the project found it first.** *Current response:* documented; assigned to "P08". *Needed:* guard the call.
Documentation? Partially (it is already documented). Experiment? No. **Implementation.**

**6. The claimed "system of record independence" is, for two of three paths, the same file.**
*Evidence:* `agents/servicing_agent.py::_recent_orders` reads `data/orders.db`; `registry/orders.py` reads `data/orders.db`. Same for entitlements. Only the policy path is source-independent.
**VALID.** *Current response:* `registry/base.py`'s docstring already says "two independent reads of the same store" — the accurate wording. The README's is not.
Documentation? **Yes** — distinguish *source independence* from *re-derivation* (`12` §K.4). Experiment? No.

**7. The bias probe cannot detect bias.**
*Evidence:* the group label is drawn after the scenario and never passed to `decide()`.
**VALID.** *Current response:* the docstring's hedges are good but the framing ("counterfactual-twin bias probe") oversells.
Documentation? **Yes** — rename it an independence check. Experiment? A real probe would need bias-capable inputs (names, addresses) reaching extraction — a different, larger study. Limitation? Yes.

**8. The manifest is mostly decoration.**
*Evidence:* `latency_budget_ms`, `escalation_budget_pct`, `fail_posture`, `evidence_retention_days`, `risk_tier_default` are read by **no code** (grep across all `.py`/`.json`). The knowledge-assistant JDM graph is two identity aliases.
**VALID.** *Current response:* README concedes escalation rate-limiting only.
Documentation? Partially. **Implementation** for `fail_posture` — it is the one that matters, because the ROADMAP's Simplex-derived safety argument depends on it.

**9. There is no threat model, and the one test the ROADMAP calls essential was not built.**
*Evidence:* `docs/ROADMAP.md` §6: *"The one test worth naming in the README: chaos-test the verifier itself."* No such test exists. Compare OAP's 879 adversarial attempts.
**VALID.** Documentation? Only to scope it out. Experiment? A chaos test is ~half a day and would be the second-best experiment available. Limitation? Yes if not done.

**10. The M5 bug's chronology is unverifiable, and its framing overshoots.**
*Evidence:* `git log --all -- controlplane/decide.py` returns only `c653b7f`; the pre-fix version exists in no commit. `decide.py`'s docstring calls it "exploitable by an agent … that simply degrades its own evidence quality", but `reliability_class` is set by `registry/freshness.py` from a DB table and is not agent-reachable.
**VALID.** Documentation? **Yes** — reframe as an implementation defect with a real regression test (`06` §E.3). Experiment? No.

**11. The "signed audit trail" has no chaining, no non-repudiation, and does not cover telemetry.**
*Evidence:* `receipt.py` — shared-secret HMAC, no sequence, no chain; `telemetry.py::record` signs only the `receipt` sub-object. Compare Aegis's Immutable Logging Kernel.
**VALID.** Documentation? Partially. **Implementation** (a prev-hash field is ~10 lines) — cheap and high credibility-per-hour.

**12. The gate is bypassable by construction.**
*Evidence:* `intercept.py:165` branches on a caller-supplied `session.gate_enabled`; impls are ordinary module-level functions.
**VALID as a security claim; INVALID as a criticism of a prototype.** The ROADMAP invokes SEC 15c3-5's "non-bypassable pre-execution control" as precedent, which invites the attack.
Documentation? **Yes** — drop any non-bypassability framing. **Must remain a limitation.**

**13. `escalation_for()` is dead code, and `SOURCE_UNRELIABLE` cannot fire from real data.**
*Evidence:* called only from `tests/test_registry.py`; the sole `inferred` field (`orders.order_status`) is read by no servicing claim. `docs/gold-set.md` §5 states this.
**VALID.** Documentation? No. **Implementation** — wire it, or delete it and say the floor in `decide()` is the mechanism. Tests that exercise dead code inflate apparent coverage.

**14. `make report` claims never to use hand-typed numbers, and its only chart is three hand-typed numbers.**
*Evidence:* contradiction C-1; `bench/report.py:41-43`.
**VALID.** Documentation? **Yes**, immediately — this is the kind of contradiction that costs disproportionate credibility because the project's whole pitch is honesty.

**15. The anti-staging evidence cannot be regenerated.**
*Evidence:* D-R1 — `gate_check.py` unpacks 3 from a 4-tuple.
**VALID.** Documentation? No. **Implementation — one line.**

**16. The 77.4% bound belongs to a model the project deliberately does not run.**
*Evidence:* LLM-AggreFact top entry is Bespoke-MiniCheck-7B (77.4); HHEM-2.1-Open is not on the leaderboard; `requirements.txt` excludes Bespoke-MiniCheck on CC BY-NC grounds.
**VALID.** Documentation? **Yes** — restate the bound with attribution (`05` §"the one real external anchor"). Or measure HHEM on LLM-AggreFact — a genuinely cheap experiment, though not a priority.

**17. The metamorphic invariants are weaker than they read.**
*Evidence:* `tests/test_invariants.py` uses a test-local harness with hand-supplied `predicate_result`; M3 varies only `order_id`; M4 calls a pure function twice.
**PARTIALLY VALID.** M1/M5 are real and one of them caught a real bug. M3 and M4 are near-vacuous, and none covers extract→resolve→predicate.
Documentation? **Yes** — state that the invariants are properties of `decide()`, not of the pipeline. Experiment? Lifting them to `dispatch_tool` is a genuinely good, cheap idea.

**18. Two domains, one of which has no rule layer.**
*Evidence:* `knowledge_assistant.json` = two identity expressions; the entitlement decision is Python in `registry/entitlements.py`, returning verdict-shaped booleans in violation of `registry/orders.py`'s stated "never a verdict" contract.
**VALID.** Documentation? Partially. **Implementation** — move the two membership tests into the graph; it is a small change that would make the generality claim real rather than nominal.

**19. The receipt-size test cannot fail on the case the claim is about.**
*Evidence:* `tests/test_receipt.py` uses 1 claim / 1 evidence; README concedes the real receipt is ~3.8 KB.
**VALID but minor**, and README already discloses it. Documentation? Change the test's name and assert against the real BLOCK receipt with the true bound.

**20. The gold-set documentation describes files and tests that are not in the repository.**
*Evidence:* `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl`, `exp3_checker.py`, `docs/experiment-audit.md`, `test_label_independence.py`, `test_gold_set_holdout_isolation.py` — all absent from `8a48bf7`. And §5's `SystemExit` claim is false against that branch's own code.
**VALID.** Documentation? No. **Push the files.** This single act would answer objections #1, #2 (partially) and #20 together.

---

## Objections a reviewer might raise that are **INVALID** — rebut these confidently

- *"SQLite is not a system of record."* **INVALID for what is demonstrated.** `data/build_db.py`'s docstring pre-empts it correctly: the liveness that matters is procedural (two reads at two times), not infrastructural.
- *"The demo is prompt-engineered."* **INVALID in intent, currently unprovable in fact.** `agents/servicing_agent.py`'s `SYSTEM_PROMPT` describes the process, never the answer; `scripts/gate_check.py`'s own docstring says *"If it fails: fix the retrieval, never the prompt."* The discipline is real; only D-R1 blocks the proof.
- *"You use an LLM to check an LLM."* **INVALID.** `CLAUDE.md` hard constraint #3 forbids LLM-as-judge on the critical path, and the code honours it: the only model on the path is the extractor, restricted to 4 nullable fields by `_ClaimedFields`, and grounding is off by default and never blocks (C3 → ESCALATE, never BLOCK, per D3).
- *"Claiming 100% deterministic coverage is absurd."* **INVALID.** The project explicitly refuses that claim — `ground.py`'s docstring: *"Without it you'd be claiming 100% deterministic coverage, which nobody will believe."* Building a real C3 tier to keep the coverage number honest is a genuinely good methodological decision.
- *"PII detection is weak."* **INVALID as a criticism.** `pii.py`'s docstring concedes regex name-detection is "moderate at best", and `ladder.py` deliberately marks the PII claim **not load-bearing** — which is the second use case's actual thesis. This is a designed position, well argued.
