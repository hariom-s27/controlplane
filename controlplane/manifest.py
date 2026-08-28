"""The minimal slice of S12 (policy manifests) that S7's predicate graph
needs today: window_days and the per-role authority ceiling. Full S12 is
"same engine, different behaviour" per use case — CP_MANIFEST already
selects servicing vs knowledge_assistant in .env, and this loader is where
that gets read once the second manifest exists. Not the whole manifest
system, just enough of it to stop being a TODO comment inside a predicate.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = ROOT / "manifests"


def load_manifest(name: str) -> dict:
    path = MANIFESTS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["_name"] = name
    return data


__all__ = ["load_manifest"]
