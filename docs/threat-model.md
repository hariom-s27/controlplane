# Threat model

## Scope and security objective

This threat model describes the verified local release candidate whose C/I/D engineering code was reconciled at `986b65e522091cc2d5d2f4ccf571688a095c3529` and whose execution-recipient entitlement binding was corrected at `dce2e4cc4c0cc1eaae2bc58fc02f5ea7971b65c6`. The public baseline remains `6ec4261d374904f55bf5dff1a9855854f1b94819`; the release candidate and this document are not public-main facts until separately integrated and pushed. Off-release P03/P04/P05/P08/P09 material is not used as current defense evidence, and P06 and tau2 are not used.

The objective is narrow: for the registered, gate-enabled paths, check selected proposed tool-call facts against configured evidence before execution; preserve uncertainty instead of silently treating it as a passing predicate; apply the resulting intervention; and record the decision. The objective does not include authenticating the caller, isolating the Python process, proving the record sources correct, mediating arbitrary calls to tool implementations, or certifying deployment security.

The implementation and focused tests are the source of truth. Step 6 did not run tests, experiments, fuzzing, red-team campaigns, providers, or benchmarks. `docs/architecture.md` is not present in this tree, so the boundary below is reconstructed from source, tests, README, the receipt documentation, and the related-work document.

## Assets

- Integrity of proposed tool-call decisions and the arguments that actually execute.
- Business records, current policy state, customer data, document contents, and entitlement data.
- Predicate inputs, resolved evidence, verdicts, interventions, and compensability posture.
- Availability of the gate, registry sources, predicate engine, and governed dispatch path.
- Process-local idempotency state and prior completed results.
- Decision receipts, their HMAC key, and adjacent telemetry.

## Trust boundaries

The implemented path is:

```text
agent / caller
  -> tool arguments, justification, retrieved context, SessionContext
  -> extraction into ProposedAction and Claim objects
  -> ProposedAction.facts_for_predicate()
  -> registry resolution from configured stores
  -> manifest-selected predicate graph
  -> decide()
  -> dispatch_tool()
  -> registered implementation
  -> decision receipt and telemetry file
```

The code, manifests, predicate graphs, resolver mappings, decision function, and registered implementation are trusted to be the reviewed candidate. That is an assumption, not protection against a compromised process or operator. Registry data, source metadata, session identity, and the HMAC secret are partially trusted: the implementation consumes them but does not establish their correctness, provenance, or custody. Agent prose, retrieved context, tool arguments, and caller-constructed session fields are untrusted. `dispatch_tool()` is the central interception point for the included governed call paths, but it is not a privilege boundary: `SessionContext.gate_enabled` can disable the gate and in-process code can call an implementation directly.

`facts_for_predicate()` excludes prose-derived `claimed_*` fields. It does not make structural tool arguments trustworthy; those remain agent-controlled inputs that must be checked by specific predicates. A decision-time query establishes recency of that query, not truth or source independence. In the orders path, agent retrieval and resolver evidence can depend on the same underlying store. The policy path is more strongly separated because it selects the currently effective row independently of the version asserted by the agent.

## Threat actors / failure sources

- A mistaken or hostile agent that chooses claims, tool arguments, or retrieved context.
- A caller or integrator that controls session fields, disables the gate, selects a manifest, or bypasses `dispatch_tool()`.
- An incorrect, unavailable, ambiguous, stale, or malformed record source.
- A configuration or policy author who chooses an open outage posture or leaves a control declarative but unenforced.
- A process failure during execution, retry, or restart.
- A log writer, operator, or HMAC-key holder who can alter, delete, replay, or forge audit material.
- Provider, extraction, parsing, dependency, and unexpected-structure failures.

The model does not assume protection after host, source database, manifest, code, or operator compromise. Those conditions are external constraints unless a specific defense below says otherwise.

## Attack surfaces

