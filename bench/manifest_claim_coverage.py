#!/usr/bin/env python3
"""P3-A — kind-level manifest claim-coverage.

    manifest_claim_coverage(tool) = bound required load-bearing kinds
                                    ──────────────────────────────────
                                    independently required load-bearing kinds

`required` comes from ``bench/extraction_reference.py`` — a hand-authored,
per-tool list of the load-bearing checks a correct verifier of that tool must
run, derived from the tool argument schema, the policy prose and
``docs/threat-model.md``, NEVER from the manifest's own ``claim_bindings``.
`bound` comes from the live manifest.

This is the INVERSE of ``controlplane.manifest._tool_contract_check``, which
asks "does every binding reference a real tool field?". This asks "is every
required check actually bound?".

WHAT THIS IS NOT
----------------
  * Not instance-level extraction recall / precision / decomposition accuracy.
    Those need an independent PER-ACTION reference claim corpus, which does
    not exist (``docs/extraction-reliability.md``). They are reported as
    NOT_MEASURED, never estimated.
  * Not a completeness proof. A tool at 100% here means only that the manifest
    binds every kind the reference lists — the reference is human-authored and
    bounded by its author's reading.
  * Not a risk-coverage curve.

Usage::

    python bench/manifest_claim_coverage.py           # JSON to stdout; exit 1 on a structural error
    python bench/manifest_claim_coverage.py --write    # also regenerate reports/manifest-claim-coverage.md

``--write`` regenerates ``reports/manifest-claim-coverage.md`` ONLY. It does
not touch ``reports/summary.json`` or any other artifact. Deterministic: no
model, no database, no network; same inputs, same output.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

import extraction_reference as ref  # noqa: E402  (bench/ is on sys.path; matches the repo's bench-module convention)
from controlplane.ladder import is_load_bearing  # noqa: E402
from controlplane.schema import ClaimKind  # noqa: E402

MANIFESTS_DIR = ROOT / "manifests"
REPORTS = ROOT / "reports"

NOT_MEASURED = {
    "instance_level_extraction_recall": "NOT_MEASURED — needs an independent per-action reference claim corpus",
    "instance_level_precision": "NOT_MEASURED — needs an independent per-action reference claim corpus",
    "decomposition_accuracy": "NOT_MEASURED — needs an independent per-action reference claim corpus",
    "silent_pass_rate": "NOT_MEASURED — a RATE needs the per-action corpus; the per-manifest unbound-load-bearing list is the kind-level signal",
}


class ReferenceError(RuntimeError):
    """The reference itself is malformed (bad ClaimKind, non-load-bearing
    required kind, missing tool entry). A structural failure, not a finding."""


def _validate_reference() -> list[str]:
    """The reference must name only real, load-bearing ClaimKinds, with a
    basis drawn from the controlled vocabulary. Returns [] or raises."""
    problems: list[str] = []
    for tool, kinds in ref.REQUIRED.items():
        for rk in kinds:
            try:
                kind = ClaimKind[rk.kind]
            except KeyError:
                problems.append(f"{tool}: {rk.kind!r} is not a ClaimKind")
                continue
            if not is_load_bearing(kind):
                problems.append(f"{tool}: {rk.kind} is not load-bearing (ladder._LOAD_BEARING) — cannot be 'required'")
            for token in rk.basis:
                if token not in ref.BASIS_VOCAB and not token.startswith("threat-model:T"):
                    problems.append(f"{tool}: {rk.kind} basis token {token!r} not in the controlled vocabulary")
    if problems:
        raise ReferenceError("; ".join(problems))
    return problems


def _read_manifest(path: Path) -> dict:
    """Plain YAML read of one manifest — enough for `tool` and the bound
    ClaimKind names, which is all this metric needs. Deliberately NOT
    ``controlplane.manifest.load_manifest``: that also resolves every
    binding's resolver against ``RESOLVER_BY_NAME``, which fails offline for
    the tau2 manifests (their ``tau2_retail`` resolver is registered only
    when ``bench/tau2_adapter`` is imported, under the P06 C2 runtime). Full
    manifest validation is ``controlplane.manifest.lint`` /
    ``tests/test_manifest_hardening.py``, not this file's job.

    Reading ``claim_bindings`` here is the "bound" side of the ratio — the
    thing being measured. The independence rule is on the *reference*
    (``bench/extraction_reference.py``), not on this metric.
    """
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _bound_kinds(manifest: dict) -> list[str]:
    """The ClaimKind *names* the manifest binds, in declared order."""
    return [b["claim_kind"] for b in (manifest.get("claim_bindings") or [])]


def _assess_tool(tool: str, manifest_name: str, manifest_id: str, bound: list[str]) -> dict:
    if tool not in ref.REQUIRED:
        raise ReferenceError(
            f"manifest {manifest_name!r} governs tool {tool!r}, which has no entry in "
            f"bench/extraction_reference.py. A governed tool cannot be silently "
            f"un-assessed — add an explicit reference entry."
        )

    required = list(ref.REQUIRED[tool])
    required_names = [rk.kind for rk in required]
    required_lb = [name for name in required_names if is_load_bearing(ClaimKind[name])]
    bound_set = set(bound)

    bound_required = [name for name in required_lb if name in bound_set]
    unbound_lb = [name for name in required_lb if name not in bound_set]

    note_by_kind = {rk.kind: rk.binding_note for rk in required if rk.binding_note}
    unbound_detail = [
        {"kind": name, "binding_note": note_by_kind.get(name)}
        for name in unbound_lb
    ]

    # bound kinds the reference does not list — split so a deliberate
    # non-load-bearing signal (e.g. PII detection) is not called "spurious".
    extra = [name for name in bound if name not in required_names]
    extra_lb, extra_non_lb = [], []
    for name in extra:
        try:
            (extra_lb if is_load_bearing(ClaimKind[name]) else extra_non_lb).append(name)
        except KeyError:
            extra_lb.append(name)  # unknown kind — surface it, don't hide it

    n = len(required_lb)
    if n == 0:
        status, coverage = "not_assessed", None
    else:
        status, coverage = "assessed", round(len(bound_required) / n, 6)

    return {
        "tool": tool,
        "manifest": manifest_name,
        "manifest_id": manifest_id,
        "status": status,
        "coverage": coverage,
        "required_load_bearing_kinds": required_lb,
        "bound_kinds": list(bound),
        "bound_required_kinds": bound_required,
        "unbound_load_bearing_kinds": unbound_lb,
        "unbound_load_bearing_detail": unbound_detail,
        "bound_not_in_reference_load_bearing": extra_lb,
        "bound_not_in_reference_non_load_bearing": extra_non_lb,
        "deliberately_not_required": [
            {"kind": k, "why": why} for k, why in ref.DELIBERATELY_NOT_REQUIRED.get(tool, ())
        ],
        "unrepresentable_required": [
            {"name": u.name, "rationale": u.rationale, "basis": list(u.basis)}
            for u in ref.UNREPRESENTABLE_REQUIRED.get(tool, ())
        ],
    }


def build_report() -> dict:
    _validate_reference()

    manifests = sorted(MANIFESTS_DIR.glob("*.yaml"))
    if not manifests:
        raise ReferenceError(f"no manifests found under {MANIFESTS_DIR}")

    tools_seen: dict[str, dict] = {}
    per_manifest: list[dict] = []
    for path in manifests:
        name = path.stem
        manifest = _read_manifest(path)
        tool = manifest.get("tool")
        if not tool:
            raise ReferenceError(f"manifests/{name}.yaml has no 'tool' key")
        row = _assess_tool(tool, name, manifest.get("manifest_id", name), _bound_kinds(manifest))
        per_manifest.append(row)
        # tau2 binds one tool per manifest; non-tau2 tools appear once. If two
        # manifests ever governed the same tool with different bindings, keep
        # the worst (smallest coverage) for the tool-level roll-up.
        prev = tools_seen.get(tool)
        if prev is None or (
            row["coverage"] is not None
            and (prev["coverage"] is None or row["coverage"] < prev["coverage"])
        ):
            tools_seen[tool] = row

    assessed = [r for r in per_manifest if r["status"] == "assessed"]
    not_assessed = [r for r in per_manifest if r["status"] == "not_assessed"]
    with_unbound = [r for r in per_manifest if r["unbound_load_bearing_kinds"]]

    fully_covered = sum(1 for r in assessed if r["coverage"] == 1.0)

    return {
        "task": "P3A_MANIFEST_CLAIM_COVERAGE_KIND_LEVEL",
        "reference_id": ref.REFERENCE_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "what_this_is": (
            "Kind-level check that each manifest binds every load-bearing ClaimKind an "
            "independently authored reference (bench/extraction_reference.py) says the "
            "governed tool requires. Deterministic; no model, DB or network."
        ),
        "metric": "bound_required_load_bearing_kinds / independently_required_load_bearing_kinds",
        "not_measured": NOT_MEASURED,
        "totals": {
            "manifests": len(per_manifest),
            "distinct_tools": len(tools_seen),
            "assessed": len(assessed),
            "not_assessed": len(not_assessed),
            "fully_covered_manifests": fully_covered,
            "manifests_with_unbound_load_bearing": len(with_unbound),
        },
        "manifests": per_manifest,
        "findings": _findings(per_manifest),
    }


def _findings(rows: list[dict]) -> list[dict]:
    """Grouped by (finding kind, binding note) so an identical omission across
    N manifests (the tau2 case) is one finding naming N manifests, not N
    copies of the same paragraph."""
    grouped: dict[tuple, dict] = {}
    for r in rows:
        for d in r["unbound_load_bearing_detail"]:
            key = ("unbound_required", d["kind"], d["binding_note"])
            grouped.setdefault(key, {
                "type": "unbound_required",
                "kind": d["kind"],
                "note": d["binding_note"],
                "manifests": [],
            })["manifests"].append(r["manifest"])
        for name in r["bound_not_in_reference_load_bearing"]:
            key = ("bound_not_in_reference", name, None)
            grouped.setdefault(key, {
                "type": "bound_not_in_reference",
                "kind": name,
                "note": "load-bearing kind bound by the manifest but absent from the reference "
                        "— reference gap or manifest over-bind; review",
                "manifests": [],
            })["manifests"].append(r["manifest"])
    return [grouped[k] for k in sorted(grouped)]


def write_markdown(report: dict) -> str:
    L = [
        "# P3-A — manifest claim-coverage (kind level)",
        "",
        "Harness: `bench/manifest_claim_coverage.py` (regenerate with "
        "`python bench/manifest_claim_coverage.py --write`). For each governed manifest it "
        "compares the ClaimKinds actually bound against the load-bearing kinds an "
        "independently authored reference — `bench/extraction_reference.py`, "
        f"`{report['reference_id']}` — says that tool requires. The reference is authored "
        "only from the tool argument schema, the policy prose and `docs/threat-model.md`; "
        "it imports nothing from `controlplane/` and reads no manifest "
        "(`tests/test_extraction_reference.py` enforces this).",
        "",
        "**Metric:** `bound required load-bearing kinds / independently required "
        "load-bearing kinds`. Zero required kinds ⇒ `not_assessed`, never `1.0`.",
        "",
        "**What this is NOT:** instance-level extraction recall, precision, decomposition "
        "accuracy, or a silent-pass *rate* — those need an independent per-action reference "
        "claim corpus, which does not exist. They are `NOT_MEASURED` here, not estimated. "
        "A manifest at 100% only binds every kind the reference lists; the reference itself "
        "is human-authored and bounded by its author's reading. See "
        "`docs/extraction-reliability.md`.",
        "",
        "| manifest | tool | status | coverage | bound / required (LB) | unbound load-bearing |",
        "|---|---|---|--:|--:|---|",
    ]
    for r in report["manifests"]:
        cov = "N/A" if r["coverage"] is None else f"{r['coverage'] * 100:.0f}%"
        nb, nr = len(r["bound_required_kinds"]), len(r["required_load_bearing_kinds"])
        unbound = ", ".join(r["unbound_load_bearing_kinds"]) or "—"
        L.append(
            f"| `{r['manifest']}` | `{r['tool']}` | {r['status']} | {cov} | "
            f"{nb} / {nr} | {unbound} |"
        )
    t = report["totals"]
    L += [
        "",
        f"{t['assessed']} of {t['manifests']} manifests assessed; "
        f"{t['fully_covered_manifests']} bind every required load-bearing kind; "
        f"{t['manifests_with_unbound_load_bearing']} have at least one unbound required "
        f"load-bearing kind.",
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        L.append("- (none)")
    for f in report["findings"]:
        manifests = ", ".join(f"`{m}`" for m in sorted(f["manifests"]))
        if f["type"] == "unbound_required":
            L.append(f"- required load-bearing kind **{f['kind']}** is NOT bound by {manifests}")
        else:
            L.append(f"- **{f['kind']}** bound by {manifests} but not in the reference")
        if f["note"]:
            L.append(f"  - {f['note']}")
    L += ["", "## Unrepresentable required checks (no ClaimKind — advisory, not in the ratio)", ""]
    unrep: dict[tuple[str, str], list[str]] = {}
    for r in report["manifests"]:
        for u in r["unrepresentable_required"]:
            unrep.setdefault((u["name"], u["rationale"]), []).append(r["tool"])
    for (name, rationale), tools in sorted(unrep.items()):
        scope = ", ".join(f"`{t}`" for t in sorted(tools))
        L.append(f"- **{name}** ({scope}): {rationale}")
    L += [
        "",
        "## Deliberately not required",
        "",
        "ClaimKinds a reader might expect but which the reference intentionally omits, "
        "with the reason — so an absence is seen to be a choice, not an oversight.",
        "",
    ]
    for r in report["manifests"]:
        for d in r["deliberately_not_required"]:
            L.append(f"- `{r['tool']}` — **{d['kind']}**: {d['why']}")
    L += [
        "",
        "## Not measured here",
        "",
    ]
    L += [f"- **{k}**: {v}" for k, v in report["not_measured"].items()]
    L += [
        "",
        "Relationship to P1: P1 `verification_coverage` = verified / eligible over the "
        "claims the manifest *did* model. This metric = bound / *required* — the half P1 "
        "does not measure. A manifest can score 100% on P1 verification coverage and still "
        "have unbound required kinds here; the two numbers are orthogonal and P3-A does "
        "not change P1's.",
        "",
    ]
    text = "\n".join(L) + "\n"
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "manifest-claim-coverage.md").write_text(text, encoding="utf-8", newline="\n")
    return text


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true", help="regenerate reports/manifest-claim-coverage.md")
    p.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = p.parse_args()

    try:
        report = build_report()
    except ReferenceError as e:
        print(json.dumps({"error": str(e), "task": "P3A_MANIFEST_CLAIM_COVERAGE_KIND_LEVEL"}, indent=2))
        raise SystemExit(1) from None

    print(json.dumps(report, indent=None if args.compact else 2, default=str))
    if args.write:
        write_markdown(report)
        print("\nwrote reports/manifest-claim-coverage.md", file=sys.stderr)


if __name__ == "__main__":
    main()
