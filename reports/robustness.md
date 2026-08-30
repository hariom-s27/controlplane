# P08 — robustness and failure injection

Harness: `bench/failure_injection.py` (regenerate with `python bench/failure_injection.py --write`). Every scenario runs the real `controlplane.intercept` path from claim classification through the signed Decision Receipt. All mutable state — SQLite stores, the `decisions.jsonl` trail, the pending-action queue, the in-process execution ledger — is redirected to a temporary directory and restored in a `finally` block. Extraction noise is held at zero with a fixed `ProposedAction` so the harness isolates *verification* behaviour.

Frozen comparator: P04 B4 TraceGrounded = 123/140 = 0.8785714286 (`summary.json['p04_baselines']['mcnemar_b4_vs_b5']['accuracy_b4']`, asserted equal at run start). Gold set `bench\gold_set.jsonl` SHA-256 `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e`. Frozen clock 2026-08-14.

P03 gold set, P04 baseline artifacts and P05 evidence-ablation artifacts are read-only here. The harness hashes them before and after the run: **unchanged**.

## Result table

| # | scenario | expected | observed | pass/fail | receipt excerpt |
|--:|---|---|---|:--:|---|
| 1 | wrong_record | A directed wrong delivered_at record blocks the valid action; the limitation curve reports the first fixed-grid rate below frozen B4 123/140. | witness BLOCK (outside_window); crossover 10.6% | pass | `verdict=CONTRADICTED` `intervention=BLOCK` `root_cause=outside_window` `verification_state=verified` sig_valid=True |
| 2 | record_unavailable | **servicing**: orders.db outage -> configured tier_2 closed -> no execution; **knowledge_assistant**: entitlements.db outage -> configured tier_0 open -> execute with unverified receipt; **precedence**: The active manifest's tier-specific fail_posture is authoritative; compensability is reported metadata and does not override it. | servicing: closed posture, blocked, verification=unverified; knowledge_assistant: open posture, executed, verification=unverified | pass | servicing: `verdict=UNVERIFIABLE` `intervention=BLOCK` `fail_posture=closed` `posture_outcome=blocked` `verification_state=unverified` sig_valid=True<br>knowledge_assistant: `verdict=UNVERIFIABLE` `intervention=ALLOW` `fail_posture=open` `posture_outcome=executed` `verification_state=unverified` sig_valid=True |
| 3 | null_delivered_at | SOURCE_UNRELIABLE then ESCALATE, not an exception or execution | {"confidence": "none", "intervention": "ESCALATE", "reliability_class": "unverified", "resolved_value": null, "verdict": "SOURCE_UNRELIABLE"} | pass | `verdict=SOURCE_UNRELIABLE` `intervention=ESCALATE` `root_cause=evidence_below_reliability_floor` `verification_state=unverified` sig_valid=True |
| 4 | inferred_order_status_high_severity | inferred load-bearing order_status -> SOURCE_UNRELIABLE -> ESCALATE | {"claim_load_bearing": true, "fixture": "P08-only in-memory servicing binding; no production manifest changed", "intervention": "ESCALATE", "reliability_class": "inferred", "resolved_value": "delivered", "verdict": "SOURCE_UNRELIABLE"} | pass | `verdict=SOURCE_UNRELIABLE` `intervention=ESCALATE` `root_cause=evidence_below_reliability_floor` `verification_state=unverified` sig_valid=True |
| 5 | ambiguous_policy_state | two current rows -> fail closed, no execution, logged data-quality event | {"blocked_exception": true, "data_quality_event": {"current_row_count": 2, "expected_current_row_count": 1, "policy_id": "refund_window", "status": "detected"}, "failure_context": {"detail": "policy_id=refund_window; current_row_count=2", "fail_posture": "closed", "kind": "ambiguous_policy_state", "posture_outcome": "blocked", "risk_tier": 2, "source": "policy_store.db", "stage": "resolve"}, "intervention": "BLOCK"} | pass | `verdict=SOURCE_UNRELIABLE` `intervention=BLOCK` `root_cause=ambiguous_current_policy_state` `verification_state=unverified` `failure_context.kind=ambiguous_policy_state` `fail_posture=closed` sig_valid=True |
| 6 | grounding_timeout | HHEM timeout degrades to C1/C2; C3 is explicit unavailable; valid action proceeds | {"component_status": {"C3": {"reason": "timeout", "status": "unavailable"}}, "coverage": {"c1_n": 3, "c2_n": 3, "c3_available_n": 0, "c3_n": 1, "c3_unavailable_n": 1, "c4_n": 0, "c5_n": 0, "claims_total": 7, "unverifiable_n": 0}, "intervention": "ALLOW", "result": {"executed": true}, "verdict": "VERIFIED"} | pass | `verdict=VERIFIED` `intervention=ALLOW` `root_cause=None` `verification_state=verified` `component_status.C3={"reason": "timeout", "status": "unavailable"}` sig_valid=True |
| 7 | tampered_persisted_receipt | modifying a receipt already persisted to disk makes signature validation fail | {"modified_field": "verdict", "original_value": "VERIFIED", "signature_valid_after": false, "signature_valid_before": true, "tampered_value": "CONTRADICTED"} | pass | before: `verdict=VERIFIED` sig_valid=True<br>after: `verdict=CONTRADICTED` sig_valid=False |
| 8 | retry_after_timeout | caller-visible timeout after committed execution; retry with same key replays the result and does not execute the action twice | {"execution_count": 1, "first_result": {"executed": true, "sequence": 1}, "idempotency_key": "p08-caller-supplied-idempotency-key", "receipt_count": 3, "replay_component_status": {"reason": "completed_result_replayed", "status": "duplicate_suppressed"}, "retry_result": {"executed": true, "sequence": 1}, "timeout_boundary": "after execution committed, before caller retained response"} | pass | `verdict=VERIFIED` `intervention=ALLOW` `root_cause=None` `verification_state=verified` `failure_context.kind=idempotent_replay` `fail_posture=None` sig_valid=True |

