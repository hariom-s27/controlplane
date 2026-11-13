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

import json
import os
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


# --------------------------------------------------------------------------
# P05b: a random per-session receipt key when none is set. Product code has no
# fallback key (demo/web.py refuses to start without one), so a test session
# with CP_RECEIPT_SECRET unset gets a fresh random key for the session only.
# It is never printed, and it is removed again when the session ends. A key
# that is already set (CI, a developer's shell) is left untouched.
# --------------------------------------------------------------------------

_SESSION_KEY_SET_BY_CONFTEST = False


def pytest_configure(config):
    global _SESSION_KEY_SET_BY_CONFTEST
    if not os.environ.get("CP_RECEIPT_SECRET"):
        import secrets

        os.environ["CP_RECEIPT_SECRET"] = secrets.token_hex(32)
        _SESSION_KEY_SET_BY_CONFTEST = True


def pytest_unconfigure(config):
    global _SESSION_KEY_SET_BY_CONFTEST
    if _SESSION_KEY_SET_BY_CONFTEST:
        os.environ.pop("CP_RECEIPT_SECRET", None)
        _SESSION_KEY_SET_BY_CONFTEST = False


# --------------------------------------------------------------------------
# P05b Y21: opt-in CI counts hook. Active ONLY when CP_CI_COUNTS_FILE is set;
# otherwise it returns at once and writes nothing. It writes pytest's own
# counts, taken from the terminal reporter's stats (which include
# collection-level skips and errors), so CI can compare them with junit.xml.
# Category rules, chosen to agree with junit.xml by construction:
#   passed  = "passed" + "xpassed"     (junit counts an xpass as a pass),
#             minus tests whose call passed but whose teardown errored: junit
#             keeps one testcase for such a test and counts it as an error
#             (_pytest/junitxml.py, cnt_double_fail_tests)
#   failed  = "failed"                 (a failure in the test call)
#   errors  = "error"                  (setup/teardown errors, collection errors)
#   skipped = "skipped" + "xfailed"    (per-test and collection skips; junit
#                                       reports an xfail as skipped)
# --------------------------------------------------------------------------


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("CP_CI_COUNTS_FILE")
    if not path:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = reporter.stats if reporter is not None else {}

    def n(*keys):
        return sum(len(stats.get(k, [])) for k in keys)

    skipped_reports = stats.get("skipped", []) + stats.get("xfailed", [])
    teardown_errors = {r.nodeid for r in stats.get("error", []) if getattr(r, "when", None) == "teardown"}
    passed_then_teardown_error = sum(
        1 for r in stats.get("passed", []) + stats.get("xpassed", [])
        if getattr(r, "when", None) == "call" and r.nodeid in teardown_errors
    )
    counts = {
        "passed": n("passed", "xpassed") - passed_then_teardown_error,
        "failed": n("failed"),
        "errors": n("error"),
        "skipped": n("skipped", "xfailed"),
        "skipped_ids": sorted({getattr(r, "nodeid", "") for r in skipped_reports}),
        "source": "terminalreporter.stats",
        "pytest": pytest.__version__,
        "exitstatus": int(exitstatus),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(counts, f, indent=2, sort_keys=True)
        f.write("\n")
