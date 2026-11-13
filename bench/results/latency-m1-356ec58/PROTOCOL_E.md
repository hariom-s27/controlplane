# P04c Part E — measurement protocol (written 13 Nov 2026, before the first run)

## Conditions
- OLD = `git archive 880d5c9` → `_work\p04c\e\old` (+ data/entitlements.db, orders.db, policy_store.db; sha256 checked against the worktree copies)
- NEW = `git archive 356ec58` → `_work\p04c\e\new` (+ the same DBs; sha256 checked)
- No file in either copy is edited. No in-process patches, no wrapper around timed calls.

## Workload
- C1 (`bench/latency.py` CONFIGS[0] = C1_hhem_off_seq: HHEM off, concurrency 1), via
  `_work\p04c\scripts\c1_driver_p04c.py <copy> plain <out.json> <label>` with no further arguments
  → n = 1,050 timed calls, warm-up 50 (discarded), CAPTURE off.
- Interpreter: `controlplane\.venv\Scripts\python.exe` (3.14.3) with `-I`.
- Environment per process (`scripts\env.sh`): API_KEY / *_TOKEN variables unset (names printed only),
  HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1, TMP = TEMP = `_work\p04c\tmp`.
- `controlplane.__file__` printed and asserted inside the copy for every run.

## Order
Round 1: OLD, NEW · Round 2: NEW, OLD · Round 3: OLD, NEW (6 runs, sequential, one at a time).

## Machine gate
- `scripts\gate.ps1` (copy of the P04b script, sha256 4fe9efdc…96a7): pass = available RAM ≥ 3 GB
  (the script's `avail_GB`, `\Memory\Available MBytes`) AND CPU 5-sample average ≤ 15 %.
  Free physical RAM (`free_GB`) is recorded too.
- Run before each round, and additionally before every run, so each run has its own RAM/CPU record.
- Thresholds are never lowered. On a fail: STOP and report free RAM, commit size and the top 5
  processes by private bytes (the script prints them).

## Recorded per run
p50 / p95 / p99 / max of end-to-end, Σ stage p50, gap mean, intervention mix, all-signatures-valid,
free/available RAM, CPU average, power scheme, path, flags, DB sha256. Every run is reported,
including crashes.

## Expected / success line
- Intervention mix for every run: ALLOW 378 / BLOCK 602 / ESCALATE 70; all signatures valid.
- Per condition: median of the 3 p50 and median of the 3 p99.
- Success line: NEW median-of-3 p99 ≤ 15 ms.
- Numbers are sequential per-call service times in one process. No statistical claim is made
  without a test.

## Amendment 1 (13 Nov 2026, before any run)
Found before the first run: the power overlay was 961cc777-2547-4f9d-8174-7d86181b8a7a
(Best power efficiency, GUID_POWER_MODE_BEST_EFFICIENCY), not Best performance. The user then
set Power mode (plugged in) to Best performance. The agent changes no power setting.

- **E1 (official):** power mode Best performance. Before each round (and before each run), read
  `HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\ActiveOverlayAcPowerScheme`;
  it must equal `ded574b5-45a0-4f42-8737-46345c09c238`, else STOP. Order OLD NEW | NEW OLD |
  OLD NEW; machine gate as above. The success line applies to E1 only:
  NEW median-of-3 p99 <= 15 ms.
- **E2 (secondary, comparison with P04b):** power mode Best power efficiency
  (`961cc777-2547-4f9d-8174-7d86181b8a7a`), set by the user after E1. Same order, gate, n and
  warm-up; the overlay must read 961cc777-… before each round, else STOP. No success line; report only.
- Each run's overlay GUID is recorded. E1 and E2 outputs go to `e\out\E1_*` and `e\out\E2_*`.
