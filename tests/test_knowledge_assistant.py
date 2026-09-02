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

import pytest

from controlplane import pii
from controlplane.errors import SourceUnavailable
from controlplane.idempotency import reset_execution_ledger
from controlplane.intercept import Blocked, REGISTRY, dispatch_tool
from controlplane.registry.clock import now
from controlplane.registry.entitlements import EntitlementsResolver
from controlplane.schema import Claim, ClaimKind, Intervention, ProposedAction, SessionContext, Verdict

_SESSION = SessionContext(trace_id="t-ka", subject_id="EMP-4410")

_DOC_2277_BODY = (
    "Customer Priya Raghavan (priya.raghavan@example.com, 14 Lotus Gardens, "
    "Bengaluru 560034) reported that order ORD-77301 was marked delivered "
    "on 2026-06-02 but never arrived. Refund of INR 18,499 approved by "
    "supervisor on 2026-06-09 under the delivery-exception clause."
)


@pytest.fixture
def entitlements_database(tmp_path, monkeypatch):
    """Build the committed entitlement seed outside the repository."""
    from data import build_db
    from controlplane.registry import entitlements

    monkeypatch.setattr(build_db, "DATA_DIR", tmp_path)
    build_db.build_entitlements()
    database = tmp_path / "entitlements.db"
    monkeypatch.setattr(entitlements, "DB", database)
    return database


@pytest.fixture(autouse=True)
def _clear_idempotency_ledger():
    reset_execution_ledger()
    yield
    reset_execution_ledger()


def _dispatch_send(monkeypatch, *, trace_id: str, session_subject: str, recipient_id: str, doc_id: str):
    args = {"recipient_id": recipient_id, "doc_id": doc_id, "excerpt": "requested excerpt"}
    action = ProposedAction(tool="send_document", **args)
    calls = []
    receipts = []
    monkeypatch.setenv("CP_MANIFEST", "knowledge_assistant")
    monkeypatch.setattr("controlplane.intercept.extract_action", lambda **_kwargs: action)
    monkeypatch.setattr(
        "controlplane.intercept.record",
        lambda decision, *_args: receipts.append(decision) or {"receipt": {}},
    )
    monkeypatch.setitem(REGISTRY, "send_document", lambda **kwargs: calls.append(kwargs) or {"status": "sent"})
    session = SessionContext(trace_id=trace_id, subject_id=session_subject)
    return args, session, calls, receipts


def test_pii_recogniser_detects_the_third_party_data():
    """Half 1: detection must actually work, or the demo proves nothing."""
    hits = pii.detect(_DOC_2277_BODY)
    entity_types = {h["entity_type"] for h in hits}
    assert "EMAIL" in entity_types
    assert "ORDER_ID" in entity_types
    assert len(hits) > 0


def test_entitlement_check_blocks_the_cross_tenant_record(entitlements_database):
    """Half 2: EMP-4410 is entitled to CUST-2291 only; DOC-2277 is about
    CUST-7788. The classification itself ("internal") is something EMP-4410
    may generally see — this must be permitted on its own — but the
    customer-specific check must independently fail."""
    classification_claim = Claim(
        id="DOC-2277:doc_classification_permitted",
        kind=ClaimKind.DOC_CLASSIFICATION_PERMITTED,
        subject="DOC-2277",
        asserted_value="EMP-4410",
    )
    classification_evidence = EntitlementsResolver().resolve(classification_claim, _SESSION)
    assert classification_evidence.value is True, "internal docs are within EMP-4410's general entitlement"

    entitlement_claim = Claim(
        id="DOC-2277:recipient_entitled_to_doc",
        kind=ClaimKind.RECIPIENT_ENTITLED_TO_DOC,
        subject="DOC-2277",
        asserted_value="EMP-4410",
    )
    entitlement_evidence = EntitlementsResolver().resolve(entitlement_claim, _SESSION)
    assert entitlement_evidence.value is False, "EMP-4410 is not entitled to CUST-7788's record"


def test_authorized_recipient_executes_normally(entitlements_database, monkeypatch):
    args, session, calls, receipts = _dispatch_send(
        monkeypatch,
        trace_id="t-authorized",
        session_subject="EMP-4410",
        recipient_id="EMP-4410",
        doc_id="DOC-1042",
    )

    assert dispatch_tool("send_document", args, session) == {"status": "sent"}
    assert calls == [args]
    assert receipts[0].verdict is Verdict.VERIFIED
    assert receipts[0].intervention is Intervention.ALLOW


def test_entitlement_is_checked_for_execution_recipient(entitlements_database, monkeypatch):
    """An entitled session subject must not authorize an unentitled recipient."""
    args, session, calls, receipts = _dispatch_send(
        monkeypatch,
        trace_id="t-recipient-mismatch",
        session_subject="EMP-2201",
        recipient_id="EMP-4410",
        doc_id="DOC-2277",
    )

    with pytest.raises(Blocked):
        dispatch_tool("send_document", args, session)

    assert calls == []
    assert receipts[0].verdict is Verdict.CONTRADICTED
    assert receipts[0].intervention is Intervention.BLOCK
    assert any(reason.rule == "recipient_entitled" for reason in receipts[0].reasons)


def test_existing_cross_tenant_dispatch_remains_blocked(entitlements_database, monkeypatch):
    args, session, calls, receipts = _dispatch_send(
        monkeypatch,
        trace_id="t-cross-tenant",
        session_subject="EMP-4410",
        recipient_id="EMP-4410",
        doc_id="DOC-2277",
    )

    with pytest.raises(Blocked):
        dispatch_tool("send_document", args, session)

    assert calls == []
    assert receipts[0].intervention is Intervention.BLOCK


def test_knowledge_source_outage_uses_configured_open_posture(monkeypatch):
    args, session, calls, receipts = _dispatch_send(
        monkeypatch,
        trace_id="t-source-outage",
        session_subject="EMP-4410",
        recipient_id="EMP-4410",
        doc_id="DOC-1042",
    )
    monkeypatch.setattr(
        "controlplane.intercept.resolve_bindings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SourceUnavailable(source="entitlements.db", operation="connect")
        ),
    )

    assert dispatch_tool("send_document", args, session) == {"status": "sent"}
    assert calls == [args]
    assert receipts[0].verdict is Verdict.UNVERIFIABLE
    assert receipts[0].intervention is Intervention.ALLOW
    assert receipts[0].root_cause == "authoritative_source_unavailable"


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
