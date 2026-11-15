"""P07a G5: bench/fixtures/p05/README.md is written with LF only, and only when
its bytes differ, so a test run leaves a fresh clone's checkout unmodified
(the file is committed LF; .gitattributes: * text=auto eol=lf)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
DATA = ROOT / "data"
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def E(tmp_path, monkeypatch):
    for name in ("orders.db", "policy_store.db"):
        if not (DATA / name).exists():
            subprocess.run([sys.executable, str(DATA / "build_db.py")], check=True,
                           capture_output=True, cwd=ROOT)
    import evidence_ablation
    monkeypatch.setattr(evidence_ablation, "FIX", tmp_path)
    return evidence_ablation


def _clauses(E):
    return (E._live_clause("refund_window", current=True),
            E._live_clause("refund_window", current=False))


def test_readme_is_written_with_lf_only(E, tmp_path):
    E._write_fixture_readme(*_clauses(E))
    raw = (tmp_path / "README.md").read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_readme_is_not_rewritten_when_bytes_match(E, tmp_path, monkeypatch):
    E._write_fixture_readme(*_clauses(E))
    before = (tmp_path / "README.md").read_bytes()

    def no_write(*_a, **_k):
        raise AssertionError("README.md was rewritten although its bytes already matched")
    monkeypatch.setattr(E, "open", no_write, raising=False)  # shadows the builtin inside the module
    E._write_fixture_readme(*_clauses(E))
    assert (tmp_path / "README.md").read_bytes() == before


def test_a_crlf_copy_is_rewritten_as_lf(E, tmp_path):
    E._write_fixture_readme(*_clauses(E))
    lf = (tmp_path / "README.md").read_bytes()
    (tmp_path / "README.md").write_bytes(lf.replace(b"\n", b"\r\n"))
    E._write_fixture_readme(*_clauses(E))
    assert (tmp_path / "README.md").read_bytes() == lf


def test_generated_readme_equals_the_committed_file(E, tmp_path):
    """So regenerating it in a clean checkout changes no byte."""
    E._write_fixture_readme(*_clauses(E))
    committed = (BENCH / "fixtures" / "p05" / "README.md").read_bytes().replace(b"\r\n", b"\n")
    assert (tmp_path / "README.md").read_bytes() == committed