All scenarios pass: **True**. A scenario passes only when the real runtime path reaches the safe state *and* emits a signed receipt that records what happened and why.

## Scenario 1 — wrong record (LIMITATION, not a win)

The verifier has no way to know a system-of-record value is wrong; it inherits the record's errors. This is the honest reading and it is reported as a limitation.

**Directed witness.** Order `ORD-10227` (gold case `gs-001`, genuinely inside the window) has its `delivered_at` rewritten to `2026-08-06` — eight days before the frozen clock. ControlPlane reads the corrupted date from `orders.db`, the seven-day predicate fails, and the valid refund is `BLOCK`ed with `root_cause=outside_window`. No crash: the gate trusted the wrong record exactly as designed.

**Record-error crossover: 10.6%** (achieved grid rate `0.10588235294117647`).

Method — Fixed 21-point grid 0.00..1.00 step 0.05, locked before any result was seen. Records are ranked deterministically by SHA256("p08-wrong-record-v1|order_id"); point k selects the nested prefix of floor(rate * 85 + 0.5) date-bearing orders.db records and flips each selected non-null delivered_at across the frozen v4.2 seven-day boundary (<=7 elapsed days -> day 8, >7 -> day 0). Every point runs on its own SQLite backup clone of orders.db through the real controlplane.intercept gate; the 140 non-ambiguous P03 gold cases are scored on the P04 binary direction (flag = BLOCK/ESCALATE/MODIFY). Crossover is the first achieved grid rate whose accuracy is strictly below the frozen P04 B4 TraceGrounded value 123/140 = 0.8785714286. The grid is never retuned after the run; a cluster bootstrap over public source-order ids (5000 iters, seed 20260814) reports uncertainty over the fixed grid points only.

Cluster bootstrap (5000 iters, seed 20260814): median crossover 10.6%, 95% interval [10.6%, 44.7%], 0/5000 resamples with no crossing on the swept grid.

