# The policy manifest (S12)

A manifest is the **whole** per-use-case configuration. The engine —
everything under `controlplane/` — is use-case agnostic; adding a use case
is a new file in `manifests/` and nothing else. `tests/test_engine_is_use_case_agnostic.py`
fails if any string under `controlplane/` names a use case.

`manifests/*.yaml` is loaded and validated by `controlplane/manifest.py`.
An unknown resolver, an unknown claim kind, a malformed reference, a
reference to a `claimed_*` field, or a missing predicate graph fails
**loudly at load**, naming the binding and the reason.

---

## Fields

| Field | Type | Meaning |
|---|---|---|
| `manifest_id` | str | id stamped on every receipt |
| `tool` | str | the one tool this manifest governs. A call to any other tool is rejected in `intercept._run_gate`. |
| `predicate_graph` | str | Zen JDM graph, path relative to `manifests/` (e.g. `graphs/servicing.json`) |
| `compensation` | map | `{action: <compensating action or null>, compensability: fully\|partially\|not}` — D49. `not` forces BLOCK on any non-VERIFIED verdict. |
| `policy_id` | str | the policy this use case's clause claims are about (referenced by bindings as `manifest.policy_id`) |
| `window_days` | int / null | inclusive day window for a `WITHIN_REFUND_WINDOW` claim |
| `authority_ceiling_paise` | int | ceiling for an `AMOUNT_WITHIN_AUTHORITY` claim |
| `reliability_floor` | str | evidence below this → SOURCE_UNRELIABLE (D36) |
| `verdict_handling` | map | per-verdict intervention: `escalate` or `allow_with_caveat` |
| `fail_posture` | map | `{tier_0, tier_1, tier_2}` → `open`/`closed` when the escalation budget is exhausted |
| `risk_tier_default`, `latency_budget_ms`, `escalation_budget_pct`, `evidence_retention_days` | | policy metadata; `risk_tier_default` selects the exhausted-budget fail posture and `escalation_budget_pct` is enforced statefully at `dispatch_tool` |
| `predicate_payload` | map | static scaffolding the graph reads that is not backed by a claim: `{<dotted path>: <reference>}` |
| `claim_bindings` | list | **the evidence bindings** — see below |

## `claim_bindings`

One entry per claim this use case checks, **in receipt order**.

```yaml
claim_bindings:
  - claim_kind: WITHIN_REFUND_WINDOW      # a ClaimKind enum member
    resolver: orders                       # a name in registry.RESOLVER_BY_NAME
    subject: action.order_id               # reference for claim.subject
    predicate_key: delivered_at            # where the resolved value lands
```

| Key | Meaning |
|---|---|
| `claim_kind` | a `ClaimKind` (engine vocabulary — `controlplane/schema.py`). Unknown → load error. |
| `resolver` | `orders` \| `policy` \| `entitlements` \| `authority` \| `pii` \| `intent`. Unknown → load error. |
| `subject` | reference for `claim.subject`: `action.<structural field>`, `manifest.<key>`, `session.<attr>`. `action.claimed_*` → **load error**. |
| `predicate_key` | where this evidence's value goes in the payload the graph reads as `evidence.*`: <br>• a dotted string — `payload[path] = value` <br>• a `{sub: path}` map — `payload[path] = value[sub]` (for a dict-valued evidence, e.g. `ORDER_ATTRIBUTES_MATCH`) <br>• `null` — not fed to the graph; handled by `decide()` (clause version), grounding (`CLAUSE_SEMANTICS_MATCH`), or `pii` (`EXCERPT_CONTAINS_THIRD_PARTY_PII`) |

### Adjusted from the roadmap's sketch, and why

The roadmap's target shape had `query:` and `params:` per binding. This
schema drops both:

- **No raw `query`.** Resolvers are typed adapters (`controlplane/registry/*.py`)
  with fixed, parameterised queries — one per `ClaimKind` they answer. Raw
  SQL in a manifest is an injection surface and would duplicate what the
  resolver already encodes. The binding names the *resolver*; the resolver
  owns the SQL.
- **No `params` beyond `subject`.** The only value a binding needs to pass
  into resolution is the entity the claim is about (`claim.subject`), which
  is the single `subject:` reference. Everything else the resolver derives
  from `subject` + `session` + `manifest`.

Also kept out of the binding on purpose:

- **`tier`** — the Checkability Ladder (`controlplane/ladder.py`) owns tier,
  keyed by `ClaimKind`. A per-manifest override would let two manifests
  disagree about whether a SQL read is C1, which is exactly the kind of
  silent policy drift the ladder exists to prevent.
