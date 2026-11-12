"""Suite-wide runtime isolation (D-M1-01, Part C / C-b).

Since D-M1-01 more paths ESCALATE (an `escalate` source-outage posture, and
knowledge_assistant's UNVERIFIABLE handling), and an ESCALATE writes to the
pending-action queue and reads the operational trail for the escalation
budget. Those engine functions bind their file paths as *default arguments*
at import time (controlplane/escalation.py, controlplane/telemetry.py), so
patching a module attribute alone does not redirect them. This fixture
redirects every such path for every test to the test's own tmp_path:

- module attributes: receipt.OPERATIONAL_TRAIL / PRIVILEGED_TRAIL,
  telemetry.OPERATIONAL_TRAIL, escalation.OPERATIONAL_TRAIL / PENDING_QUEUE,
  bench.reviewer_console.PENDING_QUEUE (if that module is loaded);
- bound defaults: escalation.{escalation_budget_exhausted,
  record_budget_exhaustion}.trail_path, escalation.{enqueue_pending,
  pending_items, record_review}.path, telemetry.latency_percentiles.path.

A test that needs a different location still monkeypatches over this; the
shared `monkeypatch` instance undoes everything at teardown. The session
guard below fails the run if any test created or changed the repo-root
trail or queue files. (Making the engine resolve these paths at call time
is a separate refactor, out of scope for D-M1-01.)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import controlplane.escalation as escalation_module
import controlplane.receipt as receipt_module
import controlplane.telemetry as telemetry_module

ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT_RUNTIME_FILES = (
    ROOT / "decisions.jsonl",
    ROOT / "decisions_privileged.jsonl",
    ROOT / "pending_actions.jsonl",
)


def _with_kwdefault(func, name: str, value: Path) -> dict:
    defaults = dict(func.__kwdefaults__ or {})
    assert name in defaults, f"{func.__qualname__} has no keyword-only default {name!r}"
    defaults[name] = value
    return defaults


@pytest.fixture(autouse=True)
def _isolate_runtime_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    trail = tmp_path / "decisions.jsonl"
    privileged = tmp_path / "decisions_privileged.jsonl"
    queue = tmp_path / "pending_actions.jsonl"

    monkeypatch.setattr(receipt_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(receipt_module, "PRIVILEGED_TRAIL", privileged)
    monkeypatch.setattr(telemetry_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(escalation_module, "OPERATIONAL_TRAIL", trail)
    monkeypatch.setattr(escalation_module, "PENDING_QUEUE", queue)

    for func, name, value in (
        (escalation_module.escalation_budget_exhausted, "trail_path", trail),
        (escalation_module.record_budget_exhaustion, "trail_path", trail),
        (escalation_module.enqueue_pending, "path", queue),
        (escalation_module.pending_items, "path", queue),
        (escalation_module.record_review, "path", queue),
    ):
        monkeypatch.setattr(func, "__kwdefaults__", _with_kwdefault(func, name, value))

    lp = telemetry_module.latency_percentiles
    monkeypatch.setattr(lp, "__defaults__", (trail,))

    console = sys.modules.get("bench.reviewer_console")
    if console is not None:
        monkeypatch.setattr(console, "PENDING_QUEUE", queue)

    return {"trail": trail, "privileged": privileged, "queue": queue}


def _snapshot() -> dict[Path, tuple[int, int] | None]:
    out = {}
    for p in _REPO_ROOT_RUNTIME_FILES:
        try:
            st = p.stat()
            out[p] = (st.st_size, st.st_mtime_ns)
        except FileNotFoundError:
            out[p] = None
    return out


@pytest.fixture(autouse=True, scope="session")
def _repo_root_runtime_files_untouched():
    before = _snapshot()
    yield
    after = _snapshot()
    changed = [str(p.name) for p in _REPO_ROOT_RUNTIME_FILES if before[p] != after[p]]
    assert not changed, f"a test created or modified repo-root runtime file(s): {changed}"
