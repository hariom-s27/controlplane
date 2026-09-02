# Claim corrections — P11 R2 audit

**Scope.** Repository-wide claim-discipline pass over the P10 R2 base
`68eeb90a82774e986a9d75c3b6ca6a382bf64cde` (parent
`4ef58129649019e688e5db564f78df9169d686c3`), public baseline
`6ec4261d374904f55bf5dff1a9855854f1b94819`. No source, test, benchmark,
data, manifest, or frozen-evidence file was modified or executed. No
experiment, benchmark, provider, or LLM call was made.

**What changed since the prior P11 pass (commit `8f7eea4` on ancestor
`2d5ed94`).** Two commits were added on top of `2d5ed94`:

- `4ef5812` "docs: stabilize release candidate identity" — replaced hardcoded
  references to a single SHA as "the verified local release candidate" with
  "the candidate represented by the audited HEAD" in `README.md`,
  `docs/experiment-audit.md`, `docs/retired-figures.md`, and
  `docs/related-work.md`. This is a provenance improvement, not a claim
  change: it stops a specific commit hash from going stale as "the
  candidate" once further commits land on top of it, while still correctly
  naming `986b65e`, `dce2e4c`, and `aac3bea` for what they specifically
  contain (C/I/D reconciliation, recipient-authorization fix, threat-model
  sync — not "the candidate" itself).
