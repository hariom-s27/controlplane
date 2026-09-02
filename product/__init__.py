"""Product-facing views over the real ControlPlane decision pipeline.

CLAUDE.md #21 / MASTER-11-15 section 21 (no duplication): every function in
here is a thin renderer over the existing `controlplane/` engine and
`bench/baselines.py` case-loading helpers. Nothing here re-implements
predicate evaluation, evidence resolution, receipt signing, or idempotency —
it only reads the `Decision`/receipt objects those modules already produce.

MASTER-11-15 section 19/20 (research/product firewall): this package is
read-only with respect to research state. It never writes to `bench/`,
`reports/`, `manifests/`, gold/holdout files, or any P01-P09/P06 artifact.
The only writes are its own `decisions.jsonl`/`decisions_privileged.jsonl`
(via the existing `controlplane.receipt.persist`, same as any other run) and
files under `product/out/`.
"""
