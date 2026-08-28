# The Decision Receipt — S10

A ~1 KB signed JSON artifact per governed decision, appended to
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
