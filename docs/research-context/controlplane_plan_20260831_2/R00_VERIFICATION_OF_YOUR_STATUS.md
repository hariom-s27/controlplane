# Verification of your status document

**Checked 2026-08-31 against `github.com/hariom-s27/controlplane`, re-fetched live.**

## 0. The finding that governs everything else

**The public repository has not changed since my last audit. Nothing you describe has been pushed.**

```
git fetch --all --prune
refs on origin:
  main                              42143cf   2026-08-29 16:43 +0530
  p03-m4-blind-human-label-sheet    8a48bf7   2026-08-30 17:44 +0530
total commits, all refs: 4
```

Present on **no** pushed ref: `tau2` (anything), `adapters/tau2_retail.py`, `manifests/tau2_retail.yaml`, `tests/test_manifest_hardening.py`, `bench/label.py`, `bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`, `tests/test_label_independence.py`, `docs/experiment-audit.md`, `reports/p06-c1-freeze.json`.

`git log --all -S` returns **0** commits for `ORDER_STATUS_SUPPORTS_ACTION`, `status_supports_action`, and `tau2_retail`.
`git ls-remote --heads origin` shows **no** `p11-readme-reconciliation` branch.
`b4ef009` — the base commit you say your P11 worktree was cut from — **does not exist in the public repository**. Your local history has diverged from public `main` by more than a few commits.

*(Note: `5adbd96…`, `fb9dd57…`, `4a8c229…` are content hashes of artifacts and a test file, not commits. Their absence from the public repo is expected and is not a finding.)*

### What this means for the verification you asked for

I can verify three classes of claim, and only three:

| Class | Verifiable? | Method |
|---|---|---|
| **Literature / prior-art claims** | **YES, fully** | fetched primary sources today |
| **Logical / statistical / methodological reasoning** | **YES** | internal consistency, standard inference rules |
| **Repository state claims (P02 fixes, C1/C2 freeze, tau2 integration, zero tool calls, bench/label.py)** | **NO** | not in any pushed ref |

Every repository claim below is therefore marked **UNVERIFIABLE — LOCAL ONLY**. That is not a criticism of the work; it is a statement about what is checkable. But it *is* itself a finding: **your freeze is not a freeze in the reproducibility sense.** A frozen artifact that exists only in a local worktree plus an external archive cannot be checked by anyone, cannot be cited, and cannot survive a laptop failure. Your own note R1 says this; I would raise its severity from "LIMITATION" to **P0**, and I put a fix in the plan (`R04`, Phase 0, item 3) that costs ~20 minutes and does not require publishing any result.

---

## 1. Where your reasoning is CORRECT — and better than my audit's

These are not rubber stamps. Each one is a judgement I checked and would defend against a hostile reviewer.

### 1.1 **C2-3 — "the rates are UNDEFINED, not zero."** ✅ CORRECT, and this is the sharpest single call in your document.
`N_attempted_writes = 0` ⇒ block recall, false-block rate and policy-violating-write rate are ratios with an empty denominator. They are **not estimable**, not 0. Reporting `0%` would be a false precision error of the kind that ends a review. Hold this line even when it makes the results table look empty. An empty cell labelled `NOT ESTIMABLE (N=0)` is a stronger artifact than a `0%`.

### 1.2 **C2-2 / C2-4 — separating "machinery structurally demonstrated" from "governance efficacy established."** ✅ CORRECT.
This is exactly the distinction my §5 insisted on and you drew it yourself, unprompted. Keep both statements adjacent in every future write-up so a reader cannot collapse them.

### 1.3 **"ControlPlane had no effect" is too strong; "the treatment was not exercised" is right.** ✅ CORRECT.
This is the difference between a null result and an unrun experiment. Getting this wrong is the most common way a paper gets desk-rejected for overclaiming in the *negative* direction.

### 1.4 **C3-1 / C3-2 — do not run same-config C3; a config change means a new C1′.** ✅ CORRECT, and it is proper protocol discipline.
Your reasoning — the treatment mechanism *requires* a tool call to exist, so varying the policy context cannot produce a governance signal — is valid and is stronger than "low expected value." And refusing to splice `old C1 → new C2 → old C3` into one controlled sequence is exactly right: changing model, provider, tool-choice mode or agent implementation changes the data-generating process, so the baseline must be re-drawn.

### 1.5 **P12 is closed/obsolete; do not retroactively append it and call it preregistered.** ✅ CORRECT.
Preregistration is only meaningful when it precedes the result. Reconstructing it afterwards would destroy the one thing that made it valuable.

### 1.6 **"Write Actions 0/39" ≠ "0 attempted writes out of 39."** ✅ CORRECT and subtle.
τ²'s action-check field encodes the *golden expected* action set. Conflating an expected-action denominator with an attempted-write denominator would manufacture a denominator from the answer key. This is the same class of error as the tautological labels in my `10_benchmark_construct_validity.md`. Good catch.

