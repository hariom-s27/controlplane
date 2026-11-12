# P3-A — manifest claim-coverage (kind level)

Harness: `bench/manifest_claim_coverage.py` (regenerate with `python bench/manifest_claim_coverage.py --write`). For each governed manifest it compares the ClaimKinds actually bound against the load-bearing kinds an independently authored reference — `bench/extraction_reference.py`, `extraction-reference-v1` — says that tool requires. The reference is authored only from the tool argument schema, the policy prose and `docs/threat-model.md`; it imports nothing from `controlplane/` and reads no manifest (`tests/test_extraction_reference.py` enforces this).

**Metric:** `bound required load-bearing kinds / independently required load-bearing kinds`. Zero required kinds ⇒ `not_assessed`, never `1.0`.

**What this is NOT:** instance-level extraction recall, precision, decomposition accuracy, or a silent-pass *rate* — those need an independent per-action reference claim corpus, which does not exist. They are `NOT_MEASURED` here, not estimated. A manifest at 100% only binds every kind the reference lists; the reference itself is human-authored and bounded by its author's reading. See `docs/extraction-reliability.md`.

| manifest | tool | status | coverage | bound / required (LB) | unbound load-bearing |
|---|---|---|--:|--:|---|
| `discount_approval` | `approve_discount` | assessed | 75% | 3 / 4 | AMOUNT_NOT_EXCEEDING_ORDER |
| `knowledge_assistant` | `send_document` | assessed | 100% | 2 / 2 | — |
| `service_credit_approval` | `approve_service_credit` | assessed | 100% | 3 / 3 | — |
| `servicing` | `issue_refund` | assessed | 100% | 7 / 7 | — |
| `tau2_cancel_pending_order` | `cancel_pending_order` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |
| `tau2_exchange_delivered_order_items` | `exchange_delivered_order_items` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |
| `tau2_modify_pending_order_address` | `modify_pending_order_address` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |
| `tau2_modify_pending_order_items` | `modify_pending_order_items` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |
| `tau2_modify_pending_order_payment` | `modify_pending_order_payment` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |
| `tau2_return_delivered_order_items` | `return_delivered_order_items` | assessed | 50% | 1 / 2 | ORDER_BELONGS_TO_CUSTOMER |

10 of 10 manifests assessed; 3 bind every required load-bearing kind; 7 have at least one unbound required load-bearing kind.

## Findings

- required load-bearing kind **AMOUNT_NOT_EXCEEDING_ORDER** is NOT bound by `discount_approval`
  - The active discount manifest does not bind this check; service_credit_approval, a structurally identical goodwill-credit action, does. Flagged for review — a deliberate goodwill exception or an oversight.
- required load-bearing kind **ORDER_BELONGS_TO_CUSTOMER** is NOT bound by `tau2_cancel_pending_order`, `tau2_exchange_delivered_order_items`, `tau2_modify_pending_order_address`, `tau2_modify_pending_order_items`, `tau2_modify_pending_order_payment`, `tau2_return_delivered_order_items`
  - No tau2 retail manifest binds this. The tau2 retail domain exposes no structural, DB-level authenticated-identity channel independent of the agent conversation (tau2's own task data documents this as an open issue). Binding it would need previous-tool-output as evidence (disallowed) or the evaluator's hidden ground truth (circular). The check stays required; the domain as integrated cannot satisfy it — this is not a one-line binding fix.

## Unrepresentable required checks (no ClaimKind — advisory, not in the ratio)

- **currency_integrity** (`approve_discount`, `approve_service_credit`, `issue_refund`): The disbursed currency should equal the order's currency; a payout in the wrong currency is a value error. No ClaimKind expresses currency / field integrity today.
- **independent_user_authentication** (`cancel_pending_order`, `exchange_delivered_order_items`, `modify_pending_order_address`, `modify_pending_order_items`, `modify_pending_order_payment`, `return_delivered_order_items`): There is no claim kind or evidence channel for 'the session user is who they claim to be' in the tau2 retail integration. ORDER_BELONGS_TO_CUSTOMER is the closest expressible check and is itself unbindable here (see its binding_note).

## Deliberately not required

ClaimKinds a reader might expect but which the reference intentionally omits, with the reason — so an absence is seen to be a choice, not an oversight.

- `send_document` — **EXCERPT_CONTAINS_THIRD_PARTY_PII**: PII in an excerpt does not by itself make the send wrong: if the recipient is entitled to that customer's record, the PII in it is fine. What makes a send wrong is the entitlement check failing — detection is a signal, not a gate. (Matches the knowledge-assistant use case's own thesis.)
- `approve_service_credit` — **WITHIN_REFUND_WINDOW**: A service complaint (late / damaged / poor experience) is explicitly not gated by how long ago the order was delivered — unlike a refund or a discount credit. The use case's own prose says there is no delivery-window check.

## Not measured here

- **instance_level_extraction_recall**: NOT_MEASURED — needs an independent per-action reference claim corpus
- **instance_level_precision**: NOT_MEASURED — needs an independent per-action reference claim corpus
- **decomposition_accuracy**: NOT_MEASURED — needs an independent per-action reference claim corpus
- **silent_pass_rate**: NOT_MEASURED — a RATE needs the per-action corpus; the per-manifest unbound-load-bearing list is the kind-level signal

Relationship to P1: P1 `verification_coverage` = verified / eligible over the claims the manifest *did* model. This metric = bound / *required* — the half P1 does not measure. A manifest can score 100% on P1 verification coverage and still have unbound required kinds here; the two numbers are orthogonal and P3-A does not change P1's.