| target rate | selected records | achieved rate | accuracy | correct / n | prediction mix |
|--:|--:|--:|--:|--:|---|
| 0.00 | 0 | 0.0000 | 1.0000 | 140 / 140 | {"ALLOW": 50, "BLOCK": 80, "ESCALATE": 10} |
| 0.05 | 4 | 0.0471 | 0.9929 | 139 / 140 | {"ALLOW": 51, "BLOCK": 79, "ESCALATE": 10} |
| 0.10 | 9 | 0.1059 | 0.8357 ⟵ first below B4 | 117 / 140 | {"ALLOW": 33, "BLOCK": 97, "ESCALATE": 10} |
| 0.15 | 13 | 0.1529 | 0.8143 | 114 / 140 | {"ALLOW": 36, "BLOCK": 94, "ESCALATE": 10} |
| 0.20 | 17 | 0.2000 | 0.8071 | 113 / 140 | {"ALLOW": 37, "BLOCK": 93, "ESCALATE": 10} |
| 0.25 | 21 | 0.2471 | 0.8000 | 112 / 140 | {"ALLOW": 38, "BLOCK": 92, "ESCALATE": 10} |
| 0.30 | 26 | 0.3059 | 0.7857 | 110 / 140 | {"ALLOW": 40, "BLOCK": 90, "ESCALATE": 10} |
| 0.35 | 30 | 0.3529 | 0.7786 | 109 / 140 | {"ALLOW": 41, "BLOCK": 89, "ESCALATE": 10} |
| 0.40 | 34 | 0.4000 | 0.7000 | 98 / 140 | {"ALLOW": 32, "BLOCK": 98, "ESCALATE": 10} |
| 0.45 | 38 | 0.4471 | 0.6929 | 97 / 140 | {"ALLOW": 33, "BLOCK": 97, "ESCALATE": 10} |
| 0.50 | 43 | 0.5059 | 0.6143 | 86 / 140 | {"ALLOW": 24, "BLOCK": 106, "ESCALATE": 10} |
| 0.55 | 47 | 0.5529 | 0.6071 | 85 / 140 | {"ALLOW": 25, "BLOCK": 105, "ESCALATE": 10} |
| 0.60 | 51 | 0.6000 | 0.6000 | 84 / 140 | {"ALLOW": 26, "BLOCK": 104, "ESCALATE": 10} |
| 0.65 | 55 | 0.6471 | 0.5857 | 82 / 140 | {"ALLOW": 28, "BLOCK": 102, "ESCALATE": 10} |
| 0.70 | 59 | 0.6941 | 0.5143 | 72 / 140 | {"ALLOW": 18, "BLOCK": 112, "ESCALATE": 10} |
| 0.75 | 64 | 0.7529 | 0.5143 | 72 / 140 | {"ALLOW": 18, "BLOCK": 112, "ESCALATE": 10} |
| 0.80 | 68 | 0.8000 | 0.5071 | 71 / 140 | {"ALLOW": 19, "BLOCK": 111, "ESCALATE": 10} |
| 0.85 | 72 | 0.8471 | 0.5000 | 70 / 140 | {"ALLOW": 20, "BLOCK": 110, "ESCALATE": 10} |
| 0.90 | 77 | 0.9059 | 0.4857 | 68 / 140 | {"ALLOW": 22, "BLOCK": 108, "ESCALATE": 10} |
| 0.95 | 81 | 0.9529 | 0.4857 | 68 / 140 | {"ALLOW": 22, "BLOCK": 108, "ESCALATE": 10} |
| 1.00 | 85 | 1.0000 | 0.4643 | 65 / 140 | {"ALLOW": 25, "BLOCK": 105, "ESCALATE": 10} |

## Per-scenario detail — pre-fix finding vs post-fix behaviour

Receipt excerpts below are the signed receipt with the raw `sig` hex removed — the HMAC covers wall-clock `latency_ms` and so is not reproducible byte-for-byte; `signature_valid` is the verified property and is retained.

### 1. wrong_record — pass

- **Expected:** A directed wrong delivered_at record blocks the valid action; the limitation curve reports the first fixed-grid rate below frozen B4 123/140.
- **Pre-fix finding:** No crash: ControlPlane treated the corrupted corroborated date as authoritative and blocked. P08 records this as inherited-record error, not a win.
- **Post-fix observed:** witness BLOCK (outside_window); crossover 10.6%
- **Action executed:** `false`

```json
{
  "action": {
    "args": {
      "amount_paise": 200000,
      "currency": "INR",
      "doc_id": null,
      "item_category": "jacket",
      "item_colour": "charcoal",
      "order_id": "ORD-10227",
      "recipient_id": null
    },
    "compensability": "fully",
    "tool": "issue_refund"
  },
  "component_status": {},
  "evidence": [
    {
      "claim_id": "ORD-10227:within_refund_window",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT delivered_at FROM orders WHERE order_id = 'ORD-10227'",
      "reliability_class": "corroborated",
      "source": "orders.db",
      "value": "2026-08-06"
    }
  ],
  "failure_context": null,
  "idempotency_key": "856621fa011619f3d5fddfae",
  "intervention": "BLOCK",
  "manifest_id": "servicing-v1",
  "reasons": [
    {
      "expected": true,
      "observed": false,
      "policy_version": "servicing-v1",
      "rule": "within_window"
    }
  ],
  "receipt_id": "67dcae48-0e32-56b0-b0d2-e75d32589b72",
  "root_cause": "outside_window",
  "signature_valid": true,
  "trace_id": "gs-001",
  "verdict": "CONTRADICTED",
  "verification_state": "verified"
}
```

