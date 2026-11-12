# The Decision Receipt — S10

A signed JSON artifact per governed decision (measured median 2,282 bytes and
p95 3,763 bytes over 120 receipts), appended to
`decisions.jsonl`. This is the brief's "clear audit trail behind every
decision" made literal, and the single most demoable artifact in the repo —
the thing that goes on screen and makes a judge understand the entire pitch
in four seconds.

Shaped in the spirit of the W3C PROV vocabulary (Entity/Activity/Agent,
`wasDerivedFrom`, `wasAttributedTo`) rather than a bespoke schema: the
proposed action is the Activity; the claims and evidence are what its
verdict `wasDerivedFrom`; the session is who it `wasAttributedTo`. Inheriting
a decade of prior art beats inventing a schema that only this repo
understands.

## Two tiers (D11)

The **operational trail** (`decisions.jsonl`) is what `controlplane/receipt.py`
builds and signs above — discoverable, and holds everything a receipt needs
to defend a decision to a customer, an auditor, or a regulator: the query
that was run, the value it returned, the rule that fired, the root cause.

The **privileged trail** (`decisions_privileged.jsonl`) is a separate file
for a separate purpose: bias probes, counterfactual twins, and red-team
results generated while testing the gate, not while operating it. This
split is driven by the *Mobley v. Workday* privilege ruling — testing
artifacts that expose how a system was probed for bias are the kind of
material a plaintiff's discovery request goes looking for, and mixing them
into the same trail a customer's own dispute would surface is a real legal
exposure, not a hypothetical one. `receipt.persist()` only writes to the
privileged file when there's something privileged to say; most decisions
write to the operational trail alone.

## Signing

HMAC-SHA256 over the receipt's canonical JSON form — sorted keys, no
whitespace (`json.dumps(..., sort_keys=True, separators=(",", ":"))`) —
computed before the `sig` field is added, so verification re-derives the
same bytes. The key comes from `CP_RECEIPT_SECRET` in `.env`; a real
deployment would source it from a secret manager, not a dotfile.

## Verification coverage (P1)

Two fields say two different things and must not be confused:

- `verification_state` (`verified` / `unverified`) — the *receipt-and-verdict*
  story: is this a decision the gate could stand behind, or one it reached
  under a source outage / ambiguity. It is not affected by how many claims
  were checked.
- `verification_coverage` — the *scope of factual checking* behind the
  action: `verified` load-bearing verification-eligible claims over the total
  `eligible` load-bearing claims, plus `coverage` (the ratio, `null` when
  `eligible` is 0 — never `1.0`), `coverage_basis` naming that denominator
  population, and the four non-verified counters (`contradicted`,
  `unverified`, `unavailable`, `unmodelled`).

Each entry in `claims[]` also carries a `verification` field, so the coverage
number can be recomputed from the receipt and checked against the stored
value. It is a plain status string in the common case
(`"verification": "verified"`) and a dict —
`{status, modelling?, eligible?, reason?}` — only when the extra fields carry
information (an `unmodelled` claim, a `not_eligible` tier, or a `reason` that
is not just a restatement of the status). `status` is one of `verified` /
`contradicted` / `unverified` / `unavailable` / `not_eligible`; only
`verified` counts toward coverage. See `docs/verification-coverage.md` for
the full definition and what the metric does *not* mean.

Both are covered by the signature: the block is assembled before `sig`. A
receipt written before P1 (or a hand-built `Decision` with no claims) has
`verification_coverage: null` and no per-claim `verification` block, and
still verifies.
