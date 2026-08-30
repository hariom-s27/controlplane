# Onboarding-time measurement — service credit approval (use case 4)

A single, mechanically-timed measurement of onboarding one genuinely new
governed use case onto the final, hardened (P02) manifest-driven
ControlPlane architecture. One measurement of one use case — see
Limitations below before generalizing from it.

## Measurement setup

**Locked use case:** `service_credit_approval` — a customer files a service
complaint (late delivery, damaged packaging) **not** tied to returning the
item; the agent proposes a goodwill service credit against the order.

**Governed tool:** `approve_service_credit(order_id, amount_paise, currency)`.

**Policy rule:** an agent may approve a service credit up to their authority
ceiling (INR 3,000 / 300,000 paise), provided the order belongs to the
requesting customer and the credit does not exceed the order's own total.
Unlike every prior manifest, there is **no delivery-window check** — a
service complaint isn't gated by how long ago the order arrived.

**Required evidence (all via existing resolvers):** `ORDER_BELONGS_TO_CUSTOMER`
and `AMOUNT_NOT_EXCEEDING_ORDER` (resolver `orders`), `AMOUNT_WITHIN_AUTHORITY`
(resolver `authority`).

**Why non-trivial:** a real governed monetary action (credit issuance)
requiring ownership + amount-sanity + authority checks, in a combination no
existing manifest exercises — `servicing` and `discount_approval` both gate
on a delivery window; `knowledge_assistant` has no amount/authority checks
at all. This manifest has authority+ownership with **no window**.

**Independence verification (before LOCK):** repo-wide grep for
`service_credit`, `approve_service`, `goodwill_credit`, `compensation_credit`
across `*.py`/`*.yaml`/`*.json`/`*.md` — zero matches. Not `servicing` /
`knowledge_assistant` / `discount_approval`, not a renamed tool, not a
cosmetic threshold variant (it has no window at all, so it isn't a
window-days tweak of an existing manifest).

**P02_FROZEN_HEAD:** `8a48bf7ac4a20d8d57c9fc86ac47de6eb784971e` — the P02
hardening itself is uncommitted, so HEAD alone does not uniquely identify it;
the exact frozen state is additionally pinned by SHA-256 over every
P02-relevant file, recorded immediately before START:

```
controlplane/manifest.py            a5bea5a29029822a111c02b04c5ec7ced54060f2196cc163ba895fd04da991e7
schemas/manifest.schema.json        5970fc465f7bc8b4ae83505bf8ad96cd9d87c277330537b359a3817c3390ec75
manifests/servicing.yaml            c8e0860e2115a52fc406b2e110976d39a58618ec02c414a64145c1ab21961432
manifests/knowledge_assistant.yaml  9da07581ccc58ef930b7cd67aa098c1d359a9fd7f7001a3adcc40dbdce2ede43
manifests/discount_approval.yaml    9a1ab7d958aa855db4be90ab2f29cbc69668fca85f106f93be44eb3c0db733dd
docs/architecture.md                673ceb08377015d28745ef3ca4390be86934bcc07264dca890a3c1910fb4fba7
docs/policy-manifest.md             714aec54b5b5a43aeba12bd4f3e6bb9360431f2057308fedc8ff75d9ceabda50
tests/test_manifest_hardening.py    fb9dd57a2ccfdff03e0e199cead74e6f80a356ead3c60184b89b7c68c6479544
requirements.txt                    574c604112c6d9e2e3a223d7d4f18b69bd93fb77a0fd91f49c228769cf5a4c9b
controlplane/bindings.py            d6616505ad84a1ad425c61bcda660c64fce8b073248cf6904b40ea2ea8cda0fa
controlplane/intercept.py           0095cbd8c0490e343b32c50a3ea04c137992d271615a25a948386397dbb91c74
```

Branch: `p03-m4-blind-human-label-sheet`. Python: 3.14.3
(`/d/sem_iitk/sem9/comp/accenture/.venv/Scripts/python`). Model: Claude
Sonnet 5 (`claude-sonnet-5`), this session's configured reasoning effort.
No P02 file was touched during the measurement (verified: `git status` for
`controlplane/manifest.py` after END shows the identical `MM` state it had
before START — no new diff).

## Frozen acceptance test set (pre-registered before START, unchanged after)

1. `python -m pytest tests/test_service_credit_approval.py -v` — functional/use-case tests
2. `python -m pytest tests/test_engine_is_use_case_agnostic.py -v` — engine/use-case isolation
3. `sha256sum -c <frozen 9-file protected-hash list>` — protected-artifact hash verification
4. `git diff --check`

## Timing

- **START: 2026-08-30T15:33:51.080Z** — first use-case-specific action: `Write manifests/service_credit_approval.yaml`
- **END: 2026-08-30T15:35:30.599Z** — immediately after acceptance command 4 (`git diff --check`, exit 0) completed, following commands 1-3 all passing
- **Elapsed: 99.519 seconds (1 minute 39.519 seconds)**, computed directly from the two UTC timestamps above — not estimated
- **Final acceptance command:** `git diff --check` (exit code 0, only pre-existing CRLF-on-checkout warnings)