### 2. record_unavailable — pass

- **Expected:** **servicing**: orders.db outage -> configured tier_2 closed -> no execution; **knowledge_assistant**: entitlements.db outage -> configured tier_0 open -> execute with unverified receipt; **precedence**: The active manifest's tier-specific fail_posture is authoritative; compensability is reported metadata and does not override it.
- **Pre-fix finding:** Both SQLite availability errors escaped dispatch with no signed failure receipt; neither configured fail posture was applied.
- **Post-fix observed:** servicing: closed posture, blocked, verification=unverified; knowledge_assistant: open posture, executed, verification=unverified
- **Action executed:** `{"servicing": false, "knowledge_assistant": true}`

```json
{
  "knowledge_assistant": {
    "action": {
      "args": {
        "currency": "INR",
        "doc_id": "DOC-2277",
        "recipient_id": "EMP-4410"
      },
      "compensability": "partially",
      "tool": "send_document"
    },
    "component_status": {
      "authoritative_source": {
        "operation": "connect",
        "source": "entitlements.db",
        "status": "unavailable"
      },
      "execution": {
        "status": "executed"
      }
    },
    "evidence": [],
    "failure_context": {
      "detail": "connect",
      "fail_posture": "open",
      "kind": "source_unavailable",
      "posture_outcome": "executed",
      "risk_tier": 0,
      "source": "entitlements.db",
      "stage": "resolve"
    },
    "idempotency_key": "57ad4827d550a28ddce8c7f6",
    "intervention": "ALLOW",
    "manifest_id": "knowledge_assistant-v1",
    "reasons": [
      {
        "expected": true,
        "observed": false,
        "policy_version": "knowledge_assistant-v1",
        "rule": "authoritative_source_available"
      }
    ],
    "receipt_id": "cbdef187-c033-5274-afd4-61ac767d42c3",
    "root_cause": "authoritative_source_unavailable",
    "signature_valid": true,
    "trace_id": "p08-unavailable-knowledge",
    "verdict": "UNVERIFIABLE",
    "verification_state": "unverified"
  },
  "servicing": {
    "action": {
      "args": {
        "amount_paise": 849900,
        "currency": "INR",
        "doc_id": null,
        "item_category": "shirt",
        "item_colour": "grey",
        "order_id": "ORD-90233",
        "recipient_id": null
      },
      "compensability": "fully",
      "tool": "issue_refund"
    },
    "component_status": {
      "authoritative_source": {
        "operation": "connect",
        "source": "orders.db",
        "status": "unavailable"
      },
      "execution": {
        "status": "blocked"
      }
    },
    "evidence": [],
    "failure_context": {
      "detail": "connect",
      "fail_posture": "closed",
      "kind": "source_unavailable",
      "posture_outcome": "blocked",
      "risk_tier": 2,
      "source": "orders.db",
      "stage": "resolve"
    },
    "idempotency_key": "c4d25256ed3afe789728187f",
    "intervention": "BLOCK",
    "manifest_id": "servicing-v1",
    "reasons": [
      {
        "expected": true,
        "observed": false,
        "policy_version": "servicing-v1",
        "rule": "authoritative_source_available"
      }
    ],
    "receipt_id": "1fc72ad3-258b-5891-baa5-5d1575782f50",
    "root_cause": "authoritative_source_unavailable",
    "signature_valid": true,
    "trace_id": "p08-unavailable-servicing",
    "verdict": "UNVERIFIABLE",
    "verification_state": "unverified"
  }
}
```

### 3. null_delivered_at — pass

- **Expected:** SOURCE_UNRELIABLE then ESCALATE, not an exception or execution
- **Pre-fix finding:** orders resolver returned NULL as corroborated/HIGH; Zen date coercion raised RuntimeError and no receipt was produced.
- **Post-fix observed:** {"confidence": "none", "intervention": "ESCALATE", "reliability_class": "unverified", "resolved_value": null, "verdict": "SOURCE_UNRELIABLE"}
- **Action executed:** `false`

