"""D-M1-02 — policy snapshot: the manifest is validated once per content change.

Test 1, 4a and 4b pin the new behaviour (heavy work once per content, one
rebuild under a lock) and fail on the pre-snapshot loader. Tests 2, 3 and 4c
guard the cache: they pass on both the old and the new loader, because they
only describe what callers could already rely on.

Every test works on a private copy of manifests/ under tmp_path, so no shipped
file is touched. Cache state is reset with raising=False so this file also runs
against the old module, which has no cache attributes.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import threading
import time

import jsonschema
import pytest
import yaml

import controlplane.manifest as cm
from controlplane.bindings import ManifestBindingError

NAME = "servicing"


@pytest.fixture
def mdir(tmp_path, monkeypatch):
    d = tmp_path / "manifests"
    shutil.copytree(cm.MANIFESTS_DIR / "graphs", d / "graphs")
    shutil.copy(cm.MANIFESTS_DIR / f"{NAME}.yaml", d / f"{NAME}.yaml")
    monkeypatch.setattr(cm, "MANIFESTS_DIR", d)
    monkeypatch.setattr(cm, "_SNAPSHOTS", {}, raising=False)
    monkeypatch.setattr(cm, "_schema_validator", None, raising=False)
    return d


def _text(mdir) -> str:
    return (mdir / f"{NAME}.yaml").read_text(encoding="utf-8")


def _write(mdir, text: str) -> None:
    (mdir / f"{NAME}.yaml").write_text(text, encoding="utf-8")


def _expected(text: str) -> dict:
    data = yaml.safe_load(text)
    data["_name"] = NAME
    return data


def _with_window(text: str, days: int) -> str:
    out = text.replace("window_days: 7 ", f"window_days: {days} ", 1)
    assert out != text or days == 7
    return out


# ---------------------------------------------------------------- test 1


def test_1_heavy_work_runs_once_per_content_change(mdir, monkeypatch):
    schema_checks: list[int] = []
    yaml_loads: list[int] = []

    cls = jsonschema.validators.validator_for(cm._json_schema())
    orig_check = cls.check_schema
    monkeypatch.setattr(
        cls, "check_schema",
        classmethod(lambda c, schema, *a, **k: (schema_checks.append(1), orig_check(schema, *a, **k))[1]),
    )
    orig_load = yaml.safe_load
    monkeypatch.setattr(cm.yaml, "safe_load", lambda s: (yaml_loads.append(1), orig_load(s))[1])

    for _ in range(50):
        assert cm.load_manifest(NAME)["window_days"] == 7
    assert len(schema_checks) == 1, f"metaschema check ran {len(schema_checks)} times for 50 calls"
    assert len(yaml_loads) == 1, f"YAML parsed {len(yaml_loads)} times for 50 calls"

    _write(mdir, _with_window(_text(mdir), 9))  # a content change is picked up on the next call
    for _ in range(5):
        assert cm.load_manifest(NAME)["window_days"] == 9
    assert len(yaml_loads) == 2
    assert len(schema_checks) == 1  # same schema object: never re-checked


# ---------------------------------------------------------------- test 2


def _broken(mdir, kind: str, base: str):
    """Apply one broken state; return (exception type, exact message or None)."""
    path = mdir / f"{NAME}.yaml"
    if kind == "missing":
        path.unlink()
        return FileNotFoundError, None
    if kind == "bad_yaml":
        text = base + "\nbroken: [unclosed, list\n"
        _write(mdir, text)
        with pytest.raises(yaml.YAMLError) as ref:
            yaml.safe_load(text)
        return type(ref.value), str(ref.value)
    if kind == "schema_invalid":
        _write(mdir, base.replace("window_days: 7 ", 'window_days: "seven" ', 1))
        return ManifestBindingError, (
            f"manifests/{NAME}.yaml: structural schema violation at window_days: "
            "'seven' is not of type 'integer', 'null'"
        )
    if kind == "semantic_invalid":
        _write(mdir, base.replace("predicate_graph: graphs/servicing.json",
                                  "predicate_graph: graphs/does_not_exist.json", 1))
        return ManifestBindingError, (
            f"manifests/{NAME}.yaml: predicate_graph 'graphs/does_not_exist.json' not found under manifests/"
        )
    if kind == "empty":
        _write(mdir, "")
        return TypeError, None
    if kind == "graph_removed":  # YAML unchanged; something it depends on is gone
        (mdir / "graphs" / "servicing.json").rename(mdir / "graphs" / "servicing.json.off")
        return ManifestBindingError, (
            f"manifests/{NAME}.yaml: predicate_graph 'graphs/servicing.json' not found under manifests/"
        )
    raise AssertionError(kind)


def _restore(mdir, kind: str, base: str) -> None:
    if kind == "graph_removed":
        (mdir / "graphs" / "servicing.json.off").rename(mdir / "graphs" / "servicing.json")
    _write(mdir, base)


@pytest.mark.parametrize(
    "kind", ["missing", "bad_yaml", "schema_invalid", "semantic_invalid", "empty", "graph_removed"]
)
def test_2_invalid_content_raises_as_today_and_leaves_no_stale_snapshot(mdir, kind):
    base = _text(mdir)
    assert cm.load_manifest(NAME) == _expected(base)  # a good snapshot exists first

    exc_type, message = _broken(mdir, kind, base)
    for _ in range(2):  # the same failure every call: never served from the old snapshot
        with pytest.raises(exc_type) as got:
            cm.load_manifest(NAME)
        assert type(got.value) is exc_type
        if message is not None:
            assert str(got.value) == message

    _restore(mdir, kind, base)
    assert cm.load_manifest(NAME) == _expected(base)


# ---------------------------------------------------------------- test 3


def test_3_each_caller_gets_its_own_copy(mdir):
    base = _text(mdir)
    a = cm.load_manifest(NAME)
    b = cm.load_manifest(NAME)
    assert a is not b and a["claim_bindings"] is not b["claim_bindings"]

    a["window_days"] = 999
    a["claim_bindings"][0]["resolver"] = "tampered"
    a["claim_bindings"].append({"claim_kind": "x"})
    a.pop("tool")
    b["fail_posture"]["tier_2"] = "tampered"

    assert cm.load_manifest(NAME) == _expected(base)


# ---------------------------------------------------------------- test 4 (a, b, c)

_WAIT_S = 10.0


def _ab(mdir):
    text_a = _text(mdir)
    text_b = _with_window(text_a, 9).replace("manifest_id: servicing-v1", "manifest_id: servicing-vB", 1)
    assert text_b != text_a
    return text_a, text_b


def _swap_file(mdir, text: str) -> None:
    """Atomic replace while readers are idle; retry a transient Windows PermissionError."""
    target = mdir / f"{NAME}.yaml"
    tmp = mdir / f".{NAME}.swap.tmp"
    tmp.write_text(text, encoding="utf-8")
    deadline = time.monotonic() + _WAIT_S
    while True:
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.001)


def _counting_safe_load(monkeypatch, counter: list) -> None:
    orig = yaml.safe_load

    def spy(s):
        counter.append(1)
        return orig(s)

    monkeypatch.setattr(cm.yaml, "safe_load", spy)


def test_4a_barrier_rounds_all_readers_get_the_new_version_one_rebuild(mdir, monkeypatch):
    text_a, text_b = _ab(mdir)
    versions = {"A": _expected(text_a), "B": _expected(text_b)}
    parses: list[int] = []
    _counting_safe_load(monkeypatch, parses)

    n_readers, n_rounds = 16, 30
    go = [threading.Event() for _ in range(n_rounds)]
    start = threading.Barrier(n_readers, timeout=_WAIT_S)
    end = threading.Barrier(n_readers + 1, timeout=_WAIT_S)
    results: list[list] = [[] for _ in range(n_rounds)]
    errors: list[str] = []
    lock = threading.Lock()
    stats = {"rounds_done": 0, "parses_per_round": []}

    def reader():
        try:
            for r in range(n_rounds):
                if not go[r].wait(_WAIT_S):
                    raise TimeoutError(f"round {r}: go event not set")
                start.wait()  # release all 16 readers at once
                try:
                    got = cm.load_manifest(NAME)
                except Exception as e:  # noqa: BLE001
                    got = e
                with lock:
                    results[r].append(got)
                end.wait()
        except threading.BrokenBarrierError:
            return
        except Exception as e:  # noqa: BLE001
            with lock:
                errors.append(f"reader: {type(e).__name__}: {e}")

    threads = [threading.Thread(target=reader, daemon=True) for _ in range(n_readers)]
    for t in threads:
        t.start()
    try:
        for r in range(n_rounds):
            label = "B" if r % 2 == 0 else "A"
            _swap_file(mdir, text_b if label == "B" else text_a)  # readers are idle here
            parses.clear()
            go[r].set()
            end.wait()
            got = results[r]
            stats["parses_per_round"].append(len(parses))
            exc = [g for g in got if isinstance(g, Exception)]
            assert not exc, f"round {r}: {type(exc[0]).__name__}: {exc[0]}"
            assert len(got) == n_readers, f"round {r}: {len(got)} results"
            assert all(g == versions[label] for g in got), f"round {r}: a reader did not get version {label}"
            assert len(parses) == 1, f"round {r}: yaml.safe_load called {len(parses)} times (expected 1)"
            stats["rounds_done"] += 1
    finally:
        start.abort()
        end.abort()
        for e in go:
            e.set()
        for t in threads:
            t.join(timeout=_WAIT_S)
        print(f"\nD-M1-02 test 4a: rounds_done={stats['rounds_done']} "
              f"parses_per_round={stats['parses_per_round']} reader_errors={errors[:3]}")
    assert not errors, errors[:3]


def test_4b_caller_during_rebuild_waits_and_gets_the_new_version(mdir, monkeypatch):
    text_a, text_b = _ab(mdir)
    versions = {"A": _expected(text_a), "B": _expected(text_b)}
    assert cm.load_manifest(NAME) == versions["A"]  # a snapshot of A exists

    orig = yaml.safe_load
    entered, release = threading.Event(), threading.Event()
    parses_b: list[int] = []
    blocked_once = {"done": False}

    def blocking_spy(s):
        if s == text_b:
            parses_b.append(1)
            if not blocked_once["done"]:
                blocked_once["done"] = True
                entered.set()
                if not release.wait(_WAIT_S):
                    raise TimeoutError("release event never set")
        return orig(s)

    monkeypatch.setattr(cm.yaml, "safe_load", blocking_spy)
    _swap_file(mdir, text_b)

    out: dict[str, object] = {}

    def call(tag):
        try:
            out[tag] = cm.load_manifest(NAME)
        except Exception as e:  # noqa: BLE001
            out[tag] = e

    t1 = threading.Thread(target=call, args=("t1",), daemon=True)
    t2 = threading.Thread(target=call, args=("t2",), daemon=True)
    stats: dict[str, object] = {}
    try:
        t1.start()
        assert entered.wait(_WAIT_S), "thread 1 never entered safe_load for B"
        t2.start()
        t2.join(0.2)  # thread 2 reaches the rebuild; it must not return A meanwhile
        stats["t2_finished_before_release"] = not t2.is_alive()
        r2 = out.get("t2")
        stats["t2_result_before_release"] = r2.get("manifest_id") if isinstance(r2, dict) else repr(r2)
    finally:
        release.set()
        t1.join(_WAIT_S)
        t2.join(_WAIT_S)
        stats["safe_load_calls_for_B"] = len(parses_b)
        print(f"\nD-M1-02 test 4b: {stats}")

    assert not t1.is_alive() and not t2.is_alive(), "a caller hung"
    for tag in ("t1", "t2"):
        assert not isinstance(out[tag], Exception), f"{tag}: {out[tag]!r}"
    assert out["t2"] != versions["A"], "thread 2 got the old version A during the rebuild"
    assert out["t1"] == versions["B"] and out["t2"] == versions["B"]
    assert len(parses_b) == 1, f"yaml.safe_load called {len(parses_b)} times for B (expected 1)"


def test_4c_in_memory_flips_readers_only_see_whole_versions(mdir, monkeypatch):
    text_a, text_b = _ab(mdir)
    versions = {"A": _expected(text_a), "B": _expected(text_b)}
    target = mdir / f"{NAME}.yaml"
    shared = {"text": text_a}

    orig_read_text = pathlib.Path.read_text

    def read_text(self, *a, **k):
        if self == target:
            return shared["text"]  # no OS file operation for the manifest
        return orig_read_text(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    parses: list[int] = []
    _counting_safe_load(monkeypatch, parses)

    stop = threading.Event()
    lock = threading.Lock()
    stats = {"reads": 0, "flips": 0, "rebuilds": 0}
    bad: list[str] = []

    def reader():
        n = 0
        while not stop.is_set():
            try:
                got = cm.load_manifest(NAME)
            except Exception as e:  # noqa: BLE001
                with lock:
                    bad.append(f"{type(e).__name__}: {e}")
                continue
            n += 1
            if got != versions["A"] and got != versions["B"]:
                with lock:
                    bad.append(f"mixed: manifest_id={got.get('manifest_id')} window_days={got.get('window_days')}")
        with lock:
            stats["reads"] += n

    threads = [threading.Thread(target=reader, daemon=True) for _ in range(16)]
    for t in threads:
        t.start()
    try:
        end_at = time.monotonic() + 2.0
        flips = 0
        while time.monotonic() < end_at:
            shared["text"] = text_b if shared["text"] is text_a else text_a
            flips += 1
            time.sleep(0)  # yield so readers get turns
        stats["flips"] = flips
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=_WAIT_S)
        stats["rebuilds"] = len(parses)
        print(f"\nD-M1-02 test 4c: {stats} exceptions_or_mixed={len(bad)} first={bad[:3]}")

    assert not any(t.is_alive() for t in threads)
    assert not bad, bad[:5]
    assert stats["reads"] > 0 and stats["flips"] > 0