- `68eeb90` "docs: finalize evidence-grounded related work" — substantially
  expanded `docs/related-work.md`: added AEGIS/OAP/Reason-Less-Verify-More
  under a new "Pre-execution enforcement" section, added LEDGER under
  "Trace-grounded verification", added a full-paper (not abstract-only)
  LedgerAgent comparison under "Maintained structured state", and added an
  "Auditable Agents" honest self-scored rubric plus a provenance-survey
  citation under "Auditable and accountable agents". Every new claim in this
  rewrite is qualified at or below its cited source (specific §-level
  citations, `NOT DIRECTLY COMPARABLE` markers, explicit "not presented as a
  contribution" / "not claimed as a contribution" / "does not establish
  superiority" language throughout).

Both commits were read in full diff (not summarized) as part of this audit.
Neither introduces an indefensible claim; both tighten evidence scoping.

**Claim-bearing tracked files audited this pass:**

- Full diff review: `README.md`, `docs/experiment-audit.md`,
  `docs/retired-figures.md`, `docs/related-work.md` (the four files touched
  since the last audited state)
- Full re-read of the current file: `README.md`, `docs/related-work.md`
- Carried forward unchanged from the prior pass (byte-identical; re-grepped
  this pass to confirm): `CLAUDE.md`, `docs/threat-model.md`,
  `docs/compensability.md`, `docs/decision-receipt.md`, `docs/invariants.md`,
  `docs/evidence/gate_condition_check.txt`,
  `docs/evidence/negative_control.txt`, `docs/ROADMAP.md`
- `**/*.py` grepped for the full dangerous-term list; no docstring or
  comment contains an unsupported positive claim (no BLOCKED condition)

## Result

**Zero corrections were required.** As in the prior audited state, every
material claim in this tree already carries wording at or below its
supporting evidence.

### A. Labeling language

No "independent labels" / "independently label(l)ed" phrasing exists
anywhere in the tree. Nothing to correct.

### B. Sample-size / cluster-count language

No P03 gold-set sample-size claim (`n=50` or otherwise) appears anywhere in
the tree — P03 remains off-release and excluded from every candidate
document. Nothing to correct.

### C. P04 +12.1% claim

Does not appear anywhere in the tree. P04 remains off-release
(`docs/related-work.md` §Evidence and limitations: "The off-release P04,
P05/A1–A5, P08, and P09 results are not evidence for the current candidate,
because they have not been rerun against it"). Nothing to correct.

### D. P05 crossovers

Do not appear anywhere in the tree, for the same reason as C. Nothing to
correct.

### E. Receipt-integrity contribution

`docs/related-work.md` (§Pre-execution enforcement, §Auditable and
accountable agents, §Where ControlPlane sits, §Evidence and limitations —
four independent places) states AEGIS's Ed25519/SHA-256 hash-chained design
is stronger than ControlPlane's HMAC receipt, and explicitly: "ControlPlane's
receipt design is not presented here as a differentiator from AEGIS" and
"not claimed as a contribution." `docs/threat-model.md` T23–T26 and its
"Important non-goals" section independently state the same limitation.
Nothing to correct.

### F. tau2 write metrics

No tau2 write-outcome fraction appears anywhere in the tree.
`docs/related-work.md` and `docs/threat-model.md` both state P06/tau2
results are not used. Nothing to correct.

### G. Kappa / human-label language

No κ value (Cohen's kappa / P03-M4 agreement statistic) appears anywhere in
the tree. The only κ symbol in the tree is `docs/related-work.md`'s
`κ_ground`, which is AgentLTL's own published grounding-predicate notation
(a prior-art description, correctly attributed with a §8 citation), not a
ControlPlane statistic. No "human validated" / "externally validated"
phrasing applies to ControlPlane's own claims — the only such phrases are
negative disclaimers (`docs/threat-model.md`'s non-goals list;
`docs/related-work.md`: "does not establish... external validation").
Nothing to correct.

### H. M5 language

`README.md` and `docs/invariants.md` (unchanged from the prior audited
state) describe M5 as a bug "identified by Hypothesis property-based
testing rather than an observed exploit" and "a defect class an agent (or a
bug) could trigger by degrading its own evidence quality" — adversarially
*relevant* framing, never "exploitable by an agent." No such phrase exists
in the tree. Nothing to correct.

## P10 consistency check (§15 of the task)

Read `docs/related-work.md` in full and verified consistency of the rest of
the claim-bearing tree against it:

- **AEGIS positioning** (arXiv:2603.12621) — consistent across
  `related-work.md` and `threat-model.md` T24/T25 and the "Relationship to
  research claims" section: AEGIS's hash-chained, Ed25519-signed design is
  repeatedly acknowledged as stronger.
- **LedgerAgent positioning** — `related-work.md`'s full-paper comparison
  (ledger populated only from the agent's own prior reads) is not
  contradicted anywhere else in the tree; no other document claims source
  independence from the agent's own retrieval that `related-work.md`
  qualifies.
- **AgentLTL positioning** — consistent (stateless per-action `decide()` vs.
  AgentLTL's temporal constraints; both files agree ControlPlane adds no
  comparable temporal expressiveness).
- **C-Trace positioning** — consistent (trace-level GDPR obligations vs.
  transactional-record reconciliation; both `related-work.md` and
  `ROADMAP.md`'s own "adapt, don't copy" table draw the same distinction).
- **OAP/AgentCore positioning** — consistent (authorization-of-principal vs.
  content-agreement-with-a-record; AgentCore's Cedar/Dogwood policy engine
  acknowledged as a declarative-policy prior art in both `related-work.md`
  and implicitly in `CLAUDE.md`'s manifest vocabulary).
- **Fresh re-query vs. source independence** — stated three times in
  `related-work.md` (Maintained structured state, Where ControlPlane sits,
  Evidence and limitations) and once in `threat-model.md` (T27, "Agent and
  resolver share a store... Freshness is not statistical or source
  independence"). All four statements agree: only the policy-clause path is
  a genuinely distinct source; orders/entitlements are a fresh read of the
  same store the agent already reads.
- **Receipt limitations** — consistent across `related-work.md`,
  `threat-model.md`, and `decision-receipt.md` (none of the three claims
  hash-chaining, immutability, or tamper-evidence across entries).
- **No novelty / superiority / production-readiness claim** — `README.md`
  §Verified release-candidate engineering semantics ("not evidence of
  research efficacy, external validation, broad generalization, production
  readiness or adversarial robustness"), `related-work.md`'s closing
  paragraph ("does not establish novelty, broad generalization, external
  validation, superiority over any named system, or production readiness"),
  and `threat-model.md`'s "Important non-goals" section all agree.

No inconsistency found. Nothing to correct for P10 consistency.

## Search firewall (final static search, this pass)

Full-file review (not grep-only, for the ambiguous high-volume terms "only",
"real", "current", "verified", "validated") plus a case-insensitive pattern
search for the complete task term list across all `.md`/`.txt` claim-bearing
files. Remaining hits, classified:

| File | Text (representative) | Class |
|---|---|---|
| `docs/threat-model.md` §Important non-goals | "does not establish or claim production readiness... non-bypassability, tamper-proof logging... zero-trust operation... guaranteed policy compliance" | 2 — negative/limitation |
| `docs/threat-model.md` §Relationship to research claims | "does not establish current-candidate attack resistance or security effectiveness" | 2 — negative/limitation |
| `docs/related-work.md` §Evidence and limitations (closing line) | "does not establish novelty, broad generalization, external validation, superiority over any named system, or production readiness" | 2 — negative/limitation |
| `docs/related-work.md` §Reason Less, Verify More | "NOT DIRECTLY COMPARABLE" | 2 — negative/limitation (explicit non-comparison marker) |
| `docs/related-work.md` §AgentLTL | "κ_ground... uses no external data source" (AgentLTL's own definition) | 4 — prior-art description |
| `docs/related-work.md` §Auditable Agents | "This is a self-assessment against an externally defined rubric, not an external audit, and it does not establish superiority" | 2 — negative/limitation |
| `docs/ROADMAP.md` (multiple, unchanged from prior audit) | "novelty claim" (as a section to write), "beats" (design-tradeoff phrasing), SEC 15c3-5 "non-bypassable pre-execution control" prior-art description | 4 — planning-document / prior-art description, with the document's own built-in caution against overclaiming from it |

**Zero category-5 (indefensible positive self-claim) occurrences.**

## Numbers, methodology, research results

No numeric value, methodology, or research result was changed, generated,
or regenerated by this task. No file other than this one was written or
modified.

## Unresolved issues

None identified. No number was found to be independently incorrect.
