# RESEARCH GAP DECISION

*Repository: `github.com/hariom-s27/controlplane` · `main` @ `42143cf` · branch `p03-m4-blind-human-label-sheet` @ `8a48bf7` · audited read-only, 2026-08-30.*
*Scope note: the brief's τ²/AgentLTL/P02–P09/C1–C3/A1–A5/frozen-evidence premise is **EXPLICITLY ABSENT** from every blob in every commit on every branch. See `03_premise_reconciliation.md`. Everything below is decided against the artifact that exists.*

### Strong enough now

- **The claim/fact separation.** `ProposedAction.facts_for_predicate()` structurally prevents any agent-derived field from reaching the rule engine; `registry/policy.py::PolicyResolver` cannot receive the agent's assertion at all. Guarded by `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine`. This is the repository's strongest engineering claim and it is fully established.
- **The negative control.** Gate OFF → a refund executes 26 days past delivery under a 7-day policy; gate ON → BLOCK citing the currently-effective clause. One binary manipulation at one code branch, everything upstream held fixed. **IDENTIFIED, n=1.**
- **Determinism and the honest-refusal register.** Byte-deterministic DB build, frozen clock, single seed, content-hashed fixtures — plus six places where a number could have been invented and was not, and a kill list of seven retired figures.
- **The AgentLTL distinction, on primary-source evidence.** κ_ground ≡ `∀e ∈ ent(a), e ∈ out(τ)`; atomic propositions "evaluated globally over τ" with "no external data sources" (arXiv:2607.02599v1). ControlPlane re-queries the record. **SUPPORTED.**

### Needs P06 to establish

**Nothing — because P06 does not exist.** No file, blob or commit in this repository references P06, τ², or any A1–A5 arm. Per §20's own vocabulary the correct status is **NOT STARTED**, for C1 as much as for C2 and C3. No statement in this audit is conditioned on P06.

*The substantive question P06 was meant to answer — does independent current-source adjudication change decisions, and how often? — remains open, and its blocker is not P06. It is that no labels exist which the gate did not produce.*

### One additional experiment worth doing

**Score SEB-1 Exp 5 against `bench/label.py`'s labels over the 150-case gold set, with a paired case-cluster bootstrap over `source_order_id`.**

This is one experiment and it closes three gaps at once — construct validity, information leakage, falsifiability. It is 90% built: `docs/gold-set.md` (branch `8a48bf7`) describes `label.py` as sharing no code with the gate, re-deriving the 7-day window from clause **prose** rather than the manifest scalar, and never opening the construction holdout, with two AST/isolation tests enforcing it. **Five of those files are not committed.** The first act is `git push`, not experimental design.

Expect off-diagonal entries. Expect some to be the project's own defects — `docs/gold-set.md` §5 already predicts 15 gold verdicts with no runtime mechanism. That is the correct outcome and the reason to run it.

### Documentation-only limitation

- **Gate bypassability.** `intercept.py` branches on a caller-supplied `gate_enabled`; impls are ordinary functions. An in-process prototype cannot close this. Drop any SEC 15c3-5 "non-bypassable" framing.
- **No external validation.** One external component (HHEM-2.1-Open), off by default. Say so.
- **Synthetic corpus.** 109 orders, 3 hand-authored; policy text hand-authored after the Firecrawl `401`.
- **The 77.4% bound.** Belongs to Bespoke-MiniCheck-7B (LLM-AggreFact top entry, verified 2026-08-30), not to the deployed HHEM-2.1-Open. Restate with attribution.
- **The M5 bug.** Detection-before-repair is **NOT ESTABLISHED** — one mega-commit, no failing-run artifact. And "exploitable by an agent" describes a path that does not exist: `reliability_class` is set from a source-metadata table, not from agent input. Reframe as an implementation defect with a genuine regression test.
- **Clustering.** ALLOW slice = 50 cases on 5 source orders; effective n ≈ 5. Already disclosed by the project, correctly.

*None of these is closable by prose in the sense §24 forbids — they are claim-scope defects, and the correct closure for a claim-scope defect is fixing the claim.*

### Experiment not worth doing

- **Multi-seed anything currently committed.** Exp 5 and mutation return 1.000 for every seed; Exp 3's arms are analytic functions of two hard-coded probabilities. Seeds would decorate a tautology and lend false credibility to an invalid construct.
- **"A5-under-corruption" or any benchmark of the corrupted/missing-record path.** The answer is already known and documented: those paths crash (`RuntimeError` from the Zen graph) or have no mechanism (`escalation_for()` is dead code). **Fix the code; do not measure the defect.**
- **A third domain, or more policy variants.** Generality is not the binding constraint; construct validity is. And 5 of 9 manifest fields are already read by no code.
- **An adversarial red-team, today.** Two fail-opens stand (`MODIFY` executes unmodified args; a null from the predicate engine is treated as pass). A red team would measure the bugs. Worth doing after they are fixed.
- **τ²-bench / BFCL integration, before the deadline.** Very high value eventually; wrong order now.

