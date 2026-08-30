"""S13 checkpoint — the cross-tenant test, against the real seeded data
(data/seed/entitlements.json already documents this exact scenario):
EMP-4410 is entitled to CUST-2291's records, not CUST-7788's. DOC-2277 is
about CUST-7788 and its body contains real, well-formed PII (a name, an
email, an address, an order id).

Both halves matter, per the roadmap's own words: the PII pass proves
detection works at all; the entitlement block proves detection alone
would have waved this through.
"""

from __future__ import annotations

from controlplane import pii
from controlplane.registry.clock import now
from controlplane.registry.entitlements import EntitlementsResolver
from controlplane.schema import Claim, ClaimKind, SessionContext

_SESSION = SessionContext(trace_id="t-ka", subject_id="EMP-4410")

_DOC_2277_BODY = (
    "Customer Priya Raghavan (priya.raghavan@example.com, 14 Lotus Gardens, "
    "Bengaluru 560034) reported that order ORD-77301 was marked delivered "
    "on 2026-06-02 but never arrived. Refund of INR 18,499 approved by "
    "supervisor on 2026-06-09 under the delivery-exception clause."
)


def test_pii_recogniser_detects_the_third_party_data():
    """Half 1: detection must actually work, or the demo proves nothing."""
    hits = pii.detect(_DOC_2277_BODY)
    entity_types = {h["entity_type"] for h in hits}
    assert "EMAIL" in entity_types
    assert "ORDER_ID" in entity_types
    assert len(hits) > 0


def test_entitlement_check_blocks_the_cross_tenant_record():
    """Half 2: EMP-4410 is entitled to CUST-2291 only; DOC-2277 is about
    CUST-7788. The classification itself ("internal") is something EMP-4410
    may generally see — this must be permitted on its own — but the
    customer-specific check must independently fail."""
    classification_claim = Claim(
        id="DOC-2277:doc_classification_permitted", kind=ClaimKind.DOC_CLASSIFICATION_PERMITTED, subject="DOC-2277"
    )
    classification_evidence = EntitlementsResolver().resolve(classification_claim, _SESSION)
    assert classification_evidence.value is True, "internal docs are within EMP-4410's general entitlement"

    entitlement_claim = Claim(
        id="DOC-2277:recipient_entitled_to_doc", kind=ClaimKind.RECIPIENT_ENTITLED_TO_DOC, subject="DOC-2277"
    )
    entitlement_evidence = EntitlementsResolver().resolve(entitlement_claim, _SESSION)
    assert entitlement_evidence.value is False, "EMP-4410 is not entitled to CUST-7788's record"


def test_full_gate_blocks_the_cross_tenant_send():
    """End to end through decide(): classification permitted, PII present
    and detected, but not load-bearing — only the entitlement failure
    should drive BLOCK."""
    from controlplane.decide import decide
    from controlplane.ladder import classify_claims
    from controlplane.schema import Confidence, Evidence, Intervention, ProposedAction, Reliability, Verdict

    action = ProposedAction(
        tool="send_document", recipient_id="EMP-4410", doc_id="DOC-2277", excerpt=_DOC_2277_BODY
    )
    class_claim = Claim(id="DOC-2277:c", kind=ClaimKind.DOC_CLASSIFICATION_PERMITTED, subject="DOC-2277", asserted_value="EMP-4410")
    entitled_claim = Claim(id="DOC-2277:e", kind=ClaimKind.RECIPIENT_ENTITLED_TO_DOC, subject="DOC-2277", asserted_value="EMP-4410")
    pii_claim = Claim(id="DOC-2277:p", kind=ClaimKind.EXCERPT_CONTAINS_THIRD_PARTY_PII, subject="DOC-2277")
    claims = classify_claims([class_claim, entitled_claim, pii_claim])

    evidence = [
        Evidence(claim_id="DOC-2277:c", value=True, source="entitlements.db", query="...", fetched_at=now(),
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="DOC-2277:e", value=False, source="entitlements.db", query="...", fetched_at=now(),
                  reliability_class=Reliability.CORROBORATED, confidence=Confidence.HIGH),
        Evidence(claim_id="DOC-2277:p", value=True, source="pii:regex", query="...", fetched_at=now(),
                  reliability_class=Reliability.INFERRED, confidence=Confidence.MODERATE, note="PII found"),
    ]
    manifest = {
        "reliability_floor": "unverified", "manifest_id": "knowledge_assistant-v1", "_name": "knowledge_assistant",
        "compensation": {"action": "revoke_access", "compensability": "partially"},
    }
    predicate_result = {"classification_permitted": True, "recipient_entitled": False}

    decision = decide(
        trace_id="t1", manifest_id=manifest["manifest_id"], action=action, claims=claims, evidence=evidence,
        predicate_result=predicate_result, manifest=manifest,
    )
    assert decision.verdict == Verdict.CONTRADICTED
    assert decision.intervention == Intervention.BLOCK
    assert any(r.rule == "recipient_entitled" for r in decision.reasons)
    assert not any(r.rule == "classification_permitted" for r in decision.reasons)  # it passed, no reason logged
