# Errata for frozen reports

The reports under `reports/` are frozen: they are never edited after they
are committed, so a later correction cannot go into them. This file records,
for each statement in a frozen report that is no longer correct, what was
stated, what is correct now and what shows it. Newest entries first.

Current numbers are listed in `docs/claims.yaml` and checked by
`tests/test_claims.py`. Figures named below as stale are history only and
must not be quoted as current.

---

## 2026-11-15 (P07a)

### E6 — `reports/README.md`: tau2-bench C1 described as done

| | |
|---|---|
| Report and lines | `reports/README.md:17` (row for `tau2-bench.md`: "Partial — C1 baseline only; C2/C3 pending"); `reports/README.md:70-74` ("tau2-bench C1 (a governance-free baseline on a third-party benchmark) is done; C2/C3 … are not yet built or run") |
| Stale text | tau2-bench C1 described as a completed baseline, with C2/C3 still to come |
| Correction | Same withdrawal as E3, which named only `reports/tau2-bench.md`: tau2-bench C1/C2 are retired as evidence (0 tool calls; the adapter dropped tools), and the runs are not in this repository. No C1 baseline exists that a later comparison could build on. The rest of the "External validation is incomplete" point stands: every quantitative result in the reports is internal, single-domain, single-gold-set evidence. |
| Evidence | E3 below (the same finding; this entry only extends it to the two places in `reports/README.md` that E3 did not name) |

---

## 2026-11-14 (P05b)

### E1 — `reports/latency.md`: P09 timing figures retired

| | |
|---|---|
| Report and lines | `reports/latency.md` §C, §D, §G and §H (lines 47-147, incl. :105, :124-125, :133-135), §I-J comparison line (:158, :160); the same values in `reports/summary.json['p09_latency']` and the decision-trail block `reports/summary.json['latency']` |
| Stale text | the C1 (grounding off) end-to-end p50 / p95 / p99 / max, the grounding-on (C2, C4) figures, the cold-start load time and the concurrency comparison |
| Correction | None of these is a current figure. The report records no commit id; per the P04c audit, the run used an uncommitted working tree (that audit record is not in this repository), and a later session could not reproduce the C1 values (`docs/decisions/D-M1-01-fail-closed.md`, "Measured effect"). Current latency figures come only from the committed evidence pack `bench/results/latency-m1-356ec58/`: per-call service time, sequential, one process, one laptop, median of the runs per condition. No grounding-on or concurrent-load figure is current. |
| Evidence | `bench/results/latency-m1-356ec58/README.md`; `python summarise.py --check` in that folder; `sha256sum -c SHA256SUMS` |

### E2 — `reports/robustness.md`: scenarios 2 and 6 describe the pre-D-M1-01 engine

| | |
|---|---|
| Report and lines | `reports/robustness.md:14` (scenario 2, `record_unavailable`); `:18` and `:426` (scenario 6, `grounding_timeout`) |
| Stale text | scenario 2: knowledge-assistant outage "tier_0 open -> execute with unverified receipt"; scenario 6: "HHEM timeout degrades to C1/C2 … valid action proceeds" (VERIFIED / ALLOW) |
| Correction | Since D-M1-01 the gate never executes on missing evidence. Scenario 2, knowledge assistant: the `open` posture is removed; the active posture is `escalate`, so the action is held (pending), not executed. Scenario 6: a grounding timeout with grounding on gives UNVERIFIABLE / ESCALATE and marks C3 unavailable. Servicing's outage behaviour (closed, BLOCK) is unchanged. The self-checks of scenarios 2 and 6 in `bench/failure_injection.py` still expect the old outcomes and would report a failure if re-run; this is recorded here and not changed in P05b. Scenario 1 (the wrong-record crossover) is unaffected and is recomputed by `tests/test_claims.py`. |
| Evidence | `docs/decisions/D-M1-01-fail-closed.md` (R1, R3, "Tests whose expectations changed", "Known limitations"); `tests/test_failure_injection.py::test_p08_record_unavailable_knowledge_honours_escalate_posture_and_marks_unverified`, `::test_p08_grounding_timeout_is_unverifiable_and_marks_c3_unavailable` |

### E3 — `reports/tau2-bench.md`: retired as evidence

| | |
|---|---|
| Report and lines | `reports/tau2-bench.md:3` ("C1 in progress"), the C1 result (:375-376, :436-437, :453), `:463` (`manifests/tau2_retail.yaml`, never built) |
| Stale text | C1 reported as a completed governance-free baseline; C2/C3 described as pending ControlPlane comparisons |
| Correction | tau2-bench C1/C2 retired as evidence (0 tool calls; adapter dropped tools); the runs are not in this repo (from run records kept outside this repo; not reproducible from it). No tau2 figure is quoted anywhere as evidence of tool-call governance. |
| Evidence | The simulation files are outside this repository; the finding comes from a local audit whose record is not committed. This entry is therefore a withdrawal, not a new result. |

### E4 — `reports/summary.json['receipt_size']`: stale

| | |
|---|---|
| Report and lines | `reports/summary.json['receipt_size']` (n, median, p95, min, max bytes) |
| Stale text | the receipt-size aggregate measured before the verification-coverage block was added to the receipt |
| Correction | Receipts produced by the current code are larger; the aggregate no longer describes them. No receipt size is quoted as current. |
| Evidence | `bench/receipt_size.py::measure_receipt_sizes(120)` on the current code gives different values (P05b, Part A); `controlplane/receipt.py::build_receipt` (the `verification_coverage` block) |

### E5 — `reports/baselines.md` latency columns: wall-clock, not a claim

| | |
|---|---|
| Report and lines | `reports/baselines.md`, the "median lat (ms)" / "p95 lat (ms)" and "median ms" / "p95 ms" columns; the same fields in `reports/summary.json['p04_baselines']` |
| Stale text | per-system latency of B0, B1, B2, B4, B5 |
| Correction | These cells are wall-clock time from one run on one machine. They are not current figures, and `python bench/baselines.py --check` deliberately does not compare them; every other cell is checked exactly. B3's latency is the recorded LLM call time from its fixtures. |
| Evidence | `bench/baselines.py` (`WALL_CLOCK_SYSTEMS`, `check()`) |