### Biggest reviewer vulnerability

**Every reported accuracy figure is a tautology of its own generator, and the README hands the reviewer the proof.**

In `bench/seb1_exp3_cross_validation.py::_make_case`, `gold_verdict` and `resolved_category` are both computed from `resolves_to_distractor`; the colour always matches by construction; so `attributes_match ≡ not resolves_to_distractor` — the predicate input **is** the label. Accuracy-with = 1.000 identically; accuracy-without = `1 − 0.5×0.5` = 0.75. In `seb1_exp5_confusion_matrix.py::_generate`, each gold class is produced by setting exactly the input `decide()` maps to it. The mutation score is 1.000 by construction. The bias probe's null is structural.

And the README's own sentence — *"75% without it — **exactly matching the 25% wrong-order-resolution rate the generator produces**"* — states the arithmetic identity and presents it as corroboration. A reviewer needs five minutes and no execution.

### Biggest research-integrity strength

**The project finds and writes down its own defects before anyone else does, including defects that hurt.**

`docs/gold-set.md` §5 names `registry/freshness.py::escalation_for()` as dead code; states that missing-record cases "currently **crash**, not escalate"; states that 15 of its own gold verdicts "have no mechanism to fire"; states that 50 ALLOW cases sit on 5 source orders and demands cluster-robust intervals; states that a bare "outside window → BLOCK" rule *passes* three other slices without exercising the intended check; and names four cases whose justifications leak the answer. `docs/ROADMAP.md:81` carries a kill list of seven retired figures and "the fabricated Runlayer sentence". `bench/agreement.py` refuses to print a partial Cohen's κ. `reports/noise_sweep.png` says in its own title that it is not a noise sweep.

**This audit re-derived every one of those findings independently from source and found the register accurate.** That is rarer than any accuracy number in the repository, and it is the project's real claim to being taken seriously as research. It belongs in the README, not on an unmerged branch.

### Strongest defensible contribution

> **A pre-execution gate that adjudicates the *content* of a proposed tool call against a freshly-queried business record rather than against the agent's account of it — with agent-derived fields structurally barred from the rule engine, a claim-checkability taxonomy that keeps confidence claims honest (deterministic checks certain; entailment-based checks moderate and never blocking), and a signed receipt recording the query that established each fact. Demonstrated on one constructed silent-supersession scenario. No performance measurement is reported.**

The distinguishing element against the nearest prior art is narrow but real and primary-source-supported: AgentLTL grounds in `out(τ)`; Bedrock's Automated Reasoning checks explicitly consults no external data; AgentCore Policy's documented inputs are identity, tool schema, session events and content-safety signals; Reddy et al.'s state is a simulated benchmark DB with no version history. **Adjudicating against a versioned record that can silently change is not covered by any source located in this audit.**

### Strongest claim that remains unsupported

> **"…and measure when that additional independence changes the decision."**

Nothing in this repository measures it. There is exactly one evidence configuration; no arm varies the evidence source; the only comparison is gate-ON vs gate-OFF at n=1, which measures whether checking happens at all — not what independence contributes. The verb *measure* and the adjective *differing* are the two words in the proposed contribution statement that do the intellectual work, and both are unsupported.

Runner-up, for the same reason: *"the enterprise's own live systems of record."* For the orders and entitlement paths, the agent and the verifier read **the same SQLite file**. The independence demonstrated there is re-derivation and freshness, not source separation. `controlplane/registry/base.py`'s own wording — *"two independent reads of the same store"* — is the accurate one; the README's is not.

### Last experiment worth doing

**The gold-set-scored confusion matrix.** After it, the next question — the four-arm evidence-source ladder (agent prose / retrieved context / cached snapshot / fresh query, paired over identical cases, cluster-bootstrapped) — becomes both *possible* and *the obvious next paper*. It is not possible before, because without independent labels the arms would score themselves.

Anything after that ladder is a different project: an external benchmark, a threat model with a red team, a third domain.

### Point of diminishing returns

**Immediately after the gold-set re-score and the sub-day fix list.**

Concretely, the returns collapse once these are done:
1. push `bench/label.py`, `gold_set.jsonl`, `ground_truth_holdout.jsonl` and the two isolation tests;
2. re-score Exp 5 against them, with a cluster bootstrap over `source_order_id`;
3. fix `MODIFY`-executes-unmodified-args (~3 lines), the missing-record crash (~10 lines), and `scripts/gate_check.py`'s arity (**1 line**);
4. commit `reports/summary.json` and a truncated `decisions.jsonl` under `docs/evidence/`, stamped with the git SHA and environment;
5. rewrite the twelve claims in `19_claim_positioning_corrections.md`.

That is under two days and it removes roughly half the hostile-reviewer surface. **Every additional experiment after it buys less than the sentence "we demonstrate the mechanism; we do not yet measure how often the answer differs" buys for free** — because that sentence converts the project's largest vulnerability into its stated scope, and this project has already shown, seven times over, that it knows how to write that sentence.