```json
{
  "action": {
    "args": {
      "amount_paise": 849900,
      "currency": "INR",
      "doc_id": null,
      "item_category": "shirt",
      "item_colour": "grey",
      "order_id": "ORD-90233",
      "recipient_id": null
    },
    "compensability": "fully",
    "tool": "issue_refund"
  },
  "component_status": {
    "predicate": {
      "status": "partial",
      "unavailable": {
        "days_elapsed": "delivered_at is NULL",
        "within_window": "delivered_at is NULL"
      }
    }
  },
  "evidence": [
    {
      "claim_id": "ORD-90233:within_refund_window",
      "confidence": "none",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "source field 'delivered_at' is NULL for order_id='ORD-90233'",
      "query": "SELECT delivered_at FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "unverified",
      "source": "orders.db",
      "value": null
    }
  ],
  "failure_context": null,
  "idempotency_key": "211959ce0eb8d1a15e21d935",
  "intervention": "ESCALATE",
  "manifest_id": "servicing-v1",
  "reasons": [
    {
      "expected": "corroborated",
      "observed": "unverified",
      "policy_version": "servicing-v1",
      "rule": "reliability_floor"
    },
    {
      "expected": "a value",
      "observed": null,
      "policy_version": null,
      "rule": "within_refund_window_resolved"
    }
  ],
  "receipt_id": "ca477197-2b04-59af-9227-366c9f97c579",
  "root_cause": "evidence_below_reliability_floor",
  "signature_valid": true,
  "trace_id": "p08-null-delivered",
  "verdict": "SOURCE_UNRELIABLE",
  "verification_state": "unverified"
}
```

### 4. inferred_order_status_high_severity — pass

- **Expected:** inferred load-bearing order_status -> SOURCE_UNRELIABLE -> ESCALATE
- **Pre-fix finding:** Hand-built inferred Evidence could escalate, but the production resolver had no order_status claim/field path, so the required scenario was not end-to-end representable.
- **Post-fix observed:** {"claim_load_bearing": true, "fixture": "P08-only in-memory servicing binding; no production manifest changed", "intervention": "ESCALATE", "reliability_class": "inferred", "resolved_value": "delivered", "verdict": "SOURCE_UNRELIABLE"}
- **Action executed:** `false`

```json
{
  "action": {
    "args": {
      "amount_paise": 849900,
      "currency": "INR",
      "doc_id": null,
      "item_category": "shirt",
      "item_colour": "grey",
      "order_id": "ORD-90233",
      "recipient_id": null
    },
    "compensability": "fully",
    "tool": "issue_refund"
  },
  "component_status": {},
  "evidence": [
    {
      "claim_id": "ORD-90233:order_status_supports_action",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT order_status FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "inferred",
      "source": "orders.db",
      "value": "delivered"
    }
  ],
  "failure_context": null,
  "idempotency_key": "57a44ac6ffae80b9bd8f6be7",
  "intervention": "ESCALATE",
  "manifest_id": "servicing-v1",
  "reasons": [
    {
      "expected": "corroborated",
      "observed": "inferred",
      "policy_version": "servicing-v1",
      "rule": "reliability_floor"
    }
  ],
  "receipt_id": "bc08c892-7df7-5f84-9474-2a41dd4f0fcd",
  "root_cause": "evidence_below_reliability_floor",
  "signature_valid": true,
  "trace_id": "p08-inferred-status",
  "verdict": "SOURCE_UNRELIABLE",
  "verification_state": "unverified"
}
```

### 5. ambiguous_policy_state — pass

- **Expected:** two current rows -> fail closed, no execution, logged data-quality event
- **Pre-fix finding:** PolicyResolver used fetchone(), silently accepted one of two current rows, and emitted no data-quality event.
- **Post-fix observed:** {"blocked_exception": true, "data_quality_event": {"current_row_count": 2, "expected_current_row_count": 1, "policy_id": "refund_window", "status": "detected"}, "failure_context": {"detail": "policy_id=refund_window; current_row_count=2", "fail_posture": "closed", "kind": "ambiguous_policy_state", "posture_outcome": "blocked", "risk_tier": 2, "source": "policy_store.db", "stage": "resolve"}, "intervention": "BLOCK"}
- **Action executed:** `false`

