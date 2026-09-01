# Claude Code prompts — paste-ready, in run order

Each prompt is self-contained. Every one carries an explicit guardrail block, because the single biggest risk in this project is an agent helpfully "fixing" a frozen artifact.

**Universal preamble — paste at the top of every session:**

> Work only in the repository/worktree I name. Never modify, regenerate, delete or re-run anything under a frozen P06 artifact path (C1, C2, their manifests, their raw logs, their hashes). Never edit git history. Never `git push` unless the prompt explicitly says to. If a task appears to require changing a frozen artifact, stop and tell me instead of doing it. When you are unsure whether something is established, say `NOT ESTABLISHED` rather than inferring. Never invent a number: run the thing and paste the real output, or leave it blank and say it is unmeasured.

---

## CC-1 · Fault-localisation probe (Phase 0.1) — RUN FIRST

> **Goal:** determine which of four layers is responsible for zero native tool calls in P06 C1/C2 — the model, the provider, the τ² agent/harness configuration, or our adapter.
>
> **Guardrails:** read-only with respect to the repo. Do not modify any C1/C2 artifact. Do not start a benchmark. Total spend must stay under a few cents. Write new files only under `probes/toolcall/`.
>
> **Task — build a single standalone script `probes/toolcall/probe.py` that runs four independent cases and writes each full request and full raw response to disk as JSON:**
>
> - **P1** — direct provider call, our locked model, exactly one trivial tool schema (`get_weather(city: str)`), a user message that plainly requires it, `tool_choice` at provider default, `max_tokens` set generously (≥1024).
> - **P2** — identical to P1 but with `tool_choice="required"` (or this route's nearest equivalent). If the route rejects the parameter, record the error verbatim; that is a result.
> - **P3** — the same logical request routed through *our* client/wrapper and the τ² agent path, so the difference between P1 and P3 isolates our adapter.
> - **P4** — direct provider call, but with one real τ² retail tool schema pasted verbatim, to test whether schema shape (nesting, `strict`, enums, `$ref`, description length) is the trigger.
>
> For each case persist: the exact request body sent, the exact raw response body, HTTP status, latency, and a one-line verdict `TOOL_CALL_PRESENT` / `TOOL_CALL_ABSENT` / `ERROR`. Redact API keys.
>
> **Deliverable:** `probes/toolcall/RESULTS.md` with a 4-row table (case, tool call present?, evidence file, one-line interpretation) and a single explicit conclusion sentence naming which layer is implicated. Also state clearly whether `max_tokens` was unset anywhere in the C1/C2 path, since a reasoning model can exhaust its budget before emitting a tool call.
>
> **Acceptance:** I can read the raw request for at least one case and see the `tools` array present, and read the paired raw response and see whether `tool_calls` is null. Do not summarise instead of showing.

## CC-2 · Freeze the request-side evidence (Phase 0.2)

> **Goal:** our central P06 finding is "tools were supplied and the model returned no tool call." The *supplied* half is currently only our testimony. Fix that.
>
> **Guardrails:** read-only over C1/C2. Do not re-run the benchmark. If the archived C1/C2 logs already contain full request bodies, extract from them; only make a fresh call if they do not.
>
> **Task:** locate or capture **one** request/response pair from the exact C1/C2 configuration in which the request body visibly contains the `tools` array and the response visibly contains `tool_calls: null` (or the field's absence). Save both, redacted, under `docs/evidence/p06/toolcall_pair/`. Write a short `README.md` stating where they came from (archived log vs fresh capture), the model and provider strings, the date, and — if fresh — that it is a *reconstruction* of the configuration, not an artifact of the original run.
>
> **Acceptance:** a reader who does not trust us can see both halves of the arrow.

## CC-3 · Publish the freeze manifest (Phase 0.3) — no results

> **Goal:** make "C1 FROZEN / C2 FROZEN" checkable by a third party without publishing any unfinished result.
>
> **Guardrails:** do not commit raw C1/C2 outputs, per-task results, metrics, or any C2/C3 finding. Manifest and provenance only. Do not touch `main`.
>
> **Task:** create `docs/evidence/p06/` containing:
> - `MANIFEST.sha256` — SHA-256 of every frozen C1 and C2 artifact, with relative paths and byte sizes
> - `CONFIG.md` — model string, provider, endpoint, seed, K, task count, τ² version/commit, date and timezone of each run, and the exact command line
> - `PROVENANCE.md` — where the raw archive physically lives, who can retrieve it, and an explicit statement that `reports/*` is gitignored so the archive is external by design
> - `STATUS.md` — one table: `C1 = SEALED`, `C2 = SEALED`, `C3 = NOT STARTED`, `governance efficacy = NOT ESTABLISHED`, `native tool calls = 0/80`, `N_attempted_writes = 0`, `block recall / false-block rate / policy-violating-write rate = NOT ESTIMABLE (N=0)`, `latency = UNAVAILABLE`, `dollar cost = UNAVAILABLE`
>
> Use the word **SEALED** rather than FROZEN until it is on a pushed ref.
>
> **Acceptance:** every hash in `MANIFEST.sha256` recomputes against the local archive.

## CC-4 · Verify the bug table (Phase 0.5)

> **Goal:** no defect may be listed as FIXED unless a commit can be named.
>
> **Guardrails:** read-only. Do not fix anything in this session.
>
> **Task:** for each of — `ORDER_STATUS_SUPPORTS_ACTION` wiring; `tau2_retail` resolver vocabulary; M5 metamorphic defect; empty-LLM-completion handling; SOURCE-UNRELIABLE NULL handling; idempotency/duplicate execution; SQLite lifecycle; ESCALATE workflow gap — run `git log --all -S "<distinctive string>" --oneline` and `git log --all -G "<regex>" --oneline`, plus `git log --all -- <file>`.
>
> **Deliverable:** `docs/engineering/bug-register.md` with columns: issue · type · introducing commit · fixing commit · test that guards it · status ∈ {FIXED (commit named), FIXED (commit not identifiable), REPORTED — NOT ESTABLISHED}. Where the fix and its test land in the same squashed commit, say so and mark the detection-before-repair chronology **NOT ESTABLISHED**. Do not soften this.

## CC-5 · The four one-line defects (Phase 1.3)

> **Goal:** close two fail-opens and two reproducibility breaks. Small, surgical, each with a test.
>
> **Guardrails:** one commit per defect, each with its test in the same commit. Do not refactor anything else. Do not touch frozen artifacts.
>
> **Tasks:**
> 1. **`MODIFY` executes unmodified arguments.** `Decision.modified_args` is never assigned anywhere, and `intercept.py` does `impl(**(decision.modified_args or args))`. Under `manifests/knowledge_assistant.yaml`, `UNVERIFIABLE → allow_with_caveat → MODIFY`, so an unresolvable `send_document` sends the document unchanged. Fix by making `MODIFY` with no `modified_args` a hard error (or route it to ESCALATE) rather than silently executing. Add a test that fails on the current behaviour.
> 2. **Missing record crashes instead of escalating.** `intercept.py::_run_gate` calls the Zen graph before `decide()` with no `try/except`, and the graph raises on a null `delivered_at`. Guard predicate evaluation so a missing/unresolvable record degrades to `UNVERIFIABLE → ESCALATE`. Add a test using a nonexistent `order_id` through `dispatch_tool`.
> 3. **`scripts/gate_check.py` arity.** Line 42 unpacks 3 values from `agents.servicing_agent.propose()`, which returns 4. One-line fix. Then note in the evidence file that the transcript predates the current signature.
> 4. **`bench/report.py` hard-coded constants.** `MEASURED_GROUNDING_LOAD_MS`, `MEASURED_GROUNDING_CALL_MS`, `TYPICAL_PREDICATE_MS` contradict the README's "never from hand-typed numbers". Either log grounding latency into `decisions.jsonl` and read it, or delete the chart and remove the README claim. Do not keep both.
>
> **Acceptance:** each fix has a test that fails before it and passes after. Show me the failing output first.

## CC-6 · P11 public reconciliation (Phase 1.1) — the delicate one

> **Goal:** bring public `main` to a state whose claims match its evidence. Nothing more.
>
> **Guardrails — read all of these before starting:**
> - Work only in the `p11-readme-reconciliation` worktree. **Never** `git merge` the P06 worktree wholesale.
> - **Nothing** relating to P06 C2 or C3 results, governance efficacy, write-level metrics, or τ² outcomes goes to public `main`.
> - Do not publish "corrected" numbers unless the implementation that produced them **and** the result artifact are both on the branch being pushed. Preserve the distinction: *audit finding ≠ repair prepared ≠ repair present ≠ result generated*.
> - Do not force-push. Do not rewrite history. Show me the diff before pushing.
>
> **Task:**
> 1. Produce `git diff --stat` between public `main` (`42143cf`) and the branch, and classify every changed file as: **publish now** / **hold (unfinished P06)** / **hold (unverified claim)**. Show me this table before changing anything.
> 2. In `README.md`, remove or narrow: the Exp 3 `100% / 75%` result; the bias-probe framing; the mutation-score framing; the receipt-size claim. Replace each with the exact safe wording from my `19_claim_positioning_corrections.md`, not with a new number.
> 3. Add a short **"What we retracted and why"** section linking to `docs/experiment-audit.md`.
> 4. Narrow the "same engine, different manifest" wording: five of nine manifest keys are read by no code, and the knowledge-assistant graph is two identity aliases — say what is actually configured.
> 5. Run the full test suite; paste the real output.
>
> **Acceptance:** `grep -riE "\b(first|novel|unique|state of the art|production ready|externally validated|human validated|adversarially robust)\b"` over the published tree returns nothing that is not defensible against a named source. Show me the grep output.

## CC-7 · Verify label independence (Phase 2.1) — **GATE C**

> **Goal:** establish, from the current branch and not from any prior audit, whether the independent labeller and gold set exist, are committed, and actually produced the labels in use.
>
> **Guardrails:** read-only. Do not create the files if they are missing — report that they are missing.
>
> **Task:** for each of `bench/label.py`, `bench/gold_set.jsonl`, `bench/ground_truth_holdout.jsonl`, `tests/test_label_independence.py`, `tests/test_gold_set_holdout_isolation.py`: report present/absent, tracked/untracked, committed (with SHA), and the commit that introduced it. Then:
> - parse `bench/label.py`'s AST and confirm it imports **nothing** from `controlplane/`;
> - confirm no checker module opens the holdout file;
> - confirm the `gold_label` values in `gold_set.jsonl` were produced by `label.py` — re-run its labeller over the case list and diff against the committed labels;
> - re-check the two determinism hashes in `tests/test_gold_set_determinism.py`.
>
> **Deliverable:** `docs/gold-set-verification.md`, a table, and a single verdict: `LABEL INDEPENDENCE ESTABLISHED` or `NOT ESTABLISHED`.
>
> **Stop rule:** if the verdict is NOT ESTABLISHED, stop and tell me. Do not proceed to the A-ladder.

## CC-8 · Preregister the A-ladder (Phase 2.2)

> **Goal:** a dated, hash-stamped preregistration committed **before** the first run.
>
> **Task:** write `docs/prereg/A-ladder.md` containing: the question; the five arms A1 MessageOnly / A2 RetrievedOnly / A3 TraceOnly / A4 CachedRead / A5 LiveQuery with an exact definition of the evidence bundle each receives; the case source and its SHA-256; the label source and its SHA-256; the primary metric **with its explicit denominator**; the paired comparisons declared in advance (**A5−A4** = the LedgerAgent boundary, **A5−A3** = the AgentLTL boundary); the uncertainty method (**paired case-cluster bootstrap over `source_order_id`**, not more seeds, because the pipeline is deterministic); the pre-declared slice split, with `stale_policy_context` reported separately; and the abort conditions.
>
> State explicitly that `source_order_id` clustering makes the effective n far smaller than the case count (the ALLOW slice is ~50 cases on ~5 orders), and that no naive binomial interval will be reported.
>
> **Acceptance:** committed, dated, and referenced by SHA from the run script.

## CC-9 · Build and run the A-ladder (Phase 2.3–2.5)

> **Goal:** measure when independently re-querying the current system of record changes adjudication.
>
> **Guardrails — this is the experiment my audit says the project needs, and it is easy to rebuild the same tautology that invalidated Exp 3 and Exp 5. Therefore:**
> - the label must come from `bench/label.py`, never from `decide()`, never from any generator variable that also feeds an arm;
> - the arms must differ **only** in the evidence bundle. Same case, same `decide()`, same manifest, same clock;
> - the construction holdout must not be opened by any arm or by the scorer;
> - if you find yourself computing a gold label from a variable that also determines an arm's input, **stop and tell me** — that is the exact defect we are correcting.
>
> **Task:** in `bench/aladder/`, for each gold-set case construct five evidence bundles from one shared case record:
> - **A1** the agent's prose/justification only
> - **A2** the retrieved context only
> - **A3** the trace / prior tool returns only *(this is AgentLTL's `out(τ)`)*
> - **A4** a snapshot of the record as of retrieval time *(this is LedgerAgent's ledger)*
> - **A5** a fresh query at adjudication time
>
> Adjudicate each with the same `decide()`; score all five against `label.py`'s label.
>
> **Report:** per-arm accuracy with explicit numerator and denominator; the paired disagreement matrix; **A5−A4** and **A5−A3** with cluster-bootstrapped intervals over `source_order_id`; the `stale_policy_context` slice separately; and the count of cases where A5 and A4 *agree*, because that is the honest denominator for "how often does independence matter".
>
> **Also report the null explicitly:** if A5 ≈ A4 on most cases, say so. A small effect is a real result and is far more credible than a large one.
>
> **Acceptance:** off-diagonal entries exist in the paired matrix. A perfectly diagonal result means the arms are not independent — tell me rather than reporting it.

## CC-10 · Local structural tool-call proof (Phase 3, gated) — no provider

> **Goal:** before spending money on another benchmark run, prove the plumbing end to end with a synthetic model output.
>
> **Guardrails:** no provider calls. Do not modify frozen artifacts.
>
> **Task:** a test that injects a hand-written assistant message containing a well-formed native tool call for one τ² retail write tool, and asserts, with explicit assertions at each hop: the τ² parser accepts it → tool dispatch is reached → ControlPlane's interception point is entered → a decision is produced → a receipt is written. Assert on **observed side effects**, not on log strings.
>
> **Deliverable:** `tests/test_toolcall_path_structural.py` plus a short note recording which hop fails first, if any.
>
> **Stop rule:** if any hop fails, the integration is the problem and no benchmark run is justified until it passes. Report and stop.

## CC-11 · New track C1′ (Phase 3, gated)

> **Preconditions — refuse to run this prompt unless all three hold, and say which one failed:** (1) CC-1 showed the tool-call fault is configuration or adapter, not model/provider; (2) CC-10's structural proof passes; (3) a preregistration for C1′ is committed.
>
> **Guardrails:** the old C1/C2 are immutable. This is a **new track** with a new baseline. Never reuse old C1 as the baseline for a changed configuration. Freeze C1′ *before* C2′ runs.
>
> **Task:** create the C1′ configuration as a new, separately-named experiment; commit its preregistration; run it; write its hash manifest; mark it SEALED. Then, and only then, C2′.
>
> **Hard gate before C3′:** after C2′, verify and report `native tool calls > 0`, `ControlPlane invocations > 0`, `governed writes > 0`. If **any** is zero, stop and report the limitation. Do not run C3′. For C3′, inject the superseded clause into the **agent context only** — never modify the authoritative store.

## CC-12 · P10 related work (Phase 4.1)

> **Goal:** a related-work section that survives a reviewer who knows this literature.
>
> **Guardrails:** every claim needs a primary source with an exact section, definition or reported figure. Never write "first", "novel", "unique", or "no prior work". Never convert "we did not find" into "does not exist". Never put figures from different systems in one comparison table — different metrics, denominators, populations and protocols mean `NOT DIRECTLY COMPARABLE`, and say so in writing.
>
> **Identifiers to use — do not substitute:**
> `AEGIS = arXiv:2603.12621` (Yuan, Su, Zhao — "No Tool Call Left Unchecked"; **not** 2603.16938, which is a different paper with a colliding name) · `LedgerAgent = arXiv:2606.20529` · `AgentLTL = arXiv:2607.02599` · `C-Trace = arXiv:2606.19242` · `OAP = arXiv:2603.20953` · `Reason Less, Verify More = arXiv:2607.07405` · `Policies on Paths = arXiv:2603.16586` · `LEDGER = arXiv:2608.18398` · `Auditable Agents = arXiv:2604.05485` · `provenance survey = arXiv:2606.04990v4`
>
> **Structure:**
> 1. **Pre-execution enforcement** — AEGIS, OAP, AgentCore Policy, Reddy et al. Note AEGIS's Ed25519 + SHA-256 chaining and say plainly that our HMAC receipt is weaker.
> 2. **Trace-grounded verification** — AgentLTL (κ_ground ≡ ∀e ∈ ent(a), e ∈ out(τ)), C-Trace (forward/redact/block), LEDGER (post-hoc claim-to-evidence graphs).
> 3. **Maintained-state policy checking — LedgerAgent, its own paragraph.** State the overlap honestly: same stale-context motivation, pre-execution check, customer-service domains, pass^k. Then the one-clause distinction: its ledger is built from user interactions and tool returns; ours is a fresh query at adjudication.
> 4. **Where we sit** — cite the survey's six dimensions (2606.04990v4 §2.1) and that verification against an authoritative external system of record is not among its enumerated categories (§3.2). Then **stop**. Do not add a novelty sentence.
> 5. **Self-scoring** against Auditable Agents' five dimensions (2604.05485 §2): action recoverability, lifecycle coverage, policy checkability, responsibility attribution, evidence integrity. Score honestly, including where we fail.
>
> **Acceptance:** every paragraph cites a section, definition or figure. No comparison table of cross-system numbers exists in the file.

## CC-13 · Threat model (Phase 4.3)

> **Goal:** a threat model we can defend, not a security claim we cannot.
>
> **Task:** `docs/threat-model.md`, one row per threat: threat · attacker capability · our defence · evidence (file/test) · TESTED or UNTESTED · remaining gap. Cover at minimum: malicious agent tool calls, evidence degradation, stale evidence, misleading tool output, corrupted authoritative record, replay, receipt tampering, identity ambiguity, policy ambiguity, fail-open, retry/idempotency abuse, resolver unavailable, source unavailable, malformed arguments, verifier-as-attack-surface, fixture poisoning.
>
> **Required honesty:** mark `fail_posture` as declared-but-unread; mark the idempotency key as computed-but-never-checked; mark receipt integrity as HMAC-with-shared-secret, no chaining, telemetry unsigned — and note that AEGIS (2603.12621) publishes hash-chained Ed25519 receipts, so this is our design choice, not a limit of the state of the art. Frame M5 as an **implementation soundness/integrity defect with adversarial relevance**, never as a demonstrated security result, and note that `reliability_class` is set from a source-metadata table and is not agent-reachable, so no exploit path was demonstrated.
>
> **Acceptance:** the UNTESTED column is populated honestly and is longer than the TESTED column.

---

## Run order and gates

```
CC-1  probe            ── GATE A ──▶ decides whether Phase 3 exists at all
CC-2  request evidence
CC-3  freeze manifest
CC-4  bug table
   │
CC-5  four fixes
CC-6  P11 reconciliation ── GATE B: nothing unfinished reaches public main
   │
CC-7  label independence ── GATE C: stop here if NOT ESTABLISHED
CC-8  preregister
CC-9  A-ladder  ◀── the experiment your thesis actually needs
   │
CC-12 related work
CC-13 threat model
   │
CC-10 structural proof ──▶ CC-11 new track   (only if GATE A allowed it)
```

**If you run only three: CC-1, CC-5, CC-6.** The first tells you what the project is; the second closes two fail-opens; the third is what you are graded on.
