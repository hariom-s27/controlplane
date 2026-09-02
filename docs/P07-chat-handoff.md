# P07 chat handoff and GitHub audit

Generated from the project conversation on 2026-08-31. This is a repository-facing handoff, not a dump of hidden system instructions or credentials. The open `.env` was deliberately not read or copied.

## Why this file exists

The request was to preserve the whole actionable conversation in Markdown so the team can see what belongs in GitHub, what is already present, and what still needs attention. The original engineering request was **TASK P07 — Seven small fixes that are currently costing us credibility**, priority P0.

## Original requested work

1. **LLM completion budget:** add an explicit `max_tokens` in `agents/llm.py`, reject empty completions, and test that zero-length output is an error rather than a result.
2. **Negative control:** rerun the five gate-off checks after Fix 1 and store the complete result and run count in `docs/evidence/negative_control.txt`.
3. **Receipt size:** measure median and p95 serialized receipt size over at least 100 receipts, update `reports/summary.json`, find old figures in repository/deck text, and disclose redundant fields instead of silently trimming them.
4. **ESCALATE consumer:** hold escalated actions, return `pending`, persist a queue, provide `make review` with blind APPROVE/BLOCK review followed by verdict reveal/agreement recording, and apply the manifest escalation budget and tier fail posture. Test exhausted-budget behavior.
5. **Latency claim:** find every occurrence of “75% of traffic finishes in 1–20 ms,” label it a design target until measurement exists, and then replace it with measured p50/p95/p99.
6. **Zen Engine positioning:** add the specified business-logic/security-perimeter sentence to `README.md` and `docs/architecture.md`.
7. **Deming sentence:** remove bare or incorrect “Deming, 1986”/kp-rule framing and use the OC-curve reformulation from the runbook exactly. Stop rather than inventing a paraphrase if the runbook text is absent.

Required output: a short report for every fix—what was found, what changed, and what test covers it—plus every file in which an incorrect number was found.

## Current repository audit

### Fix 1 — explicit completion budget and empty-response rejection

**Status: present and focused tests pass.**

- `agents/llm.py` defines `MAX_TOKENS`, defaulting to `24576` and configurable through `CP_MAX_TOKENS`.
- Every chat payload includes `max_tokens`.
- `_validated_completion()` rejects missing choices, blank content without a valid tool call, malformed tool calls, and invalid tool-call arguments.
- Validation applies to cached fixtures and live provider responses, so an old empty fixture cannot masquerade as a result.
- Coverage: `tests/test_llm_key_fallback.py`, including cached empty/unusable completions, empty choices, malformed calls, live payload budget, and live empty-response rejection.

### Fix 2 — real negative-control result

**Status: recorded as 5/5.**

- Evidence: `docs/evidence/negative_control.txt`.
- Recorded date: 2026-08-30.
- Model: `Qwen/Qwen3-8B`.
- Run count: 5.
- Result: **5/5 proposed a refund unprompted** with no empty completion counted.
- The evidence also discloses that smaller 4096- and 16384-token live attempts produced unusable empty completions and correctly raised errors; the recorded 24576-token run completed all five calls.

This audit did not rerun the paid/live model call. It preserves and reports the checked-in transcript.

### Fix 3 — receipt size

**Status: measured and reported.**

- `reports/summary.json` records **n=120**, **median=2,282 bytes**, **p95=3,763 bytes**, min 2,183 bytes, max 3,764 bytes.
- The measurement method rotates all three manifests through real resolver/predicate/decision execution while bypassing only LLM extraction with structural tool calls.
- Raw measurement receipts were not persisted; this limitation is explicitly disclosed.
- Redundant candidates were listed instead of silently removed:
  - `action.args` values repeated by `claims[].asserted`;
  - predicate outcomes repeated in reasons and `predicate_trace`;
  - `manifest_id` repeated by `reasons[].policy_version`;
  - identical evidence source/query metadata repeated per claim.
- Current figures are also reflected in `README.md`, `docs/architecture.md`, `docs/decision-receipt.md`, and `docs/ROADMAP.md`.
- Coverage: `tests/test_receipt.py` plus the reproducible report path in `bench/report.py`.

### Fix 4 — ESCALATE lifecycle

**Status: implemented and focused tests pass.**

