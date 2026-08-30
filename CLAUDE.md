# CLAUDE.md — project rules for the coding agent

Claude Code reads this file automatically at the start of every session in this
repo. You do not need to paste it into prompts. Keep it short and keep it true;
a stale rule here is worse than no rule.

---

## What this project is

ControlPlane is a **runtime verification layer for enterprise AI agents.** When
an agent proposes an action — `issue_refund(order_id, amount)` — we intercept
the tool call *before it executes*, extract the claims inside it, check those
claims against the enterprise's own live systems of record, and decide whether
to allow, modify, block or escalate. Every decision emits a signed evidence
receipt (measured median 2,282 bytes, p95 3,763 bytes over n=120).

The one-line positioning:

> Most AI checkers ask another AI for a second opinion.
> We ask the company's own systems for the actual answer.

This is a submission for the Accenture Innovation Challenge 2026, Round 2.
Deadline is roughly 6 September 2026.

---

## 🔴 The rule that carries the whole project

**The extractor produces CLAIMS. The registry produces FACTS. They never come
from the same place.**

- `ProposedAction.claimed_*` is what the *agent asserted*. It may be wrong. It
  may be `None`. Both are normal.
- The predicate engine reads `Evidence` objects whose `source` is a real system
  of record.
- `ProposedAction.facts_for_predicate()` returns **only** the fields that came
  structurally out of the tool call. Nothing else from that object may reach a
  predicate.

If you ever pass a `claimed_*` value into a predicate, you have rebuilt the
architecture we are arguing *against*, and the demo now proves the opposite of
what we want. **Do not do this even if it looks convenient.** If a task seems to
require it, stop and say so instead of writing it.

The slogan version, which is also literally true of the code:
**the verifier never reads a date.** The tool call carries an order ID; the
delivery date comes from `orders.db`, the seven-day window from
`policy_store.db`, and today from the clock.

---

## Hard constraints — do not violate without being asked

1. **Money is integer paise.** Never floats, anywhere. Format only at the render
   boundary.
2. **Time comes from `controlplane/registry/clock.py`.** Never `datetime.now()`
   inline. The demo clock is frozen at `CP_DEMO_DATE` so "26 days elapsed" stays
   26 forever and the recorded video does not go stale.
3. **No LLM-as-judge on the critical path.** It contradicts the project's own
   central argument (judges approve 96% of good answers and catch under 25% of
   bad ones). A model is the *last* resort, and when it is used the verdict is
   `UNVERIFIABLE`, not a confidence score.
4. **`decide()` in `controlplane/decide.py` must stay a pure function.** No I/O,
   no clock, no logging inside it. The metamorphic invariants and the mutation
   harness call it thousands of times, which only works if it is pure. It also
   must take no protected-attribute parameter — `tests/test_no_protected_attributes.py`
   enforces this structurally (the bias probe that used to live here was
   circular and was deleted; see `docs/experiment-audit.md`).
5. **Every dependency must be MIT or Apache-2.0.** The repo is public and licence
   hygiene is graded. Do not add a dependency without checking, and do not add
   one at all if stdlib will do.
6. **Instructor must be constructed with `Mode.JSON`, explicitly.** Its default
   is `Mode.TOOLS`, which returns silent empty objects on most Featherless
   models. Mode.JSON has its own quiet trap, paid for once in `controlplane/extract.py`:
   under load, Qwen3-8B sometimes wraps its answer as `{"YourModelName": {...fields...}}`
   instead of the flat shape asked for. If every field on your `response_model` has a
   `= None`/`= default` fallback, Pydantic treats the (then-absent) top-level keys as
   "not provided" and silently validates into an all-default object — **no exception**,
   so Instructor's retry loop never fires and you get a confident, wrong, empty result.
   Fix: make fields required-but-nullable (`x: T | None` with **no** `= None`) instead
   of optional-with-default, wherever "the model didn't say" must be *distinguishable*
   from "the key came back missing." That turns the wrap into a real validation error,
   which Instructor retries against and which does self-correct in practice.
