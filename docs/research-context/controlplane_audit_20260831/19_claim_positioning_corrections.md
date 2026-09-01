# R. Claim / positioning audit and corrections

Method: grep of the shipped artifacts (`README.md`, `CLAUDE.md`, `docs/*.md`, every docstring, commit messages) for the §27 trigger words — *first, novel, unique, only, better, superior, beats, lower FPR, fully general, independent, external validation, state of the art, adversarial, robust, sound, secure, production ready*.

**Encouraging result: the words `first`, `novel`, `unique`, `state of the art`, `production ready`, `beats` and `superior` do not appear as self-claims anywhere.** The project does not currently overclaim novelty. The corrections below are about *precision*, *reproducibility* and *scope* — not about novelty inflation.

---

## R.1 Corrections required

### 1. "never from hand-typed numbers"
- **OLD:** *"`make report` regenerates `reports/` and `summary.json` from whatever's actually in `decisions.jsonl`, never from hand-typed numbers."* (README; echoed in `c653b7f`)
- **PROBLEM:** `bench/report.py:41-43` defines `MEASURED_GROUNDING_LOAD_MS = 13_209.0`, `MEASURED_GROUNDING_CALL_MS = 109.8`, `TYPICAL_PREDICATE_MS = 0.6`, and the promotion-cost chart is drawn entirely from them.
- **SAFE:** *"`make report` regenerates coverage, latency and confusion figures from `decisions.jsonl`. Two grounding-latency constants are carried by hand from a single measured session and are marked as such in the source and on the chart (n=1)."*
- **FOR THE STRONGER CLAIM:** log grounding latency into `decisions.jsonl` and delete the constants.

### 2. "the enterprise's own live systems of record"
- **OLD:** README's opening paragraph and the tagline.
- **PROBLEM:** for orders and entitlements, the agent and the verifier read **the same SQLite file**. Only the policy path is source-independent (`12` §K.4).
- **SAFE:** *"At decision time we re-query the record the claim is about, rather than trusting the agent's account of it. For policy clauses this is a genuinely different source from the agent's retrieval index; for order and entitlement data it is a fresh, correctly-scoped read of the same store."*
- **FOR THE STRONGER CLAIM:** an adapter to a store the agent has no path to.

### 3. "the single choke point" / non-bypassable control
- **OLD:** README; `docs/ROADMAP.md` §7 cites SEC 15c3-5's *"non-bypassable pre-execution control"* as precedent.
- **PROBLEM:** `dispatch_tool` branches on a caller-supplied `session.gate_enabled`; impls are ordinary module-level functions.
- **SAFE:** *"`dispatch_tool()` is the single call site through which this codebase invokes a governed tool. It is a code-structure discipline enforced by tests, not a process or privilege boundary — an in-process prototype cannot provide one."*
- **FOR THE STRONGER CLAIM:** out-of-process mediation. Out of scope; keep it a limitation.

### 4. "Exp 3's result is real and worth stating: 100% … vs 75%"
- **PROBLEM:** tautology (`10` §I.1, `13` §L.1). The README's own next clause proves it.
- **SAFE:** *"Exp 3 confirms the attribute check is wired end-to-end and reaches BLOCK on constructed wrong-order cases. Its accuracy figures are properties of the generator — the label and the predicate input are derived from the same variable — and we do not report them as performance."*
- **FOR THE STRONGER CLAIM:** score against `bench/label.py` (D-01/D-02).

### 5. "counterfactual-twin bias probe"
- **PROBLEM:** the group label is drawn after the scenario and never reaches `decide()`; the null is structural.
- **SAFE:** *"A structural independence check: `decide()` takes no protected-attribute input, and we verify that outcomes are independent of a label it never receives. This is not a bias measurement — bias, if present, would enter through retrieval or extraction, which this does not test."*
- **FOR THE STRONGER CLAIM:** a probe over bias-capable inputs reaching the extractor. Different, larger study.

### 6. "found a real soundness bug … exploitable by an agent"
- **PROBLEM:** two issues. (a) `git log --all -- controlplane/decide.py` returns only `c653b7f`; the pre-fix code exists in no commit, so detection-before-repair is **NOT ESTABLISHED** by repository evidence. (b) `reliability_class` is assigned by `registry/freshness.py` from a DB table; no agent-reachable input sets it, so "exploitable by an agent" describes an attack path that does not exist.
- **SAFE:** *"Property-based testing of `decide()` caught a monotonicity violation in our verdict-precedence logic: degrading one claim's evidence reliability could suppress an unrelated claim's contradiction and relax BLOCK to ESCALATE. Fixed by per-claim precedence plus an intervention floor, with a Hypothesis regression test. We did not demonstrate an exploit; evidence reliability is set from a source-metadata table, not from agent input."*

