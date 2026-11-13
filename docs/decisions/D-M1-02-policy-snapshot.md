# D-M1-02 — Policy snapshot: validate the manifest once per content change

**Status:** accepted · **Branch:** m1-fail-closed · **Changes:** `controlplane/manifest.py` only

## Why

Every gate call used to re-read the manifest YAML, parse it, and run the full JSON-schema
validation, and `jsonschema.validate` re-checks the schema itself against the 2020-12
metaschema each time. Profiling (P04b) put almost all gate overhead in `load_manifest`,
about two-thirds of it in that metaschema check. The policy did not change between calls.

## What changed

- The schema validator is built once per schema object; the metaschema check runs once.
- `load_manifest(name)` still reads the file and takes its sha256 on **every** call. If the
  hash matches the stored snapshot, it returns a deep copy of the already-validated manifest
  and re-runs only the cheap semantic checks (graph file present, resolvers registered).
- If the hash differs, it rebuilds under a lock: parse with `yaml.safe_load`, run the full
  checks in the same order as before, then store the new snapshot with one reference swap.
- A failed rebuild removes the old snapshot first and caches nothing, so every call on broken
  content raises exactly the exception it raised before. Edits apply on the next call.
- Callers always get their own copy; mutating it cannot change what later calls see.
- `intercept.py`, `decide.py`, receipts, manifests and the schema are unchanged.

## How it is checked

`tests/test_policy_snapshot_m1.py`: (1) 50 calls parse and metaschema-check once, an edit
triggers exactly one rebuild — fails on the old loader; (2) missing / bad YAML / schema-invalid /
semantic-invalid / empty / graph removed raise today's exceptions, twice, then recover;
(3) copies are isolated; (4) 16 readers during atomic swaps only ever see a whole version.

## Where it fails

- The per-call file read and hash remain; there is no change notification or live reload.
- Predicate graph edits still need a process restart (unchanged: the predicates module
  caches compiled graphs).
- On Windows a call can fail with `PermissionError` while the file is being atomically
  replaced (same as today).
- A broken manifest raises an exception and writes no receipt (same as today; future work).
- The receipt does not yet name the policy revision (manifest file hash).
