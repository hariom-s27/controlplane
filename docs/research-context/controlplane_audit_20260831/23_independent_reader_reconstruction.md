# §25 — Independent-reader reconstruction

**Premise:** a skeptical researcher has only the public repository, the primary sources, the frozen artifacts and the public reports. Nothing else. Can they reconstruct the work?

| # | Question | Classification | Why |
|---|---|---|---|
| 1 | **What was tested?** | **PARTIALLY RECONSTRUCTABLE** | The pipeline is legible: `README.md`'s architecture diagram matches `controlplane/` file-for-file, and `CLAUDE.md` restates it. The *benchmarks* are readable too. But `data/*.db` and `data/stale_index/chunks.json` are gitignored, so the reader must run `data/build_db.py` to see the corpus at all — and the stale index, which *causes* the demonstrated failure, is a generated artifact |
| 2 | **What did the labels mean?** | **NOT RECONSTRUCTABLE** as valid labels — **fully reconstructable as tautologies.** A careful reader will see in `_make_case` that `gold_verdict` and `resolved_category` come from one variable, and conclude correctly that the labels mean nothing. On the branch, `docs/gold-set.md` explains what labels *would* mean, but `bench/label.py` and `gold_set.jsonl` are absent, so its central claim cannot be checked |
| 3 | **What did the metrics mean?** | **PARTIALLY RECONSTRUCTABLE** | Numerators and denominators are readable from source. But `coverage_ratio` has **two different definitions** under similar names (`schema.py::Decision.coverage` = (C1+C2+C3)/total; `report.py::_coverage_report` = (C1+C2)/total), and no committed `summary.json` disambiguates which was reported |
| 4 | **What changed between conditions?** | **RECONSTRUCTABLE for gate ON/OFF** — a single branch on `session.gate_enabled` at `intercept.py:165`, with everything upstream identical. **NOT RECONSTRUCTABLE for anything else**, because there is nothing else |
| 5 | **Why does the conclusion follow?** | **NOT RECONSTRUCTABLE.** For the negative control the reader can follow the causal chain and will accept it (n=1). For every accuracy claim the conclusion does *not* follow, and the reader can see why — the README hands them the proof ("exactly matching the 25% wrong-order-resolution rate the generator produces") |
| 6 | **What was withdrawn?** | **RECONSTRUCTABLE, and unusually well.** `docs/ROADMAP.md:81` carries an explicit kill list — `+36 points`, `63.3%/99.2%`, `55.8% whole-record`, `8% on HARD`, `15× swing`, `DBNR 2–3%`, `97–98% order accuracy`, and "the fabricated Runlayer sentence" — with the instruction to grep every artifact. `README.md`'s Honest limitations withdraws the noise sweep, the receipt-size target, logger 2 and the console's agreement rate. **This is better than most published work manages** |
| 7 | **What remains uncertain?** | **RECONSTRUCTABLE for what the project knows it does not know; NOT RECONSTRUCTABLE for what it believes it does.** The Honest-limitations section and `docs/gold-set.md` §5 are exhaustive about known gaps — including dead code and a crash path. What is *not* flagged as uncertain is precisely the set of tautological metrics, which are presented as findings |

## Where a reader gets stuck first

Running `make setup && make test` requires: Python (unpinned), a resolvable dependency set (floor-only, no lockfile, `zen-engine>=0.30`), and — for `make demo` — a `CP_RECEIPT_SECRET` they must generate. The demo then runs offline from committed fixtures, which is a genuinely good decision and the difference between a judge running it and reading about it.

Then:
- `make bench` reproduces two numbers that mean nothing.
- `make report` requires a populated `decisions.jsonl`; on a fresh clone it emits `None` for every latency stage, and draws the promotion chart from three hard-coded constants.
- `CP_MODE=live python scripts/gate_check.py` — the anti-staging check — **raises `ValueError`** (D-R1).
- Nothing in `reports/` or `docs/evidence/` contains a machine-readable result to compare against.

## The asymmetry

**The repository is more reconstructable than its results are.** A reader can rebuild the system exactly and still be unable to check a single reported number, because no number is frozen and no number is valid.

Both halves have the same cheap fix: commit `reports/summary.json` and a truncated `decisions.jsonl` under `docs/evidence/` with the git SHA and environment stamped in (D-06), and score against labels the gate did not produce (D-01/D-02).

## One thing a skeptical reader will conclude, correctly, in the project's favour

That the author knows where the bodies are. `docs/gold-set.md` §5 names its own dead code (`escalation_for()`), its own crash path (`RuntimeError` on a null `delivered_at`), its own clustering (50 cases on 5 orders), its own confounding ("a bare 'outside window → BLOCK' rule *passes*…") and its own label tells — before any external reviewer got there. This audit re-derived every one of those independently from source and found the register accurate.

**That register is the artifact's strongest claim to being taken seriously as research.** It should be surfaced in the README, not left in a doc on an unmerged branch.