### 7. "C3 is bounded by published NLI SOTA (77.4%)"
- **PROBLEM:** 77.4 is Bespoke-MiniCheck-7B's LLM-AggreFact average (verified 2026-08-30). HHEM-2.1-Open — the model actually deployed — is not on that leaderboard, and Bespoke-MiniCheck was excluded on CC BY-NC grounds.
- **SAFE:** *"C3 is probabilistic. The best reported average on LLM-AggreFact is 77.4 (Bespoke-MiniCheck-7B). We deploy HHEM-2.1-Open, whose score on that benchmark we have not established, so C3 is treated as moderate confidence and never blocks."*

### 8. "USPS OIG found `delivered_at` scans problematic at 2.45%"
- **PROBLEM:** report 22-159-R23 (2023-05-11) reports 500 sampled, 318 (64%) inaccurate messages, **163** marked "Out for Delivery" while still at the post office, 46 missing, 497 nondescriptive. **2.45% does not appear.** Also, the repo says "origin office"; the report says "post office".
- **SAFE:** *"USPS OIG 22-159-R23 (2023) found 163 of 500 sampled packages (32.6%) displaying 'Out for Delivery' while still at the post office, and 64% of tracking messages inaccurate as to location, time or date."*
- Either locate the source of 2.45% or delete it. **This is the only unverifiable figure this audit found in the shipped code, and the project's own kill-list discipline (`docs/ROADMAP.md:81`) demands it be treated the same way as the seven figures already retired.**

### 9. "the four loggers"
- **PROBLEM:** logger 2 is `"status": "not_measured"` and logger 4 is `not_measured` unless grounding ran.
- **SAFE:** *"Four logging channels; two report measured values today, extraction accuracy is an explicit `not_measured` stub, and promotion cost reports only when grounding is enabled."* (The repo already says this in `telemetry.py`; align the README.)

### 10. "Same engine, different behaviour"
- **PROBLEM:** 4 of 9 manifest fields are read; for use case 2 only 2 differentiate; that graph is two identity aliases.
- **SAFE:** *"One engine, two manifests. Today the manifest differentiates the window, the authority ceiling, the reliability floor and the verdict handling; the remaining fields are declared for the design and not yet read by the engine."*

### 11. "Verified live" claims in the README
- **PROBLEM:** `docs/evidence/negative_control.txt` states `CP_MODE=fixture (replayed)`. The README's several "Verified live" phrases describe past sessions with no committed artifact.
- **SAFE:** mark each as *"observed in a live session on <date>, recorded as fixture `<hash>.json`; the committed transcript is a replay."*

### 12. `docs/gold-set.md` §5's `SystemExit` claim
- **PROBLEM:** false against that branch's own code (contradiction C-2).
- **SAFE:** delete the sentence, or make it true.

---

## R.2 Claims that are correct and should be kept verbatim

Recorded so the rewrite does not weaken them:

- *"the verifier never reads a date"* (`CLAUDE.md`) — **literally true and enforced** by `facts_for_predicate()` and `tests/test_predicates.py::test_no_claimed_field_reaches_the_engine`.
- The `reports/noise_sweep.png` disclosure — *"is not a noise sweep"*, with the chart's own title saying so. **Exemplary.**
- `bench/reviewer_console.py --auto-approve` — *"exists only to prove the console doesn't crash — it is explicitly NOT a measurement"*.
- The mutation-testing caveat (Just & Ernst, FSE'14) — *"a rigorous lower bound and a regression signal, not a real-world catch rate"*.
- The two licence exclusions (Bespoke-MiniCheck CC BY-NC, SDV BUSL-1.1) *"before we knew a public repository would be required"*.
- The Firecrawl `401` disclosure and the decision not to chase it.
- The `~3.8 KB` receipt disclosure against a `~2 KB` target.
- `docs/ROADMAP.md:81`'s **kill list of seven retired figures plus "the fabricated Runlayer sentence"**.
- `docs/gold-set.md`'s clustering, confounding and label-tell disclosures, and §6's refusal to allow the phrase "human validated".
- `docs/ROADMAP.md` §7's *"do NOT copy"* column, which pre-emptively forbids six specific overclaims — including *"don't claim Simplex's formal reachability guarantees"* and *"don't claim SEC 15c3-5 mandates a latency figure"*.

**This is a genuinely unusual body of self-restraint.** §27's rule — never turn *"we did not find"* into *"no prior work exists"* — is a rule this project already follows. The corrections in R.1 bring the remaining claims up to the standard the project has already set for itself.

---

## R.3 The one place §27's inverse risk applies

`docs/ROADMAP.md:900` states that a human-override-rate number *"four research passes confirmed does not exist anywhere in published form."*

**This is exactly the "we did not find ⇒ does not exist" inference §27 forbids.** Four unsuccessful searches are evidence of absence only in proportion to their coverage, which is not documented.
**SAFE:** *"We did not find a published human-override rate for this setting in our search; we do not claim none exists."*