| Surface | Trust classification | Implemented boundary | Important residual risk |
|---|---|---|---|
| Agent-generated content | UNTRUSTED | Extracted into nullable `claimed_*` fields | Extraction accuracy and intent correspondence are not adversarially tested |
| Tool arguments | UNTRUSTED | Typed `ProposedAction`; selected fields checked by predicates | No complete tool-schema or semantic validation; caller identity and authority to choose a recipient remain external |
| Retrieval and context | UNTRUSTED | Not admitted as predicate facts | Can still influence the proposed action and extracted claims |
| Record-source layer | PARTIALLY TRUSTED | Resolvers issue scoped SQLite queries and attach reliability/confidence | A successful read can still return wrong data; some paths share the agent's store |
| Policy store | PARTIALLY TRUSTED | Current-row query; multiple current rows rejected | Operator correctness and policy semantics are assumed |
| Predicate engine | TRUSTED | Receives resolver evidence plus `facts_for_predicate()` | Graph/configuration defects remain possible; no formal proof |
| Decision engine | TRUSTED | Pure deterministic verdict/intervention function | Correctness is regression-tested, not proven for every input |
| Interception layer | PARTIALLY TRUSTED | Central dispatch for registered governed paths | Caller-controlled gate-off path and direct in-process calls remain |
| Idempotency state | PARTIALLY TRUSTED | Locked in-memory ledger | Lost on restart and not shared across processes |
| Receipt and telemetry | PARTIALLY TRUSTED | HMAC over canonical receipt fields | No chain, deletion/replay protection, or signature over telemetry |
| Deployment/integration | OUT OF SCOPE | No isolation or authenticated ingress is implemented | Security depends on callers routing every action through the gate |

## Threat matrix

The status is the primary classification for the exact scope stated in each row. `MITIGATED` means an implementation behavior with direct regression evidence; it does not mean elimination of the broader threat.