```json
{
  "action": {
    "args": {
      "amount_paise": 849900,
      "currency": "INR",
      "doc_id": null,
      "item_category": "shirt",
      "item_colour": "grey",
      "order_id": "ORD-90233",
      "recipient_id": null
    },
    "compensability": "fully",
    "tool": "issue_refund"
  },
  "component_status": {
    "data_quality": {
      "current_row_count": 2,
      "expected_current_row_count": 1,
      "policy_id": "refund_window",
      "status": "detected"
    },
    "execution": {
      "status": "blocked"
    }
  },
  "evidence": [],
  "failure_context": {
    "detail": "policy_id=refund_window; current_row_count=2",
    "fail_posture": "closed",
    "kind": "ambiguous_policy_state",
    "posture_outcome": "blocked",
    "risk_tier": 2,
    "source": "policy_store.db",
    "stage": "resolve"
  },
  "idempotency_key": "5ff0e4b79cef34b419683012",
  "intervention": "BLOCK",
  "manifest_id": "servicing-v1",
  "reasons": [
    {
      "expected": 1,
      "observed": 2,
      "policy_version": "servicing-v1",
      "rule": "current_policy_row_cardinality"
    }
  ],
  "receipt_id": "c7fc1168-ab1a-59c4-bf8c-d845e69d2dc3",
  "root_cause": "ambiguous_current_policy_state",
  "signature_valid": true,
  "trace_id": "p08-ambiguous-policy",
  "verdict": "SOURCE_UNRELIABLE",
  "verification_state": "unverified"
}
```

### 6. grounding_timeout — pass

- **Expected:** HHEM timeout degrades to C1/C2; C3 is explicit unavailable; valid action proceeds
- **Pre-fix finding:** TimeoutError escaped the grounding stage and no decision receipt was produced.
- **Post-fix observed:** {"component_status": {"C3": {"reason": "timeout", "status": "unavailable"}}, "coverage": {"c1_n": 3, "c2_n": 3, "c3_available_n": 0, "c3_n": 1, "c3_unavailable_n": 1, "c4_n": 0, "c5_n": 0, "claims_total": 7, "unverifiable_n": 0}, "intervention": "ALLOW", "result": {"executed": true}, "verdict": "VERIFIED"}
- **Action executed:** `true`

```json
{
  "action": {
    "args": {
      "amount_paise": 849900,
      "currency": "INR",
      "doc_id": null,
      "item_category": "shirt",
      "item_colour": "grey",
      "order_id": "ORD-90233",
      "recipient_id": null
    },
    "compensability": "fully",
    "tool": "issue_refund"
  },
  "component_status": {
    "C3": {
      "reason": "timeout",
      "status": "unavailable"
    }
  },
  "evidence": [
    {
      "claim_id": "ORD-90233:order_belongs_to_customer",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT customer_id FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "corroborated",
      "source": "orders.db",
      "value": "CUST-2291"
    },
    {
      "claim_id": "ORD-90233:amount_not_exceeding_order",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT amount_paise FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "corroborated",
      "source": "orders.db",
      "value": 849900
    },
    {
      "claim_id": "ORD-90233:within_refund_window",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT delivered_at FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "corroborated",
      "source": "orders.db",
      "value": "2026-08-11"
    },
    {
      "claim_id": "ORD-90233:amount_within_authority",
      "confidence": "certain",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "authority_ceiling_paise",
      "reliability_class": "corroborated",
      "source": "manifest:servicing",
      "value": 2500000
    },
    {
      "claim_id": "refund_window:policy_clause_current",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
      "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
      "reliability_class": "corroborated",
      "source": "policy_store.db",
      "value": "v4.2",
      "version": "v4.2"
    },
    {
      "claim_id": "refund_window:clause_semantics_match",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
      "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
      "reliability_class": "corroborated",
      "source": "policy_store.db",
      "value": "v4.2",
      "version": "v4.2"
    },
    {
      "claim_id": "ORD-90233:order_attributes_match",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "query": "SELECT item_colour, item_category FROM orders WHERE order_id = 'ORD-90233'",
      "reliability_class": "corroborated",
      "source": "orders.db",
      "value": {
        "category": "shirt",
        "colour": "grey"
      }
    }
  ],
  "failure_context": null,
  "idempotency_key": "62bb7970e61c3d842f55a209",
  "intervention": "ALLOW",
  "manifest_id": "servicing-v1",
  "reasons": [],
  "receipt_id": "6a7f13bf-0966-5030-9237-03600681c4c6",
  "root_cause": null,
  "signature_valid": true,
  "trace_id": "p08-ground-timeout",
  "verdict": "VERIFIED",
  "verification_state": "verified"
}
```