- `controlplane/intercept.py` holds ESCALATE actions and returns a pending state.
- `controlplane/escalation.py` persists pending work to `pending_actions.jsonl` and records budget exhaustion.
- `bench/reviewer_console.py` implements blind review: it hides the verdict, accepts APPROVE/BLOCK, then reveals the verdict and records agreement.
- `Makefile` exposes `make review`.
- Manifest `escalation_budget_pct` is enforced; exhausted budgets use the active risk tier’s configured open/closed fail posture.
- Coverage: `tests/test_escalation.py`, including open and closed exhausted-budget paths, queue behavior, blind output, reviewer decisions, and an integrated escalation/review/exhaustion flow.

### Fix 5 — modelled latency claim

**Status: old claim retired; P09 measurement is available.**

- The old “75% of traffic finishes in 1–20 ms” wording remains only in explicit historical/retired contexts and in a regression test that prohibits presenting it as a current fact.
- `reports/latency.md` reports P09 measurements across four configurations with 1,050 gated calls per configuration.
- Comparable headline (C1, HHEM off, sequential): **p50 7.67 ms, p95 12.65 ms, p99 14.52 ms, max 26.47 ms**.
- HHEM-on and concurrency-10 results are kept separate rather than blended into the headline.
- Coverage: `tests/test_latency.py` rejects any unlabelled reintroduction of the old claim.

### Fix 6 — Zen Engine positioning

**Status: exact requested sentence present.**

The following text appears in both `README.md` and `docs/architecture.md`:

> Zen Engine expresses business decision logic — the window is 7 days and this order is at 26. It is not the security perimeter; authorization is upstream and is not our contribution.

This narrows the contribution honestly: Zen represents business rules, while authorization remains upstream.

### Fix 7 — Deming/OC-curve reformulation

**Status: runbook wording exists and is regression-tested.**

- Authoritative reformulation: `docs/round2-runbook-block0.md` under “Safe reformulation, which survives either reading.”
- The text correctly states the statistical-control/i.i.d. premise and explains the superseded-policy document as an assignable cause.
- `tests/test_deming_reformulation.py` scans shippable documentation for prohibited bare attribution and inverted framing, and verifies the approved reformulation remains present.

## Focused verification performed for this handoff

Command:

```text
.venv\Scripts\python.exe -m pytest tests\test_llm_key_fallback.py tests\test_escalation.py tests\test_receipt.py tests\test_deming_reformulation.py -q -p no:cacheprovider
```

Result on 2026-08-31: **52 tests passed**.

The live negative-control run was not repeated during this documentation-only request; its checked-in evidence was inspected. The full test suite was also not run for this handoff.

## Wrong or retired number locations

The present tree no longer states the old values as current facts. These files retain them only to document retirement or enforce regression protection:

- `docs/ROADMAP.md` — records the now-retired old “75% in 1–20 ms” claim, then points to P09 measurements.
- `tests/test_latency.py` — contains the old wording solely as a forbidden-pattern regression test.
- `README.md` — mentions the approximately 2 KB receipt **target**, clearly contrasted with the measured larger result; it is not presented as the measured size.
- `docs/ROADMAP.md` — mentions Proof of Execution’s approximately 1.1 KB object as external prior art, explicitly separated from this project’s 2,282/3,763-byte measurement.

No submitted slide/deck binary was identified in this focused audit. If the actual submitted deck lives outside this repository or only as a binary, it still needs a separate visual/text inspection before publication.

## GitHub packaging notes

- Add this file as the human-readable P07 handoff.
- Include the implementation, tests, evidence transcript, and report changes associated with P07 in the eventual commit/PR.
- Do **not** add `.env`, API keys, provider credentials, `pending_actions.jsonl`, or other runtime/private records.
- The working tree currently contains unrelated modified and untracked P06/tau2 work. Do not stage everything wholesale; select P07 files deliberately so unrelated work is not mixed into the P07 commit.
- Before merging, run the full suite and review the final diff for generated artifacts and secrets.

## Conversation note

The user’s latest instruction was to put the whole actionable chat into a Markdown file so the team can assess what should go to GitHub and understand what has been completed. This document fulfills that request as an audit-friendly summary while omitting secrets and internal platform instructions.
