# CLAUDE.md — rules for coding agents in this repository

Read this before changing anything. It holds rules, not results: this file
states no measurements. Every public number lives in `docs/claims.yaml`.

## Purpose

ControlPlane intercepts an AI agent's proposed tool call before it executes,
checks the claims inside it against the system of record (order DB, policy
store) queried at decision time, and allows, modifies, blocks or escalates,
writing an HMAC-signed decision receipt. The records in this repository are
synthetic seeds.

## The rule that carries the project

**The extractor produces CLAIMS. The registry produces FACTS. They never come
from the same place.** `ProposedAction.claimed_*` is what the agent asserted;
predicates read only `Evidence` from a system of record and the fields
`ProposedAction.facts_for_predicate()` returns. Never pass a `claimed_*` value
into a predicate. If a task seems to need it, stop and say so.

## How to run tests

Run tests and benchmarks on a copy, never in the live working tree:

```
git archive HEAD | tar -x -C <empty dir>
python data/build_db.py            # or copy the three data/*.db files in
python -m pytest tests/            # inside the copy
python bench/baselines.py --check  # headline table; writes nothing
```

`pytest.ini` sets the frozen demo clock. The suite never needs an API key;
unset provider keys before running. `tests/test_ground.py` skips itself
without `torch`. CI (`.github/workflows/ci.yml`) runs the full suite on Linux
and Windows.

## Files you must not change

- **FROZEN** (never edit): `bench/gold_set.jsonl`,
  `bench/ground_truth_holdout.jsonl`, `bench/label.py`,
  `bench/extraction_gold_v1.jsonl`, `docs/p06-post-p02-integrity.sha256`,
  every committed file under `reports/`, and tau2-bench simulation data.
  A frozen report that is wrong gets an entry in `docs/errata.md`, never an
  edit.
- **PROTECTED** (change only with an explicit, approved decision that names
  the file): `controlplane/intercept.py`, `controlplane/manifest.py`,
  `controlplane/decide.py`, `schemas/manifest.schema.json`,
  `manifests/*.yaml`, `tests/test_manifest_hardening.py`. Their hashes are in
  `docs/m1-integrity-v2.sha256`, checked by `tests/test_integrity_v2.py`.

## HEADLINE GUARD

After any change to `bench/baselines.py`, engine code under `controlplane/`,
a manifest or the schema, run `python bench/baselines.py --check` on a copy.
It must exit 0: B4/B5 direction accuracy, the discordant cases, the p-value
and every per-case prediction in
`bench/results/baselines-per-case-c240d87.jsonl` unchanged. If it fails,
stop and report the case ids. Never tune a manifest, threshold or label to
make it pass.

## NUMBERS RULE

- A number goes into public text only if code computes it from committed
  files. Add it to `docs/claims.yaml` with its definition, sample size,
  conditions, evidence path and command; `tests/test_claims.py` must pass.
- If you cannot run the thing, leave the number out and say it is
  unmeasured. Never invent, round up or copy a number from memory or from an
  old document.
- Latency figures come only from a committed evidence pack (today
  `bench/results/latency-m1-356ec58/`). They are per-call service time,
  sequential, on one machine — never "latency under load".

## KILL LIST

Never write these as current claims:

- any figure listed in `docs/retired-figures.md` or `docs/errata.md`
  (the circular-experiment results, the old P09 latency figures, the old
  receipt sizes);
- tau2-bench results as evidence of tool-call governance;
- external figures that no committed file backs;
- novelty wording ("first", "no one does X"); write "in the systems we
  surveyed" and cite `docs/related-work.md`.

Docs carrying a "Historical record" banner are records of past work, not
current claims; do not quote from them.

## Engineering constraints

1. **Money is integer paise.** Never floats; format only at the render
   boundary.
2. **Time comes from `controlplane/registry/clock.py`.** Never call
   `datetime.now()` inline.
3. **No LLM-as-judge on the critical path.** A model is the last resort, and
   then the verdict is `UNVERIFIABLE`, not a confidence score.
4. **`decide()` stays pure** — no I/O, no clock, no logging — and takes no
   protected-attribute parameter (`tests/test_no_protected_attributes.py`).
5. **Fail closed.** The gate never executes on missing, unavailable or failed
   evidence (`docs/decisions/D-M1-01-fail-closed.md`).
6. **Dependencies:** check the licence before adding one, note it in
   `requirements.txt`, and prefer the standard library.
7. **Instructor uses `Mode.JSON`, explicitly**, with required-but-nullable
   fields (`x: T | None`, no default) where "the model didn't say" must be
   distinguishable from "the key is missing" (see `controlplane/extract.py`).
8. **`data/build_db.py` stays deterministic** (`tests/test_data.py`).

## How to work

- Small commits, one component each, with its test in the same change.
- Cite the decision id (`# D49`, `D-M1-01`) when you implement one.
- When unsure, say so in your reply instead of guessing in code.
- Stage explicit paths only and run gitleaks on staged changes before a
  commit (`.gitleaks.toml`); never commit `.env`.
