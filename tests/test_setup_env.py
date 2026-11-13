"""P05b Y12: `make setup` / `.\\make.ps1 setup` write a local receipt key.

Both task runners carry the same Python snippet. It creates .env from
.env.example with a new random CP_RECEIPT_SECRET only if .env does not exist,
never changes an existing .env, and never prints the key. These tests extract
the snippet from both files and run it in a temporary directory.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
KEY = "CP_RECEIPT_SECRET"


def _makefile_code() -> str:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    m = re.search(r"^\t@\$\(PY\) -c '([^']*)'$", text, flags=re.M)
    assert m, "Makefile setup snippet not found"
    return m.group(1)


def _ps1_code() -> str:
    text = (ROOT / "make.ps1").read_text(encoding="utf-8")
    m = re.search(r"^\s*\$EnvCode = '([^']*)'\s*$", text, flags=re.M)
    assert m, "make.ps1 setup snippet not found"
    assert re.search(r"^\s*\$EnvCode \| & \$Py -\s*$", text, flags=re.M), "make.ps1 must pipe the snippet to Python"
    return m.group(1)


def _run(code: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-c", code], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_both_task_runners_carry_the_same_snippet_and_no_plain_copy():
    assert _makefile_code() == _ps1_code()
    assert "cp .env.example .env" not in (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "Copy-Item .env.example .env" not in (ROOT / "make.ps1").read_text(encoding="utf-8")


def test_env_example_holds_a_placeholder_not_a_key():
    value = dotenv_values(ROOT / ".env.example")[KEY]
    assert "placeholder" in value
    assert not re.fullmatch(r"[0-9a-f]{64}", value)


def test_setup_creates_env_with_a_random_key_and_never_prints_it(tmp_path):
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.example")
    keys = []
    for run in range(2):  # two fresh directories: two different keys
        d = tmp_path / f"fresh{run}"
        d.mkdir()
        shutil.copy(ROOT / ".env.example", d / ".env.example")
        proc = _run(_makefile_code(), d)
        assert proc.returncode == 0, proc.stderr
        env = dotenv_values(d / ".env")
        key = env[KEY]
        assert re.fullmatch(r"[0-9a-f]{64}", key)
        assert key not in proc.stdout and key not in proc.stderr
        example = dotenv_values(d / ".env.example")
        assert {k: v for k, v in env.items() if k != KEY} == {k: v for k, v in example.items() if k != KEY}
        keys.append(key)
    assert keys[0] != keys[1]


def test_setup_never_overwrites_an_existing_env(tmp_path):
    shutil.copy(ROOT / ".env.example", tmp_path / ".env.example")
    first = _run(_makefile_code(), tmp_path)
    assert first.returncode == 0, first.stderr
    before = (tmp_path / ".env").read_bytes()
    for code in (_makefile_code(), _ps1_code()):
        again = _run(code, tmp_path)
        assert again.returncode == 0, again.stderr
        assert (tmp_path / ".env").read_bytes() == before
        assert "Kept the existing .env" in again.stdout

    custom = tmp_path / "custom"
    custom.mkdir()
    shutil.copy(ROOT / ".env.example", custom / ".env.example")
    (custom / ".env").write_bytes(b"FEATHERLESS_API_KEY=\nCP_RECEIPT_SECRET=my-own-value\n")
    proc = _run(_makefile_code(), custom)
    assert proc.returncode == 0, proc.stderr
    assert (custom / ".env").read_bytes() == b"FEATHERLESS_API_KEY=\nCP_RECEIPT_SECRET=my-own-value\n"
    assert "my-own-value" not in proc.stdout
