# N. Reproducibility audit

## N.1 What is pinned

| Dimension | Status | Evidence |
|---|---|---|
| Random seed | **PINNED** — `CP_SEED=20260814`, default in `build_db.py`, `mutation.py`, `bias_probe.py`, both bench scripts, `report.py` | `.env.example`, source defaults |
| Clock | **PINNED** — `CP_DEMO_DATE=2026-08-14`; `registry/clock.py` is the single source of `now()`, with a `set_clock()` test override; `pytest.ini` sets it via `pytest-env` | `clock.py`, `pytest.ini` |
| Database | **BYTE-DETERMINISTIC**, asserted by test; `PRAGMA journal_mode=DELETE` to avoid `-wal`; sorted inserts | `data/build_db.py`, `tests/test_data.py:114` |
| Model identity | **PINNED** — `CP_MODEL=Qwen/Qwen3-8B` | `.env.example` |
| Model responses | **CACHED** — content-hash fixtures; `CP_MODE=fixture` is the default and raises rather than calling the network on a cache miss | `agents/llm.py::chat`, `controlplane/extract.py` |
| Python version | **NOT PINNED** — no `.python-version`, no `requires-python`, no `pyproject.toml`. `Makefile` uses bare `python3` | — |
| Dependency versions | **FLOOR-ONLY** (`pydantic>=2.7`, `instructor>=1.5`, `zen-engine>=0.30`, `hypothesis>=6.100`, …). No lockfile, no hashes. **One genuine upper bound**, and it is well-earned: `transformers>=4.40,<5.0`, pinned because `transformers>=5.0` breaks HHEM's `trust_remote_code` class — documented with the actual `AttributeError` | `requirements.txt` |
| Configuration provenance | **PARTIAL** — `.env` is gitignored; `.env.example` documents every flag, which is good practice |
| Artifact hashing | **ABSENT on `main`. PRESENT on the branch** — `tests/test_gold_set_determinism.py` pins three SHA-256 hashes and asserts byte-identity across two builds. That is the right mechanism |
| State reset | **PARTIAL** — `make clean`; but `decisions.jsonl` is **append-only across runs**, so `latency_percentiles()` and `report.py` aggregate over an unbounded, unversioned history |
| External dependencies | Featherless API + HuggingFace model download (both optional in default mode) | — |
| Benchmark runner | `Makefile` / `make.ps1` | — |
| Environment construction | `python3 -m venv .venv` + `pip install -r requirements.txt` — no lock, no container, no CI | — |

## N.2 The three reproducibility breaks

### D-R1 — `scripts/gate_check.py` cannot run against the committed code
**This is the most serious reproducibility defect in the repository, because it invalidates the one artifact that exists to prove the demo is not staged.**

- `agents/servicing_agent.py::propose` returns a **4-tuple**: `tuple[dict | None, dict, str, list[str]]` — `(call, message, context, chunk_texts)`.
- `scripts/gate_check.py:42` does `call, message, _ = propose(phrasing)` — **3 targets**.
- Python raises `ValueError: too many values to unpack (expected 3)` on the first iteration.

Both files were introduced or last modified in the same mega-commit `c653b7f`; `propose()` gained `chunk_texts` when `dispatch_tool` began receiving `retrieved_chunks`, and the script was not updated. `docs/evidence/gate_condition_check.txt` therefore records a run of **an earlier version of the code that is not in any commit**.

*(Established by static inspection of both files, consistent with §0's no-execution constraint. Trivially confirmable by running the script.)*

**Consequence:** the repository's answer to "did you stage the demo?" is currently unreproducible. Fix cost: **one line.**

### D-R2 — no result artifact is committed
`.gitignore` excludes `reports/`, `decisions.jsonl`, `decisions_privileged.jsonl`, `data/*.db`, `data/stale_index/`.

The DBs and the stale index are rebuildable from committed seeds, which is a legitimate and well-reasoned choice. But `reports/` and `decisions.jsonl` are **outputs**, and excluding them means **no number the project reports is inspectable without re-running everything**. There is no `summary.json`, no confusion matrix, no coverage table, no latency percentile in any commit.

Against the brief's "frozen evidence" premise: **there is no frozen evidence.** Against §25: an independent reader cannot check any figure without a working environment.

### D-R3 — hand-carried constants in the "no hand-typed numbers" script
`bench/report.py:41-43`. See contradiction C-1 (`01`) and `13` §L.5.

## N.3 Weakest link

**Ranked:**

1. **D-R2 — nothing is frozen.** Every claim depends on the reader rebuilding the world.
2. **D-R1 — the anti-staging evidence is unreproducible.**
3. **Unpinned Python + floor-only dependencies with no lockfile.** `zen-engine>=0.30` is the sharpest risk: the entire predicate layer is a third-party JDM evaluator on a floor-only pin, and a change in null-handling would silently alter `predicate_result` (`09` T-4 shows a null is treated as *pass*).
4. **Fixture mutability.** `data/fixtures/` is committed, unsigned, and rewritten at runtime under `CP_MODE=live`. For an artifact whose default mode is replay, the fixtures *are* the experiment, and nothing binds them to a run.
5. **`decisions.jsonl` accumulates across runs**, so any percentile is over an unversioned mixture.

## N.4 What to do, cheapest first

| Fix | Cost | Effect |
|---|---|---|
| Fix the `gate_check.py` unpack | 1 line | Restores the anti-staging evidence |
| Commit `reports/summary.json` and a truncated `decisions.jsonl` under `docs/evidence/`, with the git SHA and env recorded | ~30 min | Turns "trust us" into "check us"; creates the first genuinely frozen artifact |
| Add `pyproject.toml` with `requires-python` + a `pip freeze` lockfile | ~30 min | Removes the dependency-drift risk |
| Delete `MEASURED_GROUNDING_*` from `report.py` or move them to a dated `docs/evidence/grounding_latency.txt` with the machine spec | 15 min | Resolves contradiction C-1 |
| SHA-256 manifest over `data/fixtures/` asserted by a test | ~1 h | Binds the replayed experiment to committed bytes |
| Adopt the branch's `test_gold_set_determinism.py` pattern repo-wide | ~1 h | The mechanism is already written; generalise it |

**None of these is an experiment. All of them raise the artifact's credibility more than any additional benchmark would.**
