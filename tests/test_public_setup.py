"""Release guards for the credential-free local setup path."""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent


def test_receipt_fixture_is_present_and_obviously_non_production():
    value = dotenv_values(ROOT / ".env.example").get("CP_RECEIPT_SECRET", "")
    assert value
    normalized = value.lower()
    assert "development" in normalized or "test" in normalized
    assert "not-for-production" in normalized


def test_generated_env_file_remains_gitignored():
    ignored_entries = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert ".env" in ignored_entries
