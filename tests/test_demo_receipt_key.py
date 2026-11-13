"""P05b Y12: the dashboard (demo/web.py) has no fallback receipt key.

Without CP_RECEIPT_SECRET it refuses to start with a clear message; with a key
it starts. Each case runs in a fresh interpreter, because the check runs when
demo.web is imported (`python -m demo.web` and `uvicorn demo.web:app` both
import it).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MESSAGE = "CP_RECEIPT_SECRET is not set — run `make setup` (or make.ps1 setup) first"
START = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import demo.web as w; "
    "from fastapi.testclient import TestClient; "
    "r = TestClient(w.app).get('/'); "
    "print('started', r.status_code)"
)


def _start(env_key: str | None) -> subprocess.CompletedProcess:
    assert "CP_RECEIPT_SECRET" not in os.environ  # removed by monkeypatch in each test
    env = dict(os.environ)
    if env_key is not None:
        env["CP_RECEIPT_SECRET"] = env_key
    # -X utf8: the message contains an em dash; read it exactly on any console.
    return subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", START, str(ROOT)],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT)


def test_demo_refuses_to_start_without_a_receipt_key(monkeypatch):
    # The session may carry a key (CI, or tests/conftest.py's per-session one);
    # remove it for this test only.
    monkeypatch.delenv("CP_RECEIPT_SECRET", raising=False)
    # An empty value counts as "not set"; it also stops python-dotenv from
    # filling the variable from a developer's local .env.
    proc = _start("")
    assert proc.returncode != 0
    assert MESSAGE in proc.stderr
    assert "started" not in proc.stdout
    if not (ROOT / ".env").exists():
        unset = _start(None)
        assert unset.returncode != 0
        assert MESSAGE in unset.stderr


def test_demo_starts_with_a_receipt_key(monkeypatch):
    monkeypatch.delenv("CP_RECEIPT_SECRET", raising=False)
    proc = _start("test-key-not-for-production")
    assert proc.returncode == 0, proc.stderr
    assert "started 200" in proc.stdout
