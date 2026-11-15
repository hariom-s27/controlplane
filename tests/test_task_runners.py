"""Static checks of the two task runners, make.ps1 and Makefile (audit labels
P07a Q6/Q7/G7).

The tests read the runner files as text; no shell is started. They check that
every native command in make.ps1 goes through Invoke-Native, so a failing step
stops the run with that step's exit code instead of carrying on and looking
like success (exp5 is the one step allowed to fail); that the console encoding
is put back afterwards; and that the help texts are accurate (the paid probe
step is not presented as a first step, setup is followed by test). Live
behaviour is not exercised here; run the tasks in a fresh clone to see it.
These tests keep the texts and the failure handling from drifting back.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PS1 = (ROOT / "make.ps1").read_text(encoding="utf-8")
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")


def _invoke_native_body() -> str:
    m = re.search(r"^function Invoke-Native \{\n(.*?)^\}\n", PS1, flags=re.M | re.S)
    assert m, "make.ps1 must define Invoke-Native"
    return m.group(1)


def _lines_inside_invoke_native_blocks() -> set[int]:
    """Line numbers (1-based) inside an `Invoke-Native ... {` block, by brace depth."""
    inside: set[int] = set()
    depth = 0  # >0 while inside an Invoke-Native block
    for no, line in enumerate(PS1.splitlines(), 1):
        code = line.split("#", 1)[0] if not line.lstrip().startswith("$EnvCode =") else ""
        if depth == 0:
            m = re.search(r"Invoke-Native(?: -AllowFailure)? \{", code)
            if m:
                inside.add(no)
                tail = code[m.end():]
                depth = 1 + tail.count("{") - tail.count("}")
            continue
        inside.add(no)
        depth += code.count("{") - code.count("}")
    return inside


def test_help_texts_say_eight_scenario_and_no_probe_first():
    for name, text in (("make.ps1", PS1), ("Makefile", MAKEFILE)):
        assert "six-scenario" not in text, name
        assert "eight-scenario" in text, name
        assert "do this first" not in text, name
        assert re.search(r"probe .*paid key", text), f"{name}: probe help must say it needs a paid key"


def test_setup_next_step_is_test_not_probe():
    assert "Setup complete. Next:  .\\make.ps1 test" in PS1
    assert "Setup complete. Next: make test" in MAKEFILE
    assert "Next:  .\\make.ps1 probe" not in PS1
    assert "Next: make probe" not in MAKEFILE


def test_every_native_call_in_make_ps1_goes_through_invoke_native():
    inside = _lines_inside_invoke_native_blocks()
    native = re.compile(r"& \$Py\b|\bpython -m venv\b|\$EnvCode \| & \$Py -")
    offenders = [
        f"{no}: {line.strip()}" for no, line in enumerate(PS1.splitlines(), 1)
        if native.search(line.split("#", 1)[0]) and no not in inside
    ]
    assert not offenders, "native call outside Invoke-Native:\n" + "\n".join(offenders)


def test_continue_preference_only_inside_the_helper_and_exit_code_propagates():
    body = _invoke_native_body()
    assert '$ErrorActionPreference = "Continue"' in body
    assert PS1.count('$ErrorActionPreference = "Continue"') == 1
    assert '$ErrorActionPreference = "Stop"' in PS1
    assert "exit $code" in body
    assert "make.ps1: $Task failed (exit $code)" in body
    # the choice depends on redirection and the PowerShell version, never on the task
    assert "[Console]::IsErrorRedirected" in body
    assert "$Task" not in body.replace("make.ps1: $Task failed (exit $code)", "")


def test_exp5_is_the_only_tolerated_failure():
    assert PS1.count("-AllowFailure {") == 1
    line = next(l for l in PS1.splitlines() if "-AllowFailure {" in l)
    assert "seb1_exp5_confusion_matrix.py" in line
    assert not re.search(r"try \{ & \$Py bench\\seb1_exp5", PS1), "the old try/catch around exp5 must be gone"
    assert "-$(PY) bench/seb1_exp5_confusion_matrix.py" in MAKEFILE


def test_console_encoding_is_restored():
    assert "$SavedConsoleEncoding = [Console]::OutputEncoding" in PS1
    tail = PS1[PS1.rindex("} finally {"):]
    assert "[Console]::OutputEncoding = $SavedConsoleEncoding" in tail
    assert "PYTHONIOENCODING" in tail


def test_makefile_ci_help_matches_its_recipe():
    assert re.search(r"^ci:\s*; \$\(PY\) -m pytest tests -q$", MAKEFILE, flags=re.M)
    assert '@echo "  ci        test suite, quiet output (pytest -q)"' in MAKEFILE
