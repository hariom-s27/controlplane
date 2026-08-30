# P04 prior-art clarification — AEGIS's 500-benign-call FPR is not a ranking against ours

**Status of this document: preventive, not corrective.** A full-repository
search (`grep -rn "AEGIS" reports/ docs/ bench/`) found no existing claim in
this repository comparing our P04 false-positive rate to AEGIS's. AEGIS is
currently cited only for **latency** (`reports/latency.md`, P09) — never for
FPR. This document exists so that comparison is never made carelessly later,
not because a wording defect was found.

## AEGIS — verified from the primary source (arXiv:2603.12621)

Read directly from `arxiv.org/html/2603.12621` (the false-positive-analysis
section).

| Item | Finding | Category |
|---|---|---|
| Sample size | 500 benign tool calls | PAPER-DERIVED |
| False positives | 6 | PAPER-DERIVED |
| FPR | 6/500 = 1.2% | PAPER-DERIVED |
| Selection method | "sampled from production-like workflows" — the paper states this but does not describe the sampling frame, data source, or collection procedure beyond this phrase | PAPER-DERIVED |
| Workflow/tool types | "SELECT queries, file reads, API requests, and text processing" — listed, not quantified by proportion | PAPER-DERIVED |
| Sampling procedure (random / stratified / other) | **Not specified in the paper.** | PAPER-DERIVED (absence) |
| Population size the 500 were drawn from | **Not specified in the paper.** | PAPER-DERIVED (absence) |
| Time window of collection | **Not specified in the paper.** | PAPER-DERIVED (absence) |
| Explicit representativeness claim or disclaimer for the benign sample | **Not specified in the paper.** (The paper's own "Limitations" section disclaims attack-category exhaustiveness — "covers known attack categories but is not exhaustive" — but says nothing about the benign sample's representativeness.) | PAPER-DERIVED |
| Root cause of the 6 false positives | **A single shared cause**, not six distinct ones: "All six cases arise from legitimate SQL queries with disjunctive WHERE predicates that trigger the OR-based injection pattern." No per-case breakdown is given. | PAPER-DERIVED |
| Mitigation the paper offers | "these cases can be mitigated through server-side tool-specific overrides without disabling the corresponding policy globally" | PAPER-DERIVED |

**Correction to a common mis-paraphrase:** AEGIS does not report "six distinct
false-positive causes." It reports six false-positive *instances* sharing
**one** documented root cause (OR-predicate SQL flagged as injection-like).
Any future citation of this number should say so.

## OAP — verified from the primary source (arXiv:2603.20953)

Read directly from `arxiv.org/html/2603.20953v1`.

**No directly comparable benign-call FPR experiment was identified.** OAP's
evaluation section reports: an adversarial testbed (4,437 authorization
decisions across 1,151 sessions; a live bounty where social engineering
succeeded 74.6% of the time under a permissive policy and 0% under a
restrictive OAP policy across 879 attempts) and latency (p50 53 ms, N=1,000).
Neither is a benign-call false-positive measurement, and the paper's own
"Threats to validity" section discusses attacker self-selection, not
false-positive testing on legitimate operations. **Do not invent an OAP FPR
figure — none exists in the source.**

## Our P04 — repository-derived, independently verified this audit

Source: `reports/baselines.md`, `bench/gold_set.jsonl` (SHA-256
`09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e`),
`bench/label.py`.

| Item | Our P04 | Category |
|---|---|---|
| Unit of analysis | one proposed `issue_refund` tool call, scored against an independently re-derived gold label (`bench/label.py`, never `controlplane.decide`) | REPOSITORY-DERIVED |
| Population | 150 synthetic gold cases (140 non-ambiguous + 10 ambiguous), one refund-servicing domain | REPOSITORY-DERIVED |
| "Benign" here means | the 50 gold-`ALLOW` cases (the `allow_in_window` slice) | REPOSITORY-DERIVED |
| FPR denominator | 50 gold-ALLOW cases | REPOSITORY-DERIVED |
| Source-order clustering | the 50 ALLOW cases sit on **5** real source orders (10 variations each), not 50 independent orders; 101 source-order clusters exist across the full 150-case set. `reports/baselines.md` explicitly discloses this and resamples clusters (not cases) for every CI. | REPOSITORY-DERIVED |
| Selection method | fully deterministic, seed-pinned construction (`CP_SEED=20260814`) from real `data/orders.db` rows — documented, reproducible, not "sampled from production" | REPOSITORY-DERIVED |
| Our measured FPR (B5/ControlPlane) | 0.0% [0.0%, 0.0%] across 3 evaluation-order seeds (`reports/baselines.md`) | OUR MEASURED RESULT |

## Conclusion — the AEGIS number is contextual, not an apples-to-apples ranking

The two FPR figures describe **different populations measured by different
protocols**:

- AEGIS: 500 calls "sampled from production-like workflows" with an
  unspecified sampling method, unspecified population, and no stated
  independence structure between the 500 calls.
- Ours: 50 cases built from 5 real orders under 10 controlled variations
  each, explicitly clustered, explicitly resampled at the cluster level for
  every confidence interval, and traceable case-by-case to `bench/label.py`'s
  independent verdict.

Neither population size, sampling procedure, nor independence structure is
comparable. **A statement like "ControlPlane's FPR beats AEGIS's 1.2%" would
overclaim comparability that the source data does not support**, regardless
of which number is numerically lower — this document exists to head that off
before it is written, not because it currently appears anywhere in this
repository.

**No unsupported novelty claim is made here.** This document does not assert
that ControlPlane is the first system to check database state, that AEGIS or
OAP fail to do so, or that no other prior work exists — no literature search
beyond these three named papers was performed, so no such claim could be
supported.