### 7. tampered_persisted_receipt — pass

- **Expected:** modifying a receipt already persisted to disk makes signature validation fail
- **Pre-fix finding:** HMAC verification already rejected in-memory mutation, but no test exercised a receipt reloaded after persisted-trail tampering.
- **Post-fix observed:** {"modified_field": "verdict", "original_value": "VERIFIED", "signature_valid_after": false, "signature_valid_before": true, "tampered_value": "CONTRADICTED"}
- **Action executed:** `true`

```json
{
  "original": {
    "action": {
      "args": {
        "amount_paise": 849900,
        "currency": "INR",
        "doc_id": null,
        "item_category": "shirt",
        "item_colour": "grey",
        "order_id": "ORD-90233",
        "recipient_id": null
      },
      "compensability": "fully",
      "tool": "issue_refund"
    },
    "component_status": {},
    "evidence": [
      {
        "claim_id": "ORD-90233:order_belongs_to_customer",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT customer_id FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": "CUST-2291"
      },
      {
        "claim_id": "ORD-90233:amount_not_exceeding_order",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT amount_paise FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": 849900
      },
      {
        "claim_id": "ORD-90233:within_refund_window",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT delivered_at FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": "2026-08-11"
      },
      {
        "claim_id": "ORD-90233:amount_within_authority",
        "confidence": "certain",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "authority_ceiling_paise",
        "reliability_class": "corroborated",
        "source": "manifest:servicing",
        "value": 2500000
      },
      {
        "claim_id": "refund_window:policy_clause_current",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
        "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
        "reliability_class": "corroborated",
        "source": "policy_store.db",
        "value": "v4.2",
        "version": "v4.2"
      },
      {
        "claim_id": "refund_window:clause_semantics_match",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
        "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
        "reliability_class": "corroborated",
        "source": "policy_store.db",
        "value": "v4.2",
        "version": "v4.2"
      },
      {
        "claim_id": "ORD-90233:order_attributes_match",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT item_colour, item_category FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": {
          "category": "shirt",
          "colour": "grey"
        }
      }
    ],
    "failure_context": null,
    "idempotency_key": "7d3b9de6a5521442ab265063",
    "intervention": "ALLOW",
    "manifest_id": "servicing-v1",
    "reasons": [],
    "receipt_id": "78f9fd8a-4683-5dd4-8341-d979b5efeffd",
    "root_cause": null,
    "signature_valid": true,
    "trace_id": "p08-persisted-tamper",
    "verdict": "VERIFIED",
    "verification_state": "verified"
  },
  "tampered": {
    "action": {
      "args": {
        "amount_paise": 849900,
        "currency": "INR",
        "doc_id": null,
        "item_category": "shirt",
        "item_colour": "grey",
        "order_id": "ORD-90233",
        "recipient_id": null
      },
      "compensability": "fully",
      "tool": "issue_refund"
    },
    "component_status": {},
    "evidence": [
      {
        "claim_id": "ORD-90233:order_belongs_to_customer",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT customer_id FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": "CUST-2291"
      },
      {
        "claim_id": "ORD-90233:amount_not_exceeding_order",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT amount_paise FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": 849900
      },
      {
        "claim_id": "ORD-90233:within_refund_window",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT delivered_at FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": "2026-08-11"
      },
      {
        "claim_id": "ORD-90233:amount_within_authority",
        "confidence": "certain",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "authority_ceiling_paise",
        "reliability_class": "corroborated",
        "source": "manifest:servicing",
        "value": 2500000
      },
      {
        "claim_id": "refund_window:policy_clause_current",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
        "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
        "reliability_class": "corroborated",
        "source": "policy_store.db",
        "value": "v4.2",
        "version": "v4.2"
      },
      {
        "claim_id": "refund_window:clause_semantics_match",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "note": "Customers may request a full refund within 7 days of the delivery date. Requests made after 7 days may be eligible for store credit at the discretion of a supervisor. Refunds are issued to the original payment method within 5-7 business days of approval.",
        "query": "SELECT version, text FROM clauses WHERE policy_id = 'refund_window' AND effective_to IS NULL",
        "reliability_class": "corroborated",
        "source": "policy_store.db",
        "value": "v4.2",
        "version": "v4.2"
      },
      {
        "claim_id": "ORD-90233:order_attributes_match",
        "confidence": "high",
        "fetched_at": "2026-08-14T10:00:00+00:00",
        "freshness_ms": 0,
        "query": "SELECT item_colour, item_category FROM orders WHERE order_id = 'ORD-90233'",
        "reliability_class": "corroborated",
        "source": "orders.db",
        "value": {
          "category": "shirt",
          "colour": "grey"
        }
      }
    ],
    "failure_context": null,
    "idempotency_key": "7d3b9de6a5521442ab265063",
    "intervention": "ALLOW",
    "manifest_id": "servicing-v1",
    "reasons": [],
    "receipt_id": "78f9fd8a-4683-5dd4-8341-d979b5efeffd",
    "root_cause": null,
    "signature_valid": false,
    "trace_id": "p08-persisted-tamper",
    "verdict": "CONTRADICTED",
    "verification_state": "verified"
  }
}
```