No retries, no failed test, no debugging cycle occurred in this run — all four acceptance commands passed on their first execution. This is recorded honestly, not smoothed: the interval reflects one implementer (this agent) building from a fully-internalized architecture (having just completed the P02 hardening audit in the same session) against real, pre-existing seed data, with no schema-drift or resolver gap encountered.

## Scope

| | Lines |
|---|---:|
| Manifest YAML (`manifests/service_credit_approval.yaml`) | 56 |
| Predicate graph (`manifests/graphs/service_credit_approval.json`) | 24 |
| Tool schema (`APPROVE_SERVICE_CREDIT_TOOL` literal, inside the agent file) | 18 |
| **New use-case-specific `controlplane/` Python** | **0** |
| New resolver Python | 0 |
| Agent/demo-wrapper file (`agents/service_credit_agent.py`, full file incl. the 18-line tool schema above) | 153 |
| Test file (`tests/test_service_credit_approval.py`) | 118 |

Files changed, exhaustive (`git status --short`, exactly 4 new untracked files, nothing else touched):
```
?? agents/service_credit_agent.py
?? manifests/graphs/service_credit_approval.json
?? manifests/service_credit_approval.yaml
?? tests/test_service_credit_approval.py
```

## Reuse

- **Resolvers reused:** `orders`, `authority` — zero new resolvers
- **Claim kinds reused:** `ORDER_BELONGS_TO_CUSTOMER`, `AMOUNT_NOT_EXCEEDING_ORDER`, `AMOUNT_WITHIN_AUTHORITY` — zero new claim kinds
- **Graph machinery reused:** the same Zen JDM `inputNode → expressionNode → outputNode` shape as `servicing.json`/`discount_approval.json`; only the `expressions` array is new (3 lines of Zen expression syntax)
- **Validation/lint reused:** `controlplane/manifest.py::load_manifest` / `_validate` / `_validate_structural` (P02 JSON Schema) / `lint()` — all unchanged, all exercised against the new manifest with no code change
- **Shared engine reused:** `intercept._run_gate` → `extract.build_claims` → `ladder.classify_claims` → `registry.resolve_bindings` → `bindings.build_predicate_payload` → `predicates.evaluate` → `decide.decide` → `receipt.record` — the entire pipeline, unmodified
- **Tests/utilities reused:** the `test_third_use_case.py` structural pattern (fixture shape, `_dispatch` helper) was followed for the new test file; `test_engine_is_use_case_agnostic.py` itself needed no change to cover the new manifest (it discovers forbidden tokens from `manifests/*.yaml` automatically)

## Result

All 13 acceptance criteria from the task's Section 9 were met:

1. tool/schema valid — `APPROVE_SERVICE_CREDIT_TOOL` present, well-formed
2. manifest loads — `load_manifest("service_credit_approval")` succeeds
3. manifest validation passes — semantic (`_validate`) + structural (JSON Schema) both pass
4. manifest lint/explain passes — `cm.lint(...)["ready"] is True`, `tool_contract` starts `"OK —"`, no dead bindings
5. governed tool correctly connected — `dispatch_tool("approve_service_credit", ...)` reaches `_run_gate`
6. evidence resolution works — both resolvers return real `data/orders.db` / manifest-backed evidence
7. valid/ALLOW case succeeds — `ORD-10200`/`CUST-1407`, credit 50,000 paise → `{"status": "approved", ...}`
8. invalid/BLOCK case — `ORD-10298`/`CUST-1629`, credit 500,000 paise → `Blocked`, reason `within_authority` (a second BLOCK case, wrong customer, was also exercised)
9. end-to-end path uses the shared engine — same `_run_gate` code path as every other manifest, no branch
10. new-use-case tests pass — 6/6 in `tests/test_service_credit_approval.py`
11. engine/use-case isolation passes — 27/27 in `tests/test_engine_is_use_case_agnostic.py`
12. protected artifacts unchanged — 9/9 SHA-256 matches, before and after
13. no accidental use-case-specific `controlplane/` code — confirmed 0 lines changed under `controlplane/` in this task

**Outcome: all frozen acceptance criteria passed on the first run.**

## Limitations

This is **one** mechanically-timed measurement of **one** use case, performed
by one AI agent immediately after building the P02 hardening being measured
against — with full, fresh context of the architecture. It does **not**
establish:

- a general onboarding-time distribution (no variance, no confidence interval, n=1)
- a universal onboarding guarantee for any future use case
- a causal claim that P02 hardening specifically *caused* this speed (no
  pre-hardening onboarding time was measured for comparison in this task)
- that every future use case will cost 0 new `controlplane/` Python — this
  one happened to need only claim kinds and resolvers that already existed;
  a use case needing a genuinely new evidence source (a new external system,
  a new claim shape) would need a new resolver, which is explicitly outside
  the "0 lines" claim and would be reported separately if it occurred
- human onboarding time — this measurement is of an AI agent's tool-call
  wall-clock time, not a human engineer's, and the two are not
  interchangeable
