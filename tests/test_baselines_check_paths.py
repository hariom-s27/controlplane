"""bench/baselines.py --check compares PATH_FIELDS with path separators
normalised (the committed reports were written on Windows; CI recomputes on
Linux). Every other field stays exact. No recompute here: the compare helpers
are pure functions over small dicts."""

from __future__ import annotations

from bench import baselines as B

WIN = "data\\fixtures\\b3"
POSIX = "data/fixtures/b3"


def _report(fixtures_dir: str, other: str = "x") -> dict:
    return {"config": {"b3": {"model": "m", "fixtures_dir": fixtures_dir}}, "other": other}


def test_path_field_is_the_b3_fixtures_dir_only():
    assert B.PATH_FIELDS == (("config", "b3", "fixtures_dir"),)


def test_backslash_and_slash_spellings_compare_equal():
    assert B._field_problems(_report(WIN), _report(POSIX)) == []
    assert B._field_problems(_report(POSIX), _report(WIN)) == []


def test_a_different_path_still_fails():
    assert B._field_problems(_report(WIN), _report("data/fixtures/b4")) == [
        "summary.json[p04_baselines].config.b3.fixtures_dir"]


def test_separator_difference_outside_path_fields_still_fails():
    assert B._field_problems(_report(WIN, other="a\\b"), _report(POSIX, other="a/b")) == [
        "summary.json[p04_baselines].other"]


def test_committed_spelling_is_adopted_for_the_byte_compare():
    committed, fresh = _report(WIN), _report(POSIX)
    B._adopt_committed_path_fields(fresh, committed)
    assert fresh["config"]["b3"]["fixtures_dir"] == WIN
    different = _report("data/fixtures/b4")
    B._adopt_committed_path_fields(different, committed)
    assert different["config"]["b3"]["fixtures_dir"] == "data/fixtures/b4"
