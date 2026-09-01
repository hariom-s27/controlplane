# V. Final gap-closure matrix

| Gap | Current evidence | Missing evidence | Reviewer risk | Minimal closure | Cost | Methodological risk | Documentation alternative? | Final decision |
|---|---|---|---|---|---|---|---|---|
| **G1 Generality** | 2 domains; 2nd has no rule layer; 1 seed, 1 model (replayed), 1 dataset. Ladder **Level 0→1** | independent cases; a domain not authored alongside the gate | **HIGH** | commit the 150-case gold set (D-02) | low | low | **NO** — documentation cannot manufacture cases | **CLOSE NOW** (partially, to Level 1) |
| **G2 External validation** | 1 external component (HHEM-2.1-Open), off by default; its accuracy bound borrowed from a model the project excluded | any third-party benchmark/evaluator/dataset | **HIGH** | none available before the deadline | very high | medium | **PARTIALLY** — state the limitation precisely, and fix the 77.4% attribution (D-14) | **DOCUMENT LIMITATION** |
| **G3 Falsifiability** | 4 committed metrics that cannot produce evidence against the system | labels the gate did not produce | **CRITICAL** | re-score Exp 5 against `bench/label.py` | low | **low, but the matrix will not be diagonal — that is the point** | **NO** | **ONE EXPERIMENT — do it** |
| **G4 AgentLTL positioning** | none in repo | primary-source comparison | MEDIUM | already executed by this audit (`07`): κ_ground grounds in `out(τ)`; ControlPlane re-queries the record | done | none | **YES — this one is genuinely a documentation closure** | **CLOSE NOW** |
| **G5 Threat model** | none; ROADMAP's "one test worth naming" not built; 2 confirmed fail-opens | a threat model, a chaos test, a red team | **HIGH** | fix D-03/D-04, then write the model (`09` is a draft) | low now | low | **PARTIALLY** — the model is documentation; the fail-opens are not | **CLOSE NOW** (fixes + model); **DO NOT DO** the red team yet |
| **Prior-art positioning** | ROADMAP §7 already cites Reddy et al., C-Trace, PoE, Wix, MiniCheck, CostBench and forbids six specific overclaims | OAP, Aegis, Policies-on-Paths, AgentCore Policy, Automated Reasoning checks, AgentLTL | MEDIUM | adopt `08_prior_art_matrix.md` | done | none | **YES** | **CLOSE NOW** |
| **Construct validity** | tautological labels in all four generators | independent labels | **CRITICAL** | as G3 | low | low | **NO** | **ONE EXPERIMENT** (the same one) |
| **Information leakage** | label ≡ prediction input | separation | **CRITICAL** | as G3 | low | low | **NO** | **ONE EXPERIMENT** (the same one) |
| **Causal identification** | only gate ON/OFF is identified, n=1 | a 4-arm evidence-source ladder (`12` §K.5) | HIGH | E1–E4 over identical cases, paired, cluster-bootstrapped | medium | medium — **cannot precede the gold set**, or the arms score themselves | **NO** | **NEEDS the gold set first** |
| **Statistical rigour** | good machinery (MDE, κ-refusal, clustering disclosure) pointed at degenerate estimands | a non-degenerate estimand | HIGH | as G3, then **cluster-robust bootstrap over `source_order_id`** | low | low | **NO** | **CLOSE NOW** (with G3) |
| **Multi-seed** | 1 seed everywhere | — | **LOW** | — | — | **HIGH if done** — decoration on a tautology | — | **DO NOT DO** |
| **Reproducibility** | seeds, frozen clock, byte-deterministic DB, pinned fixture hashes on branch | frozen outputs; a working `gate_check.py`; a lockfile | HIGH | D-05 (1 line), D-06 (30 min), D-20 (30 min) | low | none | **NO** | **CLOSE NOW** |
| **`MODIFY` fail-open** | none | — | **CRITICAL** | ~3 lines | trivial | none | **NO** — disclosure is not closure for a shipped fail-open | **CLOSE NOW** |
| **Missing-record crash** | project-documented | — | HIGH | ~10 lines | trivial | none | **NO** | **CLOSE NOW** |
| **Dead `escalation_for()` / inert `SOURCE_UNRELIABLE`** | project-documented | — | MEDIUM | wire it, or delete it and its 2 tests | ~1 h | none | **PARTIALLY** | **CLOSE NOW** |
| **Inert manifest fields (5 of 9), incl. `fail_posture`** | grep | — | MEDIUM | wire `fail_posture`; mark the rest reserved | ~1 h | none | **PARTIALLY** | **DO IF TIME** |
| **Receipt integrity (no chain, shared secret, telemetry unsigned)** | HMAC + tamper test | chaining; scope | MEDIUM | prev-hash field + verifier | ~2 h | none | **PARTIALLY** | **DO IF TIME** |
| **Human validation** | 30-row blind sheet; `agreement.py` refuses partial κ | 30 human labels | MEDIUM | fill the sheet | ~2 h | **medium — low κ is a real finding, and publishable either way** | **NO** | **DO IF TIME**, after G3 |
| **Gate bypassability** | `gate_enabled` flag; in-process impls | out-of-process mediation | LOW (for a prototype) | — | high | — | **YES** — and drop the SEC 15c3-5 non-bypassability framing | **DOCUMENT LIMITATION** |
| **Unverified `2.45%` citation** | absent from USPS 22-159-R23 | the actual source | MEDIUM — in a project whose pitch is citation discipline | find it or delete it | 30 min | none | **YES** | **CLOSE NOW** |
| **`docs/gold-set.md` §5 false `SystemExit` claim** | `git diff` is empty | — | MEDIUM | delete the sentence or make it true | 10 min | none | **YES** | **CLOSE NOW** |
| **τ²-bench / BFCL integration** | none | the integration | LOW for this deadline; CRITICAL for a paper | — | very high | medium | **YES for now** | **DO NOT DO NOW** |
| **Additional domains / policy variants** | 2 domains, 2 manifests | — | LOW | — | very high | medium | **YES** | **DO NOT DO** |
| **Adversarial red-team** | none | a threat model + a testbed | HIGH eventually | — | high | **high while fail-opens stand** | **PARTIALLY** | **DO NOT DO NOW** |

## Tally

| Decision | Count |
|---|---|
| **CLOSE NOW** | 10 |
| **ONE EXPERIMENT** (all three rows are the *same* experiment) | 3 |
| **NEEDS the gold set first** | 1 |
| **DO IF TIME** | 4 |
| **DOCUMENT LIMITATION** | 3 |
| **DO NOT DO** | 4 |

**There is exactly one experiment on this matrix, and it appears three times because three separate gaps close together when it is run.**