### 1.7 **Withdrawing the "ControlPlane can never improve Pass^1" floor-effect argument.** ✅ CORRECT self-correction.
A BLOCK can cause a retry that succeeds, so governance can in principle raise Pass^1. Replacing a general theorem with the run-specific statement ("zero tool calls occurred, so no intervention could affect outcomes in this pair") is both weaker in scope and stronger in logic. That trade is always the right one.

### 1.8 **Do not speculate about provider internals (ONNX/vLLM/TGI).** ✅ CORRECT.
"Under the locked Kimi-K2-Instruct/Featherless configuration, no native structured tool calls were observed" is the claim the evidence supports. Anything about *why* is unverified.

### 1.9 **M5 = integrity/soundness defect with adversarial relevance, not a demonstrated security result.** ✅ CORRECT — matches my `06_G3_falsifiability.md` §E.3 independently.

### 1.10 **Latency and cost are UNAVAILABLE; do not reconstruct from terminal timestamps or edit LiteLLM pricing.** ✅ CORRECT.
"Model isn't mapped yet" ≠ cost $0. Retrofitting instrumentation into a completed experiment to rescue a number is exactly the move that makes a frozen artifact meaningless.

### 1.11 **P10 must wait for the audit; do not position before the experimental state settles.** ✅ CORRECT sequencing.

### 1.12 **P02-B — "same engine, different manifest" is too strong.** ✅ CORRECT, and I can add hard evidence from the public code: on public `main`, of nine manifest keys, **five are read by no code at all** (`latency_budget_ms`, `escalation_budget_pct`, `fail_posture`, `evidence_retention_days`, `risk_tier_default`), and the knowledge-assistant JDM graph is two identity aliases. So the claim is not merely unproven, it is **contradicted by the published artifact**. Narrow the wording; do not spend 5–6 hours on the refactor now. (`02_evidence_ledger.md` A-07.)

### 1.13 **`ORDER_BELONGS_TO_CUSTOMER` — refusing to synthesise the claim from hidden evaluator state or prior agent output.** ✅ CORRECT and it is the single best methodological decision in your document.
Using evaluator ground truth to resolve a claim would rebuild the exact circularity my construct-validity audit flagged four times. Document it as a limitation. Do not "fix" it.

### 1.14 **Your "what NOT to do" list.** ✅ I agree with all eleven items, and would add three (see `R03`).

### 1.15 **AEGIS identifier.** ✅ **YOU ARE RIGHT AND I WAS WRONG.** See `R01_MY_CORRECTIONS.md` §1. This materially changes the prior-art picture, and not in your favour.

---

## 2. Where I would CORRECT or SHARPEN you

### 2.1 "C1 = FROZEN / C2 = FROZEN" — **downgrade to `SEALED LOCALLY, NOT PUBLISHED`**

A freeze has three properties: immutable, *hash-committed*, and *retrievable by a third party*. Yours has the first two and not the third. `reports/p06-c1-freeze.json` is on no pushed ref, and your own R1 notes `reports/*` is gitignored.

**Consequence:** if a reviewer (or you, in three weeks) asks "was this the artifact that produced that number?", there is no way to answer. And "frozen" becomes an unfalsifiable claim — which is precisely the property you have been rigorous about avoiding everywhere else.

**Cheap fix, no results published:** commit a `docs/evidence/p06/` directory containing *only* the SHA-256 manifest, the run configuration, the seed, the model/provider string, the row counts, and a `PROVENANCE.md` saying where the raw archive lives. That is 20 minutes, publishes no unfinished result, and converts "frozen" from an assertion into a checkable fact. (`R04` Phase 0.)

### 2.2 The zero-tool-call finding is **under-evidenced in one specific place**, and it is the place a reviewer will attack

You establish: *tools supplied → raw response has `tool_calls = null`, `function_call = null` → parser sees nothing → no dispatch → no interception.*

The weak link is the **first arrow**. "Tools were supplied" is currently your testimony. A hostile reviewer's first question is not "did the model refuse?" — it is **"did you actually send the tools, in the shape the provider expects?"** Empty `tool_calls` is exactly what you get from a malformed or dropped `tools` array, an unsupported `tool_choice` value, or a wrapper that silently strips the field.

**What closes it:** the archived *request* payload, not just the response. One captured request/response pair, with the `tools` array visible in the request and `tool_calls: null` in the response, converts this from testimony into evidence. If you have it, freeze and cite it. If you do not, capture it — it is one request. **This is the highest evidence-per-minute action available to you right now.**

### 2.3 You are treating the zero-tool-call result as a failure. It is your **strongest available result** — but only if you instrument it