| Threat | Category | Asset | Attack/failure condition | Current defense | Evidence | Status | Residual risk |
|---|---|---|---|---|---|---|---|
| T1 Incorrect factual claim | SECURITY | Decision integrity | Agent prose asserts a false fact | `claimed_*` is excluded from predicate facts; selected assertions are compared with resolved evidence | `schema.py::facts_for_predicate`; `test_no_claimed_field_reaches_the_engine`; policy-resolver tests | PARTIALLY MITIGATED | Unmodelled claims and unchecked semantics remain |
| T2 Manipulated tool arguments | SECURITY | Executed arguments | Agent chooses a wrong ID, amount, attributes, currency, or payload | Entity, amount, window, attribute, classification, and entitlement predicates cover selected fields | Predicate graphs; `test_predicate_table`; knowledge-assistant tests | PARTIALLY MITIGATED | No complete schema/semantic validation; currency, sign, payload meaning, caller identity, and delegation authority have gaps |
| T3 Stale retrieved context | SECURITY | Policy/action correctness | Retrieval contains a superseded policy or record | Resolver evidence, not retrieved prose, drives predicates; current policy row is queried | `registry/policy.py`; `test_policy_resolver_returns_v42_even_when_agent_retrieved_v38` | PARTIALLY MITIGATED | Stale context can still shape which action is proposed; coverage is limited to modelled checks |
| T4 Stale trace/context evidence | SECURITY | Predicate inputs | Prior tool output or context is treated as current evidence | Predicate facts come from structural arguments and resolver evidence, not a prior trace witness | `predicates.evaluate`; `facts_for_predicate`; claim-separation test | PARTIALLY MITIGATED | There is no general trace-verification or provenance system |
| T5 Predicate result is `None` | ENGINEERING | Verdict integrity | Required result exists with a null value | `decide()` records unavailable predicate and takes the uncertainty path | `test_unavailable_or_malformed_predicate_never_allows` | MITIGATED | Exact outcome still depends on compensability and manifest handling |
| T6 Predicate result is missing | ENGINEERING | Verdict integrity | Required result key is absent | Same explicit availability check; missing is not a passing boolean | Same focused regression with `{}` | MITIGATED | Manifest may map uncertainty to `MODIFY`, which still requires valid modified arguments |
| T7 Predicate result is malformed | ENGINEERING | Verdict integrity | Result is non-boolean or wrong type | Exact `bool` type check routes it to uncertainty | Same focused regression with a non-boolean value | MITIGATED | Predicate-engine exceptions outside this returned-result contract can still abort the gate |
| T8 Source row is missing | ENGINEERING | Evidence integrity | Lookup finds no entity | Resolver returns `Confidence.NONE` evidence; decision does not manufacture a favorable fact | `test_missing_order_and_null_field_remain_distinct_unverified_evidence`; missing-evidence decision test | MITIGATED | Availability of a decision is reduced; posture varies by use case |
| T9 Source field is NULL/incomplete | ENGINEERING | Evidence integrity | Existing row has an unavailable field | Resolver marks unavailable; predicate sentinel is erased back to `None` | NULL resolver regression; `test_null_or_missing_date_is_unavailable_not_a_zen_exception` | MITIGATED | Unmodelled nullable fields may still fail elsewhere |
| T10 Source is unavailable | OPERATIONAL | Execution and data confidentiality | Database is absent, locked, or unreadable | Typed `SourceUnavailable`; manifest-specific open/closed intervention | `sqlite_source.py`; `test_missing_source_is_typed_and_not_created`; posture regression | PARTIALLY MITIGATED | Knowledge-assistant compensable outage posture is open and can execute original arguments without entitlement evidence |
| T11 Source schema/programming failure | ENGINEERING | Integrity and availability | Table/column/schema is malformed | Availability translator rethrows non-availability errors; no favorable decision is fabricated | `translate_availability`; `test_schema_failure_remains_loud` | PARTIALLY MITIGATED | Unhandled failure causes denial of service and may omit a receipt |
| T12 Multiple current policy rows | ENGINEERING | Policy integrity | More than one policy row is marked current | Typed ambiguity becomes `SOURCE_UNRELIABLE` and `BLOCK` | `PolicyResolver`; ambiguity resolver and gate regressions | MITIGATED | Does not validate whether the single selected row is substantively correct |
| T13 Silent policy supersession | ENGINEERING | Policy freshness | Agent uses an older version while a new row is current | Query selects `effective_to IS NULL`; asserted and resolved versions are compared | `registry/policy.py`; policy resolver and clause mismatch tests | MITIGATED | Applies to the modelled policy path, not arbitrary record histories |
| T14 `MODIFY` with absent/`None` arguments | ENGINEERING | Execution integrity | Decision requests modification without a payload | Dispatch raises `Pending`; original arguments are not substituted | `intercept.py`; `test_modify_without_args_never_executes_original` | MITIGATED | No component currently constructs a semantically validated modified payload |
| T15 `MODIFY` with non-dict arguments | ENGINEERING | Execution integrity | Modified payload has an invalid representation | Structural type check refuses execution | `test_structurally_invalid_modify_args_never_execute_original` | MITIGATED | A dictionary can still be semantically invalid |
| T16 `MODIFY` with `{}` | ENGINEERING | Execution integrity | Explicit empty mapping is supplied | Empty mapping is passed exactly; original arguments are not reused | `test_modify_with_empty_mapping_does_not_reuse_original_args` | MITIGATED | The tool may reject `{}` or interpret it dangerously; no semantic validation is supplied |
| T17 Valid explicit `MODIFY` | ENGINEERING | Executed arguments | Explicit dictionary is supplied | Dispatch executes exactly that dictionary | `test_modify_with_valid_args_executes_exactly_modified_values` | PARTIALLY MITIGATED | “Valid” is structural, not tool-schema or business-semantic validity; receipt records the pre-dispatch action rather than executed modified arguments |
| T18 Completed duplicate execution | ENGINEERING | Side-effect uniqueness | Completed key is reused in the same process | Stored result is replayed without another implementation call | `idempotency.py`; `test_completed_duplicate_replays_without_reexecution` | MITIGATED | Scope is one process and one retained key |
| T19 Retry after indeterminate execution | ENGINEERING | Side-effect uniqueness | Tool raises after side effects may have occurred | Key remains indeterminate and subsequent same-key execution is suppressed | `test_failed_execution_remains_indeterminate` | MITIGATED | Recovery requires operator/application logic; restart loses the state |
| T20 Different keys for same action | OPERATIONAL | Side-effect uniqueness | Caller changes trace ID or otherwise derives a new key | None by design; distinct keys execute independently | `_idempotency_key`; deterministic-key and distinct-key tests | DOCUMENTED LIMITATION | Idempotency requires reuse of trace ID plus predicate facts |
| T21 Caller bypasses interception | SECURITY | All governed assets | Caller sets gate off or invokes implementation directly | Repository hygiene test checks one refund implementation call pattern | `dispatch_tool`; `SessionContext.gate_enabled`; `test_issue_refund_impl_is_never_called_outside_the_registry` | DOCUMENTED LIMITATION | No process, privilege, import, or cryptographic enforcement; knowledge-assistant implementation lacks the same static check |
| T22 Process restart loses ledger | OPERATIONAL | Side-effect uniqueness | Process exits between attempts | None; ledger is intentionally in memory | `idempotency.py` module contract | DOCUMENTED LIMITATION | Retry after restart can execute again; state is not shared or durable |
| T23 Receipt/telemetry tampering | SECURITY | Audit integrity | Stored JSON is edited or deleted | HMAC verification detects changed receipt fields when key remains secret and verification is invoked | `receipt.py::verify`; `test_tampered_receipt_fails_verification` | PARTIALLY MITIGATED | Whole-line deletion, reordering, and telemetry edits are undetectable; no automatic verification on read |
| T24 Forged or replayed receipt | SECURITY | Audit authenticity | Attacker fabricates or reuses a valid receipt | HMAC prevents fabrication without the shared key | `build_receipt`; `verify` | PARTIALLY MITIGATED | No freshness, audience, sequence, chain, replay, or deletion control; deterministic receipt IDs do not enforce uniqueness |
| T25 Shared-secret compromise | EXTERNAL | HMAC key and audit authenticity | Key holder or host is compromised | No in-repository key custody, rotation, or asymmetric signing control | `_secret()` reads `CP_RECEIPT_SECRET`; receipt documentation recommends external secret management | EXTERNAL CONSTRAINT | A key holder can forge receipts; HMAC provides no non-repudiation |
| T26 Unsigned telemetry | SECURITY | Operational evidence | Coverage/latency blocks are altered | None; telemetry is added outside the signed receipt | `telemetry.record`; `receipt.build_receipt` | DOCUMENTED LIMITATION | Operational metrics can be changed without invalidating the receipt HMAC |
| T27 Agent and resolver share a store | RESEARCH | Source independence | Agent retrieval and resolver ultimately read the same underlying data | Scoped re-query can correct query context | Servicing agent/order resolver; related-work limitations | DOCUMENTED LIMITATION | Freshness is not statistical or source independence; correlated source error remains |
| T28 Source returns incorrect data | OPERATIONAL | Business-record truth | Read succeeds but stored value is wrong | Per-field reliability classes and a decision reliability floor | `freshness.py`; reliability decision and invariant tests | DOCUMENTED LIMITATION | Metadata is trusted and many fields default to corroborated; no independent truth oracle exists |
| T29 Compensability/open posture | OPERATIONAL | Execution confidentiality/integrity | Configuration permits action during uncertainty or outage | Posture is explicit and tested rather than hidden | Manifests; source-unavailability posture regression | DOCUMENTED LIMITATION | Open posture intentionally permits execution; it is not a blanket fail-closed design |
| T30 Dormant manifest controls | ENGINEERING | Policy expectations | Reader assumes every declared field is enforced | Active fields are read explicitly; unsupported fields are not silently synthesized | `manifest.py`; code search | DOCUMENTED LIMITATION | Risk tier, latency budget, escalation budget, and retention declarations are not enforcement controls |
| T31 Unexpected action structure | ENGINEERING | Gate availability and argument integrity | Provider/caller supplies unknown tool, missing fields, extra fields, or wrong types | Pydantic action model; unmodelled tools and missing compensation/resolver mappings fail loudly | `extract.py`; `schema.py`; unmodelled-tool tests | PARTIALLY MITIGATED | Raw arguments are not validated against the registered tool's full schema before dispatch |
| T32 Extraction differs from agent intent | RESEARCH | Claim completeness | Extractor omits or changes intended meaning | Nullable constrained extraction; failure falls back to unavailable claims | `_ClaimedFields`; extraction fixture tests | NOT TESTED | No adversarial prompt-injection or independent intent-label evaluation exists; provider failure and extraction failure can collapse to the same result |
| T33 Authorization/recipient mismatch | SECURITY | Document confidentiality | Before Step 6A, the resolver authorized `session.subject_id` while execution targeted `action.recipient_id` | Step 6A changed entitlement resolution to check the actual execution recipient carried by `action.recipient_id`; an unentitled recipient produces refusal/`BLOCK` | `entitlements.py`; `test_authorized_recipient_executes_normally`; `test_entitlement_is_checked_for_execution_recipient`; `test_existing_cross_tenant_dispatch_remains_blocked`; direct entitlement regression | MITIGATED | `SessionContext` identity remains caller-supplied and ControlPlane does not authenticate the caller or establish delegation authority; bypass, configured outage posture, and universal authorization security remain outside this result |
| T34 Cross-tenant access attempt | SECURITY | Tenant data | Agent proposes a document outside the execution recipient's entitlement | Classification and customer entitlement are separately resolved for the actual recipient and a contradiction blocks | `test_entitlement_check_blocks_the_cross_tenant_record`; `test_entitlement_is_checked_for_execution_recipient`; `test_existing_cross_tenant_dispatch_remains_blocked`; `test_full_gate_blocks_the_cross_tenant_send` | PARTIALLY MITIGATED | T10, T21, and T29 remain reachable paths; caller identity and delegation authority are not established by ControlPlane |
| T35 Sensitive downstream disclosure | SECURITY | Document/PII confidentiality | Outbound excerpt contains sensitive data or reaches the wrong recipient | Entitlement is load-bearing; PII detection records a moderate-confidence signal | `ladder.py`; `pii.py`; knowledge-assistant tests | PARTIALLY MITIGATED | PII detection is deliberately non-load-bearing and incomplete; an allowed, bypassed, or fail-open send can disclose data |

