"""README Quick start and related public text stay accurate for a first-time user.

These checks guard fixes made in the P07a audit: a stranger following the
README must get a real clone URL, must not be sent to the paid `probe` step as
if it were required, must run the dashboard with the virtualenv's Python, and
must be told which steps use the network or a paid key. They also pin the
definition of n for the three CI count claims, the cold-start note for the
public demo, and the errata entry for the stale tau2 lines in reports/README.md.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _section(title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## )", README, flags=re.M | re.S)
    assert m, f"README section {title!r} not found"
    return m.group(1)


def _code_blocks(text: str) -> list[str]:
    return re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.S)


def test_quick_start_uses_the_real_clone_url():
    qs = _section("Quick start")
    assert "<repo-url>" not in README
    assert "git clone https://github.com/hariom-s27/controlplane.git" in qs


def test_paid_probe_is_not_in_the_step_lists_and_is_marked_paid():
    for title in ("Quick start", "Execution instructions"):
        for block in _code_blocks(_section(title)):
            assert "probe" not in block, f"{title}: probe must not be a listed step"
    row = next(l for l in _section("Quick start").splitlines() if l.startswith("| `probe`"))
    assert row.rstrip().endswith("| **yes** |"), row
    assert "Only `probe` and" in _section("Quick start")


def test_offline_table_covers_every_listed_step():
    qs = _section("Quick start")
    for step in ("`setup`", "`test`", "`negative`", "`demo`", "`demo2`", "`demo3`", "`judge-demo`", "dashboard"):
        assert re.search(rf"^\|[^\n]*{re.escape(step)}[^\n]*\|", qs, flags=re.M), step


def test_dashboard_is_started_with_the_virtualenv_python():
    for block in _code_blocks(README):
        for line in block.splitlines():
            assert not line.strip().startswith("python -m demo.web"), line
    assert ".\\.venv\\Scripts\\python -m demo.web" in README
    assert ".venv/bin/python -m demo.web" in README


def test_ci_badge_shows_push_runs_on_main():
    assert "actions/workflows/ci.yml/badge.svg?branch=main&event=push" in README.splitlines()[2]


def test_cold_start_note_cites_render_docs():
    live = _section("Live demo")
    assert "https://render.com/docs/free" in live
    assert "spins down after 15 minutes idle" in live


def test_product_smoke_bullet_mentions_the_cli_demos():
    assert "the use case 2 and 3 CLI\n  demos" in _section("Continuous integration")


N_DEFINITION = "n counts every pytest outcome reported (passed + failed + errors + skipped)"


def test_count_claims_define_n_and_readme_says_so():
    """The definition is words only, so it stays true when the quoted CI run is
    replaced; the numbers live only in the claims' value and n fields."""
    claims = yaml.safe_load((ROOT / "docs" / "claims.yaml").read_text(encoding="utf-8"))["claims"]
    counts = [c for c in claims if c["id"].startswith("ci-run-counts-")]
    assert len(counts) == 3
    for c in counts:
        gloss = c["definition"][c["definition"].index(N_DEFINITION):]
        assert "tests/test_ground.py" in gloss, c["id"]
        assert not re.search(r"\d", gloss.replace("tests/test_ground.py", "")), f"{c['id']}: numbers in the n definition"
        p, f, e, s = (int(x) for x in c["value"].split(" / "))
        assert c["n"] == p + f + e + s, c["id"]
    flat = " ".join(README.split())
    start = flat.index(N_DEFINITION)
    sentence = flat[start:flat.index(".", flat.index("without torch", start)) + 1]
    assert "the one skipped item is the whole module `tests/test_ground.py`" in sentence
    assert not re.search(r"\d", sentence.replace("tests/test_ground.py", "")), sentence


def test_errata_covers_the_stale_tau2_lines_in_reports_readme():
    errata = (ROOT / "docs" / "errata.md").read_text(encoding="utf-8")
    m = re.search(r"^### E6 .*?(?=^### |\Z)", errata, flags=re.M | re.S)
    assert m, "errata E6 missing"
    e6 = m.group(0)
    assert "`reports/README.md:17`" in e6 and "`reports/README.md:70-74`" in e6
    # newest first: E6 comes before E1
    assert errata.index("### E6") < errata.index("### E1")