Reframed: *"A locked, published model/provider configuration, given a standard τ²-bench tool schema, emitted zero native structured tool calls across 80 tasks, so the governance treatment could not be exercised."* That is a reproducible infrastructure finding about the gap between benchmark harnesses and provider tool-calling, and it is the kind of thing that saves other people weeks. τ²-bench-verified exists precisely because this class of misalignment is real.

To be publishable it needs three things you may already have: the request payload (§2.2), the exact provider/model/date, and the **negative control** in §2.4.

### 2.4 **The single biggest gap in your plan: you have not localised the fault.**

Your plan jumps from *"C1/C2 emitted no tool calls"* straight to *"build a new tool-calling-capable track with a new C1′."* But you do not yet know which of four layers is at fault:

```
(a) model            Kimi-K2-Instruct cannot/will not emit tool calls
(b) provider         Featherless does not surface them on this route
(c) tau2 agent path  the agent config used doesn't pass tools / uses a solo mode
(d) your adapter     tools dropped or reshaped before the request
```

Each implies a **completely different** and differently-priced remedy. (c) and (d) are free to fix. (a) means a new model. (b) means a new provider.

**The discriminating test costs about ten minutes and a few cents:** a single direct request to Featherless/Kimi-K2 with one trivial tool schema and `tool_choice` at default, entirely outside τ², and a second with `tool_choice="required"` if the route accepts it. Four outcomes, four different plans (`R03` §1). **Do this before anything else on the experimental side.** Committing to a new track without it risks paying for a model switch to fix a config bug.

### 2.5 Your priority order — one change

You have: `P11 → C1 forensic accounting → tool-call fix → local proof → C1′`.

I would run the ten-minute probe (§2.4) **first**, because it is ten minutes and its outcome determines whether items 3–5 are even the right items. Then P11, which is hours of careful work and needs your full attention. The probe and P11 do not compete for the same resource.

### 2.6 "P02 broader generic-engine claim NOT ESTABLISHED" — agreed, and here is the sharper wording

Not *"the architecture is use-case agnostic"* but: *"the engine is configured per use case by a manifest and a predicate graph; the two implemented use cases share the decision core, and the remaining manifest fields are declared but not yet consumed."* That sentence is defensible against `grep`.

### 2.7 Your §31 "real bugs" table — three rows say "verify final evidence"

Do not publish any of those as FIXED until you can name the commit. This is the same discipline as the M5 chronology problem in my audit: `git log --all -S` on the fix string must return a commit, or the status is **REPORTED, NOT ESTABLISHED**. Rows affected: empty LLM completion handling, SOURCE-UNRELIABLE NULL handling, idempotency/duplicate execution, SQLite lifecycle, ESCALATE workflow gap.

### 2.8 One item on your "do not do" list I would soften

*"Do not force-add files merely to make the repository look cleaner"* — right in spirit. But adding a **hash manifest and provenance file** for a frozen run is not cosmetic; it is the mechanism that makes the freeze real (§2.1). Distinguish "force-adding generated artifacts to look tidy" (don't) from "committing an integrity manifest so the freeze is checkable" (do).

### 2.9 LedgerAgent is not a generic citation. It is your **nearest competitor**, and you listed it without registering that.

See `R01` §2 and `R02`. Short version: **arXiv:2606.20529, LedgerAgent — "the ledger is also used to check state-dependent policy constraints *before environment-changing tool calls are executed*"**, in customer-service domains, reported on pass^k. Pre-execution, policy-constrained, state-backed, same domain family. Your distinction survives — its ledger is built from user interactions and tool returns, i.e. trace-derived, not an independent re-query — but it is now a **one-clause** distinction and must be stated against this paper by name.

---

## 3. Claims I could not check at all

| Claim | Status |
|---|---|
| P02-1 `ORDER_STATUS_SUPPORTS_ACTION` wiring; 70/70 and 335/335 suites | UNVERIFIABLE — LOCAL ONLY |
| P02-2 `tau2_retail` resolver vocabulary | UNVERIFIABLE — LOCAL ONLY |
| P02-3 snapshot `fb9dd57…` → `4a8c229…` | UNVERIFIABLE — LOCAL ONLY (and these are file hashes, not commits) |
| C1 archive hash `5adbd96…` | UNVERIFIABLE — LOCAL ONLY |
| 40 / 27 / 10 / 3 task accounting; D3's predicted 11-task set | UNVERIFIABLE — LOCAL ONLY |
| C1+C2 = 0/80 native tool calls | UNVERIFIABLE — LOCAL ONLY. **And see §2.2: the request-side evidence is the part that needs strengthening even locally** |
| `p11-readme-reconciliation` @ `b4ef009` | Branch not on origin; base commit not in public history |
| P04, P05, P08, P13 | No trace on any pushed ref |

**None of this means the work does not exist.** It means that today, the only auditable ControlPlane is a four-commit repository from 29 August whose README still carries the retired 100%/75% figure. That gap is your largest *practical* risk and it is what P11 exists to close.