## Established security properties

| Property | Established? | Evidence | Exact scope | What is not proven |
|---|---|---|---|---|
| Claim/fact separation | YES | `facts_for_predicate()` and predicate test | Prose-derived `claimed_*` fields do not enter predicate factual inputs | Structural tool arguments are not trustworthy merely because they are structural |
| Predicate uncertainty safety | YES | `decide.py` and focused `None`/missing/non-boolean regressions | Required returned flags must be real booleans; uncertainty cannot count as predicate success | No proof for arbitrary predicate-engine crashes or malicious graph changes |
| Missing-row and NULL handling | YES | Resolver and predicate regressions | Modelled missing/nullable fields become unavailable evidence | Availability and policy posture can still reduce service or permit execution |
| Source-outage handling | PARTIAL | Typed errors and open/closed posture regression | Recognized SQLite availability failures become explicit decisions | Open posture can execute; other dependency failures may propagate |
| Ambiguous-policy handling | YES | Typed resolver error and gate regression | Multiple current rows block | Correctness of a single row is assumed |
| `MODIFY` fallback safety | YES | Dispatch source and focused regressions | Missing/non-dict payloads do not execute; `{}` and explicit dicts never fall back to originals | Dictionary contents are not semantically validated |
| Valid `MODIFY` argument selection | YES | Exact-arguments regression | Explicit dictionary is the dictionary passed to the implementation | Tool-schema validity, business safety, and receipt binding are not proven |
| Completed duplicate suppression | YES | Ledger source and duplicate regression | Same completed key in one process returns stored result | Restart, multi-process, expiry, collision handling, and distinct keys are outside this property |
| Indeterminate retry suppression | YES | Failure regression | Same key remains suppressed after an exception in the same process | No durable recovery or restart protection |
| Execution interception | PARTIAL | `dispatch_tool()` and static repository test | Included agents route their registered calls through the central function | No non-bypassable boundary or authenticated gate-enable control |
| Receipt field integrity | PARTIAL | HMAC source and tamper regression | Changed receipt fields are detectable by a verifier without key compromise | Deletion, replay, ordering, telemetry, execution outcome, and non-repudiation are not covered |
| Source freshness | PARTIAL | Resolver queries and policy-current test | The query is performed at adjudication; policy path selects the current row | Freshness does not establish truth, independence, or uncompromised infrastructure |
| Authorization binding | PARTIAL | `entitlements.py` and Step 6A knowledge-assistant regressions | The governed `send_document` path checks classification and customer entitlement for the same `action.recipient_id` that dispatch executes | Caller authentication, delegation authority, bypass resistance, configured fail-open behavior, and universal authorization security are not proven |
| Non-bypassability | NO | Gate-off branch and ordinary Python callability | None | Process/privilege mediation is absent |
| Adversarial robustness | NO | No current-candidate adversarial evaluation | None | Hostile-agent, hostile-caller, compromised-source, and red-team effectiveness are not established |

