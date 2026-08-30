"""S12 — declarative evidence binding. Replaces the per-use-case
``_EVIDENCE_BUILDERS`` dispatch that used to live in intercept.py.

A binding (one per checked claim, in manifests/<name>.yaml) carries only
what varies per use case: ``claim_kind`` (a ClaimKind), ``resolver`` (a name
in registry.RESOLVER_BY_NAME), ``subject`` (a reference for claim.subject),
and ``predicate_key`` — where the resolved value lands in the payload:
a dotted string, a ``{sub: path}`` map, or null (fed to decide()/grounding/
pii, not the graph). ``tier`` stays in ladder.py and ``reliability_class``
in the resolver; a raw ``query`` stays out entirely (injection surface).
See docs/policy-manifest.md for the full schema and the rationale.
"""

from __future__ import annotations

from typing import Any

from controlplane.schema import ClaimKind, ProposedAction, SessionContext

# Reference roots a binding may read from. `action.*` is restricted to the
# structural fields (facts_for_predicate) — never a claimed_* value.
_REF_ROOTS = ("action", "manifest", "session", "clock")
_STRUCTURAL_FIELDS = frozenset(ProposedAction(tool="_").facts_for_predicate())


class ManifestBindingError(ValueError):
    """Raised at manifest load time for any malformed binding."""


def validate_ref(ref: str, *, where: str) -> None:
    """A reference is ``root.path`` where root is one of _REF_ROOTS. An
    ``action.claimed_*`` reference is rejected here, at load time, per the
    architecture's one rule: no claimed_* value crosses into a predicate."""
    if not isinstance(ref, str) or "." not in ref:
        raise ManifestBindingError(f"{where}: reference {ref!r} must look like 'action.order_id'")
    root, _, path = ref.partition(".")
    if root not in _REF_ROOTS:
        raise ManifestBindingError(f"{where}: reference root {root!r} not in {_REF_ROOTS}")
    if root == "action" and path.startswith("claimed_"):
        raise ManifestBindingError(
            f"{where}: reference {ref!r} reads a claimed_* field. The extractor produces "
            "CLAIMS, the registry produces FACTS — they never come from the same place."
        )
    if root == "action" and path not in _STRUCTURAL_FIELDS:
        raise ManifestBindingError(
            f"{where}: action.{path} is not a structural field (facts_for_predicate); "
            "only structural tool-call fields may reach a predicate"
        )


def resolve_ref(ref: str, *, action: ProposedAction | None = None,
                session: SessionContext | None = None, manifest: dict | None = None) -> Any:
    """Evaluate a validated reference to a concrete value."""
    root, _, path = ref.partition(".")
    if root == "action":
        return action.facts_for_predicate().get(path) if action is not None else None
    if root == "session":
        return getattr(session, path, None) if session is not None else None
    if root == "manifest":
        return (manifest or {}).get(path)
    if root == "clock":
        from controlplane.registry.clock import today

        if path == "today":
            return today().isoformat()
        raise ManifestBindingError(f"clock.{path} is not a thing; only clock.today")
    raise ManifestBindingError(f"reference root {root!r} not in {_REF_ROOTS}")


def _set_path(payload: dict, dotted: str, value: Any) -> None:
    *parents, leaf = dotted.split(".")
    node = payload
    for p in parents:
        node = node.setdefault(p, {})
    node[leaf] = value


def claim_specs(manifest: dict) -> list[dict]:
    """The manifest's claim_bindings, with claim_kind coerced to the enum."""
    out = []
    for b in manifest.get("claim_bindings", []):
        out.append({**b, "claim_kind": ClaimKind[b["claim_kind"]]})
    return out


def build_predicate_payload(manifest: dict, resolved: list, *,
                            action: ProposedAction, session: SessionContext) -> dict:
    """Assemble the dict the Zen graph reads as ``evidence.*``.

    Generic: the shape comes entirely from the manifest — the static
    ``predicate_payload`` scaffolding plus one entry per binding that has a
    ``predicate_key``. This is what used to be a hand-written function per
    use case in intercept.py.
    """
    payload: dict[str, Any] = {}
    for dotted, ref in (manifest.get("predicate_payload") or {}).items():
        _set_path(payload, dotted, resolve_ref(ref, action=action, session=session, manifest=manifest))

    evidence_by_kind = {claim.kind: ev for claim, ev in resolved}
    for spec in claim_specs(manifest):
        key = spec.get("predicate_key")
        if key is None:
            continue
        ev = evidence_by_kind.get(spec["claim_kind"])
        if ev is None:
            continue
        if isinstance(key, dict):
            src = ev.value or {}
            for sub, dotted in key.items():
                _set_path(payload, dotted, src.get(sub))
        else:
            _set_path(payload, key, ev.value)
    return payload


__all__ = [
    "ManifestBindingError",
    "validate_ref",
    "resolve_ref",
    "claim_specs",
    "build_predicate_payload",
]