### 8. retry_after_timeout — pass

- **Expected:** caller-visible timeout after committed execution; retry with same key replays the result and does not execute the action twice
- **Pre-fix finding:** The deterministic key was receipt metadata only; two dispatches with the same key invoked the tool twice.
- **Post-fix observed:** {"execution_count": 1, "first_result": {"executed": true, "sequence": 1}, "idempotency_key": "p08-caller-supplied-idempotency-key", "receipt_count": 3, "replay_component_status": {"reason": "completed_result_replayed", "status": "duplicate_suppressed"}, "retry_result": {"executed": true, "sequence": 1}, "timeout_boundary": "after execution committed, before caller retained response"}
- **Action executed:** `true`

```json
{
  "action": {
    "args": {
      "currency": "INR",
      "doc_id": "DOC-1042",
      "recipient_id": "EMP-4410"
    },
    "compensability": "partially",
    "tool": "send_document"
  },
  "component_status": {
    "execution": {
      "reason": "completed_result_replayed",
      "status": "duplicate_suppressed"
    }
  },
  "evidence": [
    {
      "claim_id": "DOC-1042:doc_classification_permitted",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "classification='internal'",
      "query": "SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = 'EMP-4410'",
      "reliability_class": "corroborated",
      "source": "entitlements.db",
      "value": true
    },
    {
      "claim_id": "DOC-1042:recipient_entitled_to_doc",
      "confidence": "high",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "about_customer_id=None",
      "query": "SELECT entitled_classifications, entitled_customer_ids FROM subjects WHERE subject_id = 'EMP-4410'",
      "reliability_class": "corroborated",
      "source": "entitlements.db",
      "value": true
    },
    {
      "claim_id": "DOC-1042:excerpt_contains_third_party_pii",
      "confidence": "moderate",
      "fetched_at": "2026-08-14T10:00:00+00:00",
      "freshness_ms": 0,
      "note": "no PII detected",
      "query": "detect(excerpt) via CP_PII=regex",
      "reliability_class": "inferred",
      "source": "pii:regex",
      "value": false
    }
  ],
  "failure_context": {
    "detail": "completed result returned without re-executing the action",
    "kind": "idempotent_replay",
    "posture_outcome": "replay",
    "stage": "execute"
  },
  "idempotency_key": "p08-caller-supplied-idempotency-key",
  "intervention": "ALLOW",
  "manifest_id": "knowledge_assistant-v1",
  "reasons": [],
  "receipt_id": "dbf6ccee-50af-5f90-a9d2-88696f710f65",
  "root_cause": null,
  "signature_valid": true,
  "trace_id": "p08-timeout-retry",
  "verdict": "VERIFIED",
  "verification_state": "verified"
}
```

## Isolation and determinism

- Runtime path: controlplane.intercept from classification through signed receipt; deterministic fixed actions hold extraction noise at zero and prevent fixture writes
- Isolation: SQLite backup clones plus temporary receipt/queue paths; globals restored in finally
- Scenario 2 precedence: active manifest tier fail_posture controls execution; compensability is reported metadata
- Windows note: SQLite clone connections are closed explicitly (`contextlib.closing`), not left to `sqlite3`'s transaction-only context manager, so `TemporaryDirectory` cleanup does not fail on a locked file.

See `docs/limitations.md` for what SOURCE-UNRELIABLE does and does not cover, and for the inherited-record-error reading of scenario 1.
