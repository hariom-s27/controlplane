# What your plan is missing — and one strategic reframe

Your status document is, on the whole, better reasoned than the artifact it describes. What follows is not disagreement with its judgements; it is the set of things it does not contain.

---

## 1. You have not localised the fault, and you are about to pay for a model switch that may not be needed

Your plan goes: *zero tool calls in C1/C2* → *build a new tool-calling-capable track* → *new C1′*. That skips the diagnosis. Four layers could be responsible, and they have wildly different prices:

```
(a) MODEL     Kimi-K2-Instruct does not emit native tool calls on this route   → new model    (expensive)
(b) PROVIDER  Featherless does not surface them on this endpoint/route         → new provider (expensive)
(c) HARNESS   the tau2 agent class used does not pass tools / uses a solo mode → config       (free)
(d) ADAPTER   your integration drops or reshapes the tools array               → bug fix      (free)
```

Half the outcome space is free to fix. You cannot currently tell which half you are in.

### The discriminating probe — ~10 minutes, a few cents, run it before anything else

Outside τ² entirely. One direct request to the provider with one trivial tool schema:

| # | Request | Interpretation |
|---|---|---|
| P1 | model + 1 tool + a prompt that obviously requires it, `tool_choice` default | tool call returned ⇒ **(a) and (b) are cleared**; fault is (c) or (d), and free |
| P2 | same, `tool_choice="required"` (or the route's equivalent) | works ⇒ the fix is a **parameter**, not a new track |
| P3 | same request replayed through *your* wrapper / the τ² agent path | diverges from P1 ⇒ fault is **(d), your adapter** |
| P4 | one τ² retail tool schema verbatim, direct to the provider | fails where P1 succeeded ⇒ schema-shape incompatibility (nesting, `strict`, enum, `$ref`) — also a free fix |

Four outcomes, four different plans. **Do not commit to a new track until you have run this.** Archive all four request/response pairs as evidence — they are worth more than the C2 run.

## 2. Your zero-tool-call evidence is missing the request side

Your chain begins *"tools supplied to Kimi → raw response `tool_calls = null`."* The first arrow is currently your testimony. The reviewer's question is not "did the model refuse?" — it is **"did you actually send the tools, in the shape the provider expects?"** An empty `tool_calls` is exactly what a dropped or malformed `tools` array produces.

**Freeze one request/response pair with the `tools` array visible in the request and `tool_calls: null` in the response.** One request. It converts your central P06 finding from an assertion into evidence. Highest evidence-per-minute action available.

## 3. You have no preregistration for the next track — and this is the cheapest credibility you will ever buy

You correctly refuse to retro-preregister P12. The corollary is that the *next* track should be preregistered properly: a dated, hash-stamped file, committed before the first run, stating the configuration, the seed, K, the primary metric with its denominator, the analysis (paired, cluster-robust), the stopping rule, and the abort gates. Twenty minutes. It permanently forecloses "you reframed after seeing the results", which is the accusation your audit history makes you most vulnerable to.

## 4. Two deadlines are being managed as one

`CLAUDE.md` puts the Accenture Round 2 deadline at ~**6 September 2026**. Today is **31 August**. Six days.

Your plan interleaves submission work (P11 public reconciliation) with open-ended research (new C1′/C2′/C3′). Those have different clocks and different acceptance criteria, and mixing them is how both slip.

| Track | Deadline | Acceptance criterion | In scope |
|---|---|---|---|
| **SUBMISSION** | 6 Sept, hard | a public repo whose claims match its evidence | P11, retractions, README, threat model doc, narrowed positioning |
| **RESEARCH** | none | a defensible causal result | fault probe, gold-set A-ladder, new track, P10 |

Anything that is not on the submission track and not finishable by 4 Sept should be explicitly deferred, in writing, today.

## 5. The strategic reframe — your thesis does not need τ², and treating it as if it does is your biggest planning error

Read your own contribution statement again:

> *ControlPlane studies when runtime governance benefits from independently querying current system-of-record state rather than relying on evidence already available in the agent's execution context, and it measures the conditions under which that independence changes adjudication.*

Now ask what evidence that sentence actually requires. It requires **paired adjudications of the same case under different evidence sources**. It does not require a live agent. It does not require τ². It does not require a working native tool-call path.

You already have the design — A1 MessageOnly / A2 RetrievedOnly / A3 TraceOnly / A4 CachedRead / A5 LiveQuery. Run it over your **independently-labelled gold set**, offline, deterministically:

```
for each case:
    freeze the case's ground truth (holdout, never read by any arm)
    construct 5 evidence bundles from the SAME case
       A1  the agent's prose only
       A2  the retrieved context only
       A3  the trace / prior tool returns only        ← this is AgentLTL's out(τ)
       A4  a snapshot of the record taken at retrieval time  ← this is LedgerAgent
       A5  a fresh query at adjudication time
    adjudicate each bundle with the SAME decide()
    score all five against the independent label
report: paired disagreement rates, A5−A4 as the independence effect,
        cluster-bootstrapped over source_order_id
```

What this buys, all at once:

- **the causal contrast your thesis names**, properly identified: one variable changes (evidence source), everything else held fixed;
- **A5 − A4 is exactly the LedgerAgent boundary** and **A5 − A3 is exactly the AgentLTL boundary** — your related-work section becomes an *experiment* rather than a paragraph;
- **it cannot be blocked by a provider**, costs no tokens, and is deterministic;
- it makes the stale-policy question (your C3) answerable **without C3**: the `stale_policy_context` slice is already in the gold set, and A2/A4 vs A5 on that slice *is* the stale-context experiment;
- it directly attacks G3, because varying the evidence source is what makes "A5 is 100% by construction" testable rather than assumed.

**τ² then becomes what it actually is: an external-validity arm.** Valuable, unblocking nothing. If the tool-call path is fixable for free (probe outcome c/d), run it. If it needs a new model or provider, defer it past the deadline without losing the thesis.

The single most consequential sentence in this document: **you have been treating τ² as the experiment and the A-ladder as supporting material. It is the other way round.**

### Prerequisite, and it is the same prerequisite as everything else

The A-ladder is only meaningful with labels the gate did not produce. `bench/label.py` + the gold set + the AST independence test. Which is what my last audit said was the highest-value action, and it still is — now for a second, larger reason.

## 6. Things to check that neither of us has checked

1. **Does the τ² agent class you used support a non-native action protocol?** Many harnesses support a text/ReAct-style action format parsed into tool dispatch. If τ² does and you used the native-tool-call agent, then governed writes are reachable **with the same model and provider**. Check the public τ² agent API before assuming a model switch. *(Unverified — check, do not assume.)*
2. **τ²-bench-verified** (`amazon-agi/tau2-bench-verified`) exists because task/policy/DB misalignment was found in the original. If you re-run anything on τ², use the verified release and say which.
3. **Empty completions vs. empty tool calls.** Your earlier gate-condition evidence on the public repo shows Qwen3 returning entirely empty responses on 2 of 5 phrasings — a *different* failure from "content but no tool call". Distinguish these in the C1/C2 accounting; they have different causes.
4. **Was `max_tokens` set?** The public `agents/llm.py::chat` sets none, and the public evidence file attributes empty responses to reasoning-token budget exhaustion. If the τ² path has the same property, a thinking model can burn its budget before emitting the tool call. This is a plausible, cheap, testable cause of "no tool call" that sits in category (c)/(d) — free to fix.
5. **Score ControlPlane on the Auditable Agents five dimensions** (arXiv:2604.05485 §2): action recoverability, lifecycle coverage, policy checkability, responsibility attribution, evidence integrity. Honest self-scoring against a published rubric is a strong related-work table and costs an hour.

## 7. Three additions to your "what NOT to do" list

- ❌ **Do not switch model or provider before the fault probe.** You may pay for a config bug.
- ❌ **Do not call anything "frozen" that is not retrievable by a third party.** Ship the hash manifest first (`R00` §2.1).
- ❌ **Do not let the A-ladder wait on τ².** It is the experiment; τ² is the venue.

## 8. What I would drop from your plan entirely

| Item | Why |
|---|---|
| P13 Part B (write-level metrics, current track) | denominator is 0; you established this yourself |
| Same-config C3 | correct, keep it dropped |
| Retroactive P12 | correct, keep it dropped |
| The 5–6 h P02 architecture refactor | positioning defect; narrow the wording instead (`R00` §2.6) |
| A5-under-corruption, before the deadline | it is a *different estimand* from independence; the A-ladder is the higher-value use of the same hours |
| Multi-seed on any deterministic offline experiment | seeds answer stochastic-variation questions; these have no stochastic component |
| Broad adversarial benchmark | AEGIS and C-Trace both have real ones; you cannot win that comparison this week, and attempting it while two fail-opens stand measures the fail-opens |
