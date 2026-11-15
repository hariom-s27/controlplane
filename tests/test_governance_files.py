"""docs/governance/ holds copies of the repository's GitHub rulesets.

ruleset-main.json must stay byte-identical to the JSON submitted to create the
`main` ruleset (so its sha256 is pinned here); ruleset-tags.json is applied
as ruleset 27320545, and the folder's README must say so. GitHub
enforces rulesets, not these files; the tests only keep the copies honest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOV = ROOT / "docs" / "governance"
MAIN_SHA256 = "4d5944998e7ba3df8aefb5a0a380efcf00254912f1badfc9d3711b756a86df25"


def test_main_ruleset_is_the_submitted_body_byte_for_byte():
    raw = (GOV / "ruleset-main.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MAIN_SHA256
    rs = json.loads(raw)
    assert rs["target"] == "branch" and rs["enforcement"] == "active"
    assert rs["bypass_actors"] == []
    assert rs["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    types = {r["type"] for r in rs["rules"]}
    assert types == {"deletion", "non_fast_forward", "required_status_checks"}
    checks = next(r for r in rs["rules"] if r["type"] == "required_status_checks")["parameters"]["required_status_checks"]
    assert checks == [{"context": "ci-ok", "integration_id": 15368}]


def test_tag_ruleset_draft_protects_release_tags_from_update_and_deletion():
    rs = json.loads((GOV / "ruleset-tags.json").read_text(encoding="utf-8"))
    assert rs["target"] == "tag"
    assert rs["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]
    assert [r["type"] for r in rs["rules"]] == ["update", "deletion"]
    assert rs["bypass_actors"] == []


def test_readme_marks_the_tag_ruleset_as_applied():
    text = (GOV / "README.md").read_text(encoding="utf-8")
    assert "**applied** (ruleset 27320545)" in text
    assert "not yet applied" not in text
    assert MAIN_SHA256 in text
    flat = " ".join(text.split())
    assert "the request body used to create ruleset 27251565 on 14 nov 2026" in flat.lower()
    assert "exported" not in flat.lower()
