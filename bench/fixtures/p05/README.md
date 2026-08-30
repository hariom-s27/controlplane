# P05 context fixtures — provenance

`context_fixtures.jsonl` is **synthetic** and generated deterministically by
`bench/evidence_ablation.py::build_context_fixtures()` from the FROZEN P03
gold set + `data/orders.db` + `data/policy_store.db`. It is committed and
SHA-pinned in `tests/test_evidence_ablation.py`.

Why it exists: a P03 gold case has no authentic customer-message field and
no serialized tool trace. P05's arm definitions need both, so they are
constructed here — clearly labelled synthetic, identical construction for
every arm.

Per case:

- **customer_message** — SYNTHETIC. A plausible support message. The delivery
  date and order total are the true values from the order record (a real
  customer knows when their parcel arrived and what they paid); the absence
  sweep removes them. No policy text — customers do not cite clause versions.
- **retrieval_chunks** — the current v4.2 refund clause, the authority clause,
  and a retrieved order-record snapshot. The staleness sweep swaps the clause
  for the v3.8 text; the absence sweep drops the order snapshot.
- **agent_trace** — `get_order` + two `get_policy` calls with the results the
  agent received earlier in its trajectory (accurate as of fetch time). The
  absence sweep drops the `get_order` step (the agent never called it); the
  staleness sweep rewrites the `get_policy('refund_window')` result to
  version v3.8 / window 30.

NOT derived from and NOT affecting: the gold label, the tool-call args, the
P03/P04 artifacts, `decide.py`, the predicate graph, or the manifest.

Current clause: v4.2 / 7d. Superseded: v3.8 / 30d (effective_to 2026-08-01).
