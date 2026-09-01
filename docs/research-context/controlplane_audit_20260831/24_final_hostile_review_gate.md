# §31 — Final hostile-review gate: disproving this audit's own conclusions

Every positive conclusion above was attacked. Surviving counterarguments are included, per §31.

---

### "Every reported accuracy is a tautology."
**What would make this wrong?** If `gold_verdict` were assigned by a process independent of `resolved_category` — e.g. if `bench/label.py` were in the loop.
**Result:** it is not, on `main` or the branch. `_make_case` computes both from `resolves_to_distractor`. **CONCLUSION SURVIVES.**
**Residual:** the author may hold a local version already wired to `label.py`. This audit sees only pushed commits (`01`). If so, the fix is a push, and this conclusion is about the repository, not the work.

### "There is no external validation."
**What would make this wrong?** An external dataset or evaluator anywhere in the tree.
**Result:** the only third-party artifact on the evidence path is HHEM-2.1-Open, disabled by default and exercised by two fixtures. **CONCLUSION SURVIVES.**
**Counterargument that has force:** using a third-party *model* (Qwen3-8B) and a third-party *rule engine* (Zen) is not nothing. **But neither supplies evidence** — one produces the thing being checked, the other evaluates project-authored expressions. The distinction is the one §5 insists on and it holds.

### "Prior art substantially overlaps."
**What prior paper would weaken this?** One showing that pre-execution gating against live record state was unpublished before ControlPlane.
**Result:** the opposite — arXiv 2607.07405 (2026-07-08) does deterministic read-only pre-execution gates that inspect "the proposed call **and current state**". **CONCLUSION SURVIVES, and is stronger than first stated.**
**Counterargument that survives and is included:** Reddy et al. run against a *simulated* τ²-bench DB and do not model version history, supersession, or per-field reliability. ControlPlane's *problem framing* — the record is versioned and itself fallible — is not covered by any source found. That framing is a real, if narrow, contribution.

### "AgentLTL grounds in the trace; ControlPlane grounds in the record."
**What would make this wrong?** An AgentLTL predicate that consults an external store.
**Result:** the primary source states atomic propositions are "evaluated globally over τ" with "no external data sources", and κ_ground ≡ `∀e ∈ ent(a), e ∈ out(τ)`. **CONCLUSION SURVIVES.**
**Residual counterargument, included:** AgentLTL's tools are *pure deterministic functions* by design (§8), so for its benchmark the trace **is** the record. The distinction is real but partly an artifact of different problem settings, not a capability gap. Do not overstate it.

### "The `MODIFY` path is a fail-open."
**What hidden dependency could explain this away?** If `modified_args` were populated somewhere this audit missed, or if `MODIFY` were unreachable.
**Result:** `grep -rn "modified_args"` returns exactly two hits — the field declaration in `schema.py:295` and the read in `intercept.py:173`. `decide()` returns `MODIFY` whenever `verdict_handling[v] == "allow_with_caveat"`, which `manifests/knowledge_assistant.yaml` sets for `UNVERIFIABLE`. **CONCLUSION SURVIVES.**
**Honest caveat:** reaching it requires an `UNVERIFIABLE` verdict on `send_document`, which requires a resolver returning `Confidence.NONE` — a missing doc or subject row. Not the default demo path. It is a **latent** fail-open, not an active one. Stated as such.

### "The gate crashes on a missing record."
**What would make this wrong?** A `try/except` around the Zen call, or a graph tolerant of nulls.
**Result:** `_run_gate` calls `evaluate_predicates` unguarded; `docs/gold-set.md` §5 states the graph raises `RuntimeError` on a null `delivered_at`. **CONCLUSION SURVIVES**, and rests partly on the project's own testimony rather than execution (§0). Labelled REPORTED + INFERRED, not MEASURED.

### "The bias probe cannot detect bias."
**What would make this wrong?** A channel from `group` to `decide()`.
**Result:** `group` is assigned after the scenario and passed nowhere. **CONCLUSION SURVIVES.**
**Counterargument with force, included:** the probe still verifies something worth verifying — that `decide()`'s signature admits no protected attribute, and that nothing leaks through the RNG. As an *architectural* assertion it is meaningful. Only the framing as a bias measurement fails.

### "The invariants are weaker than they read."
**What would make this wrong?** If M3/M4 varied something substantive, or if the harness were the real pipeline.
**Result:** M3 varies only `order_id`; M4 calls a pure function twice; the harness supplies `predicate_result` by hand. **CONCLUSION SURVIVES.**
**Counterargument that has real force:** M1 and M5 are genuine order-comparisons over `Intervention.rank`, and M5 is credited with catching a real bug. The suite is not decorative. The correct statement is that it is **narrower** than "the system is monotone in evidence quality" — it is "`decide()` is". Adjusted accordingly.

### "This project's honesty discipline is exceptional."
**What evidence would make this wrong?** A pattern of quiet overclaiming.
**Result of the adversarial search:** `first`/`novel`/`unique`/`state of the art`/`production ready` appear nowhere as self-claims. Six places refuse to report a number. A kill list of seven retired figures exists. **CONCLUSION SURVIVES.**
**But three real defects were found and are not withdrawn:** the "never from hand-typed numbers" contradiction (C-1), the false `SystemExit` claim (C-2), and the unverifiable USPS `2.45%`. The discipline is real and it is not perfect; both halves are stated.

### "Only one experiment is worth doing."
**What would make this wrong?** If the gold-set re-score were blocked, or if another experiment closed a gap it cannot.
**Result:** the gold set closes construct validity, leakage and falsifiability simultaneously (`22`, three rows, one experiment). Every alternative either presupposes it (the evidence-source ladder) or measures a known defect (A5-under-corruption).
**Strongest surviving counterargument, and it is genuine:** the **chaos test** (kill the policy store mid-decision, assert escalate-or-block) is independent of the gold set, costs half a day, is called by the ROADMAP itself *"the test that separates a demo from a system"*, and would produce a real result. This audit ranks it **#10, DO IF TIME** rather than second — but a reasonable reviewer could rank it second, and that disagreement is recorded rather than resolved in this audit's favour.

---

## What would most change this audit's conclusions

1. **A local worktree containing `bench/label.py`, `gold_set.jsonl` and the isolation tests.** That would move D-01/D-02 from OPEN to nearly-closed and change the top recommendation from "run the experiment" to "push it".
2. **Any τ² or AgentLTL integration held locally.** That would reopen §5 and §7's implementation columns, which this audit reports as NOT EXECUTABLE.
3. **The full text of the OAP specification** (`aport.io/spec/`, not fetched) or **C-Trace's Table 8** (not rendered). Either could narrow the surviving distinction further. Recorded as open counterarguments, not resolved.
4. **Execution.** §0 forbade running anything. Every DERIVED number here is analytic and short enough to check by hand, but none is MEASURED. If execution is permitted, the derivations in `13` are the first things to confirm.