## High-risk attack paths

- Incorrect claim -> `claimed_*` boundary -> resolver/predicate checks -> selected false claims can be blocked; unmodelled semantics remain.
- Stale policy context -> current-row resolver -> clause and business predicates -> the modelled supersession case is caught; general stale context remains influential upstream.
- Missing row -> unavailable evidence -> uncertainty decision -> no favorable fact is fabricated.
- Malformed predicate -> boolean type check -> uncertainty decision -> it cannot silently pass.
- Invalid `MODIFY` -> dispatch structural check -> `Pending` -> original arguments do not execute.
- Same-key duplicate -> in-memory ledger -> result replay or indeterminate suppression -> restart remains a re-execution risk.
- Caller bypass -> gate-off/direct call -> no enforcing boundary -> all gate defenses can be skipped.
- Receipt edit -> optional HMAC verification -> changed signed fields are detected -> deletion, replay, and telemetry edits remain.
- Restart -> ledger loss -> later retry appears new -> duplicate execution can recur.
- Incorrect record -> successful resolver read -> reliability metadata only -> a confidently wrong source can drive a wrong decision.
- Recipient mismatch -> `action.recipient_id` is carried into entitlement claims -> resolver checks that execution recipient -> an unentitled recipient is blocked; caller authentication, delegation authority, and bypass resistance remain external.
- Knowledge-source outage -> typed outage -> configured open posture -> original `send_document` arguments may execute without entitlement evidence.