- **`reliability_class`** — the resolver knows this. `orders.py` reads the
  DB's own `field_reliability` table (D36); a manifest cannot know a field
  went stale.

## References

`action.<field>` reads `ProposedAction.facts_for_predicate()` only — the
structural tool-call fields. It can never read a `claimed_*` value; the
validator rejects that at load time, because **the extractor produces
CLAIMS and the registry produces FACTS, and they never come from the same
place.** `session.<attr>` reads `SessionContext`. `manifest.<key>` reads the
manifest. `clock.today` is the frozen demo clock.

## Worked example — the three shipped manifests

| | servicing | knowledge_assistant | discount_approval |
|---|---|---|---|
| `tool` | `issue_refund` | `send_document` | `approve_discount` |
| `window_days` | 7 | — | 14 |
| `authority_ceiling_paise` | 2,500,000 | 0 | 500,000 |
| `compensability` | fully | partially | partially |
| `reliability_floor` | corroborated | unverified | corroborated |
| `UNVERIFIABLE` handling | escalate | allow_with_caveat | escalate |
| bindings | 7 (order + policy + attrs) | 3 (entitlement + pii) | 3 (order + authority) |
| predicate graph | `graphs/servicing.json` | `graphs/knowledge_assistant.json` | `graphs/discount_approval.json` |
| new `controlplane/` code | — | — | **0 lines** |

## P02 hardening: schema, lint, cross-contract checks

Use-case behavior is declared in a validated manifest. Resolver
implementations remain shared code components; manifests select and bind them
without introducing use-case-specific engine code.

**`schema_version: 1`** is required on every manifest. `load_manifest`
rejects a missing or unsupported version before any other check runs
(`controlplane/manifest.py::SUPPORTED_SCHEMA_VERSIONS`).

**`schemas/manifest.schema.json`** is a JSON Schema validating the
*structural* contract only — field types, the closed `claim_kind`/`resolver`
vocabulary, dotted-reference shape, and (via `additionalProperties: false` on
each `claim_bindings` item) that a binding can carry only `claim_kind` /
`resolver` / `subject` / `predicate_key` — no `query`, no `exec`, no field
that could carry raw SQL or a Python expression. It is checked automatically
inside `_validate` (`controlplane/manifest.py::_validate_structural`) on
every `load_manifest` call. It never replaces the semantic checks already in
`_validate` — an unknown `resolver`/`claim_kind` is now caught structurally by
the schema *and* would still be caught by `_validate`'s own lookup against
`RESOLVER_BY_NAME` / `ClaimKind` if the schema's enum ever drifted;
`tests/test_manifest_hardening.py::test_schema_enums_do_not_drift_from_the_live_engine_vocabulary`
pins the two together. A `claimed_*` reference passes the schema (it's a
structurally valid dotted path) and is still rejected by
`controlplane/bindings.py::validate_ref` — the schema was never meant to know
that rule.

**`python -m controlplane.manifest lint <name-or-path>`** is a read-only
report (`controlplane/manifest.py::lint`): manifest id, schema version,
governed tool, every claim's resolver, the predicate graph, the policy
config fields, a static tool-contract check, and a dead-binding scan, ending
`RESULT: READY` or `INVALID — <reason>`. It never imports
`controlplane.intercept`, so it cannot call `dispatch_tool` or any registered
tool implementation even by accident.

**The tool contract** (`_tool_contract_check`) is a static, AST-only check —
`agents/*.py`'s tool definitions are read with `ast.literal_eval`, never
imported or executed — that each `claim_bindings[].subject` naming
`action.<field>` is actually a parameter of the manifest's governed tool. This
catches a real gap `bindings.validate_ref` cannot see on its own: `action.*`
there is checked against the *engine's* global structural-field set (shared
across every use case), not against any one tool's own schema, so e.g.
`action.doc_id` would pass `validate_ref` under `discount_approval.yaml` even
though `approve_discount` has no `doc_id` parameter. When no tool schema
literal is found under `agents/`, the report says exactly
`"not statically checkable"` rather than asserting pass or fail.

**The dead-binding scan** (`_dead_binding_report`) is a textual check: for
each binding with a non-null `predicate_key`, does `evidence.<path>` appear
in the referenced graph's JSON text? A miss is reported as
`"not statically checkable beyond this substring scan"`, never as proof the
binding is unused — the graph could reference the path a way this scan
cannot see.
