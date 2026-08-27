# ControlPlane

**A runtime verification layer for enterprise AI agents.** When an agent
proposes an action, we intercept the tool call *before it executes*, check the
claims inside it against the enterprise's own live systems of record, and
decide whether to allow, modify, block or escalate — emitting a signed
evidence receipt for every decision.

> Most AI checkers ask another AI for a second opinion.
> We ask the company's own systems for the actual answer.

Accenture Innovation Challenge 2026 · Problem Track 1 · Round 2

---

## Quick start

**Windows**

```powershell
git clone <repo-url>
cd controlplane
.\make.ps1 setup      # venv + install + build the databases
.\make.ps1 probe      # check your LLM provider works
.\make.ps1 test       # 8 tests should pass
.\make.ps1 negative   # the agent fails, with the gate OFF
.\make.ps1 demo       # the gate catches it
```

**macOS / Linux** — same, with `make setup`, `make probe`, and so on.

You do **not** need an API key to run the demo: LLM responses for the demo
scenarios are cached as committed fixtures. Set `CP_MODE=live` in `.env` to
call the provider for real.

---

## Implementation approach

*(fill in from docs/ROADMAP.md §3 as the build lands)*

## Solution architecture

*(fill in — the eleven-stage pipeline diagram)*

## Dependencies

Every dependency is MIT or Apache-2.0; see `requirements.txt` for the
per-package licence. Two libraries were deliberately excluded on licence
grounds **before** we knew a public repository would be required:
Bespoke-MiniCheck-7B (CC BY-NC) and SDV (BUSL-1.1).

## Execution instructions

*(fill in)*

## Honest limitations

*(fill in — and keep this section. It is the most credible thing in the repo.)*

---

## Repository map

| Path | What it is |
|---|---|
| `controlplane/` | The product. The gate, the registry, the receipt. |
| `agents/` | Two demo agents — servicing, and an internal knowledge assistant. |
| `data/` | Committed JSON seeds + a deterministic database builder. |
| `manifests/` | Per-use-case policy configuration. Same engine, different behaviour. |
| `bench/` | SEB-1 and the measurement harnesses. |
| `docs/` | Architecture, receipt schema, invariants, limitations, evidence. |
| `tests/` | Unit, golden-file, metamorphic and mutation tests. |

## Reproducibility

Everything is seeded at `CP_SEED=20260814` and the demo clock is frozen at
`CP_DEMO_DATE=2026-08-14`. `python data/build_db.py` produces byte-identical
databases on every run — `tests/test_data.py` asserts it. If you run this
code you should get the numbers we published; if you do not, that is a bug and
we want to hear about it.