## Residual risks

Priorities below are an engineering assessment based on impact, reachable exposure in the reviewed code, and strength of evidence. They are not measured probabilities.

| Priority | Risks | Basis |
|---|---|---|
| P0 | T10/T29 knowledge-assistant outage fail-open | The intentionally configured open posture can execute without available entitlement evidence |
| P1 | T2/T17 semantic argument gaps; T21 bypass; T22 durability; T23-T26 audit gaps; T28 source correctness; unauthenticated session identity | High-impact properties depend on caller discipline, source trust, process lifetime, or key custody |
| P2 | T27 same-store dependence; T32 extraction/intent uncertainty; absent adversarial and external validation | These limit research and assurance claims but do not independently prove an exploit |
| P3 | T30 dormant controls; stronger log chaining, retention enforcement, distributed idempotency, and broader policy validation | Future hardening that does not alter the narrow verified properties above |

## Important non-goals

This document does not establish or claim production readiness, security completeness, non-bypassability, tamper-proof logging, adversarial robustness, formal verification, zero-trust operation, attack resistance, universal fail-closed behavior, cryptographic immutability, external security validation, broad enterprise protection, or guaranteed policy compliance. It does not cover compromised operators, hosts, manifests, code, databases, or unknown deployment environments.

Engineering defense is not a security proof. A regression test is not adversarial validation. A threat model is not a red-team result. A fresh query is not proof of source truth or independence. An HMAC-authenticated receipt is not a tamper-proof audit system. A central call site is not a non-bypassable boundary.

## Relationship to research claims

The enforcement point overlaps AgentLTL's online gating, AEGIS and Open Agent Passport's pre-execution controls, C-Trace's runtime intervention, AgentCore Policy's external policy enforcement, and LedgerAgent's maintained-state checks. AEGIS's chained asymmetric audit design is stronger than this repository's shared-secret, unchained receipt. Open Agent Passport and AgentCore foreground principal authorization, while this candidate does not authenticate its session identity. These comparisons constrain claims; they do not make the threat model a research contribution.

The included tests demonstrate engineering behavior in synthetic fixtures. Off-release failure injection, benchmark, ablation, latency, P06, and tau2 material does not establish current-candidate attack resistance or security effectiveness. No final-candidate quantitative efficacy or adversarial result is asserted here.

## Conclusion

The current implementation demonstrates several narrow safeguards on the governed, gate-enabled path: prose claims are separated from predicate facts; predicate uncertainty does not silently pass; missing and ambiguous evidence has explicit handling; the actual `send_document` execution recipient is checked against document entitlements; invalid `MODIFY` payloads do not fall back to original arguments; and completed or indeterminate same-key executions are controlled within one process. It explicitly does not establish protection when callers bypass or disable the gate, when caller-supplied session identity or source data is wrong, when delegation authority is absent, when the knowledge-assistant outage posture permits execution, after idempotency state is lost, or when a receipt key or host is compromised. There is no universal authorization guarantee, adversarial proof, deployment-boundary enforcement, or production-security certification.