7. **`data/build_db.py` must stay byte-deterministic.** Sorted inserts, fixed
   seed, no timestamps in the DB build. `tests/test_data.py` asserts it.

---

## How to work in this repo

- **Small, testable commits.** One component per change, with its test.
- **Write the test in the same change as the code.** Not after.
- **Cite the decision number in a comment** when you implement one — `# D2`,
  `# D49`, `# D52`. The register lives in `docs/` and it is how we answer "why
  did you build it that way" in the pitch.
- **When you are unsure, say so in the response rather than guessing in the
  code.** A `TODO` with a real question is more useful than a plausible
  invention. This project has already caught four fabricated figures in its own
  research; the same discipline applies to code.
- **Never invent a number.** If a docstring or README needs a measurement, run
  the thing and paste the real output, or leave it blank and say it is unmeasured.

---

## The pipeline, in order

```
[0] agent            agents/servicing_agent.py     proposes a tool call
[1] intercept        controlplane/intercept.py     dispatch_tool()  ← the choke point
[2] extract          controlplane/extract.py       Instructor, Mode.JSON
[3] classify         controlplane/ladder.py        Checkability Ladder C1..C5
[4] resolve          controlplane/registry/*.py    Evidence with query + freshness
[5] predicate        controlplane/predicates/      Zen Engine JDM graph
[6] ground           controlplane/ground.py        HHEM NLI, C3 only, optional
[7] verdict          controlplane/decide.py        4 verdicts
[8] intervene        controlplane/decide.py        5 interventions + compensability
[9] receipt          controlplane/receipt.py       signed JSON; median 2,282 B, p95 3,763 B
[10] telemetry       controlplane/telemetry.py     the four loggers
```

Read `docs/ROADMAP.md` for the full spec of each step, including inputs,
outputs, verification and fallbacks.

---

## Vocabulary — use these words, they are load-bearing

| Term | Means |
|---|---|
| **Checkability Ladder** | C1 recompute · C2 query record · C3 entail document · C4 consensus · C5 unverifiable |
| **Evidence Strength Hierarchy** | Never use a weaker method when a stronger one applies |
| **Load-bearing claim** | The 1–3 assertions the user will actually act on |
| **Decision Receipt** | The evidence artifact. Evidence, not a score. |
| **SOURCE-UNRELIABLE** | Fourth verdict class, for when the record itself is not trustworthy |
| **Compensability** | Fully / partially / not. A different axis from risk tier. |
| **Negative control** | The unmodified agent failing, with the gate off |
| **Manifest** | Per-use-case policy config. Same engine, different behaviour. |

---

## Things that are already decided — do not reopen

- Hand-rolled `dispatch_tool()` for interception. Portkey and LiteLLM expose
  only LLM-request hooks; neither fires on tool dispatch.
- Zen Engine for predicates (in-process, no sidecar to die mid-demo).
- SQLite ×3 for the stores. The liveness that matters is procedural, not
  infrastructural.
- FastAPI + HTMX for the reviewer console, not Streamlit — its rerun model
  fights the commit-then-reveal flow and can leak the verdict.
- HHEM-2.1-Open for grounding, MiniCheck-770M as an optional second checker.

---

## Good prompts for this repo

```
Implement S6 (the Ground Truth Registry) per docs/ROADMAP.md. Start with
registry/base.py and registry/orders.py only. Write tests/test_registry.py in
the same change. Do not touch decide.py.
```

```
Here is the failing output from `pytest tests/test_predicates.py -v`.
Diagnose it and propose a fix. Do not apply the fix until I say go.
```

```
Review controlplane/decide.py against rule 4 in CLAUDE.md — is it still a pure
function? List anything that would break the metamorphic invariants.
```

Bad prompts: "build the whole thing", "make it work", "add features".
Scope every request to one component and one test file.
