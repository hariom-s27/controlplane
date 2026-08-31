# P03-P05 conversation and repository handoff

**Status captured:** 2026-08-31 (Asia/Calcutta)

This is a durable, GitHub-ready summary of the user-visible work and decisions in
this conversation. It is not a verbatim transcript and intentionally excludes
secrets, API keys, `.env` values, hidden prompts, and unrelated personal data.

## 1. Executive status

- P03 produced the independent 150-case gold set. The gold set and construction
  holdout still match their original frozen hashes.
- P04 produced and froze the B0-B5 baseline table. The last P04-specific work in
  this conversation was documentation and `.gitignore` cleanup only; no P04
  experiment was rerun or retuned.
- P05 was stopped before implementation in this conversation because the frozen
  P03 records do not contain authentic customer messages, authentic prior agent
  tool outputs, or a genuine 200 ms historical store snapshot.
- A subsequent read-only audit found authentic demo recordings, but none map to
  the 150 P03 case IDs. Authentic mapping coverage remains 0/150 for both the
  customer-message and prior-tool-output channels.
- The current local repository now contains a separately created and committed
  P05 implementation at commit `b4ef009`. Its own README explicitly says its
  customer-message and agent-trace fixtures are synthetic. Under the user's later
  "only authentic, case-mapped evidence is acceptable" rule, those fixtures do
  not resolve the original A1/A3 blocker.
- No P03 or P04 artifact was edited while creating this handoff. This handoff is
  the only file added by the current request.

## 2. Current Git state

Repository:

```text
D:\sem_iitk\sem9\comp\accenture\phase 2\controlplanestarter\controlplane
```

Current branch and HEAD:

```text
branch: p03-m4-blind-human-label-sheet
HEAD:   b4ef009
title:  P02 hardening, P04-P05 baselines/ablation, P07 fixes, P08 robustness,
        P09 latency, onboarding measurement, and P06 preflight
```

Remote state observed from local refs:

```text
origin/main:                              6ec4261
origin/p03-m4-blind-human-label-sheet:    8a48bf7
local p03-m4-blind-human-label-sheet:     b4ef009 (ahead by 1 commit)
```

Therefore the large `b4ef009` integration is committed locally but is not shown
as pushed to `origin/p03-m4-blind-human-label-sheet` by the current tracking
metadata.

The worktree also contains unrelated, pre-existing P06/tau2 work. At capture
time, tracked modifications included:

- `controlplane/decide.py`
- `reports/tau2-bench.md`
- `schemas/manifest.schema.json`
- `tests/test_manifest_hardening.py`

There were also untracked P06/tau2 adapters, manifests, graphs, tests, and audit
documents. These are not part of the P03-P05 work summarized here and were not
modified for this handoff.

## 3. Conversation timeline

### P04 initial request

The user initially asked to read the authoritative P04 task, inspect P03 first,
then implement B0-B5 with:

- the same frozen P03 gold set for every baseline;
- no changed or invented labels;
- B4 and B5 structurally identical except for evidence strategy;
- at least three seeds and mean/range reporting;
- binary headline metrics on 140 non-ambiguous cases;
- a separate 10-case AMBIGUOUS panel;
- FPR on the 50 ALLOW cases;
- cluster-aware uncertainty because those 50 ALLOW cases use only five source
  orders;
- McNemar B4-vs-B5 testing plus a confidence interval;
- all P03 slices reported; and
- honest reporting when a component cannot run.

### P03-only audit request

The user then narrowed scope to a read-only P03 audit and explicitly prohibited
touching P04 work. The audit requirements covered independent labeling, exact
slice counts, holdout isolation, human-label sampling, determinism, clustering,
SOURCE_UNRELIABLE coverage, AMBIGUOUS policy interpretation, and leakage.

### P04 finalize-and-freeze request

The user later authorized only minimal P04 cleanup:

1. Change `.gitignore` from ignoring the whole `reports/` directory to:

   ```gitignore
   reports/*
   !reports/baselines.md
   !reports/summary.json
   ```

2. Add a sentence explaining that McNemar's p-value is paired-case-level while
   its confidence interval is a source-order cluster bootstrap, and that all 17
   discordant cases are singleton source-order clusters.
3. Add a sentence explaining the null-`delivered_at` Zen failure, the P04
   harness's safety-direction catch, and P08 ownership of the runtime fix.
4. Do not rerun, retune, or alter any P04 result.

That cleanup was completed. The reported validation at that point was:

```text
P04-focused tests: 18 passed
full pytest suite: 187 passed
```

These counts describe that frozen repository state; they are not a claim about
the current, much larger worktree.

### P05 execution request

The user requested a five-arm evidence-source ablation:

| arm | required literal source |
|---|---|
| A1 MessageOnly | the customer's message |
| A2 RetrievedOnly | the agent's retrieved chunks |
| A3 TraceOnly | the agent's own prior tool outputs |
| A4 CachedRead | a genuinely 200 ms-stale store read |
| A5 LiveQuery | an independent live query at decision time |

All arms were required to share one pipeline and differ only by the injected
`EvidenceStrategy`. The full required grid was:

```text
absence:   0%, 10%, 30%, 50%, 70%, 100%
staleness: 0%, 10%, 25%, 50%, 100%
seeds:     0, 1, 2 (at least three seeds)
cells:     5 arms x 6 absence x 5 staleness x 3 seeds = 450
```

The exact preregistered prediction requested by the user was:

> We predict that at 0% absence and 0% staleness, A3 and A5 are statistically
> indistinguishable, because when the fact is present and current in the agent's
> context, inheriting it and fetching it return the same value. We predict the
> gap opens approximately linearly in both variables. The crossover point —
> the level of context degradation at which independent re-query begins to pay —
> is the finding.

The user also explicitly required stopping instead of approximating any arm.

### P05 stop decision in this conversation

The current gate has a clean injection point:

```text
dispatch_tool
  -> extract_action
  -> build_claims
  -> classify_claims
  -> resolve_bindings       <-- replace only this with EvidenceStrategy.resolve
  -> build_predicate_payload
  -> Zen evaluate
  -> clause check
  -> decide
```

Structural isolation was feasible. The inputs were not:

- all 150 P03 records contained `justification` and `retrieved_chunks`;
- 0/150 contained `customer_message`;
- 0/150 contained a serialized prior tool-output/agent-trace channel;
- P03 defines `justification` as agent prose, not a customer message;
- `retrieved_chunks` are retrieval evidence, not prior tool outputs;
- the SQLite stores were current/static files without an existing timed
  200 ms snapshot mechanism.

The assistant stopped before editing, as required, rather than relabeling or
fabricating sources.

### P05 blocker-resolution audit request

The user then requested one read-only repository audit covering fixtures, logs,
transcripts, agent code, tests, benchmarks, DB history, cache snapshots, and
negative-control recordings. The user defined acceptable evidence as genuinely
recorded and mappable to the P03 case. Synthetic or reconstructed data was not
acceptable for the literal arms.

The audit was paused when the user requested this handoff document. Findings
completed before that pause are recorded in section 7.

## 4. P03: frozen experiment foundation

### Gold-set composition

| slice | cases | unique source orders | gold outcome |
|---|---:|---:|---|
| `allow_in_window` | 50 | 5 | ALLOW |
| `outside_window` | 20 | 20 | BLOCK |
| `over_authority` | 15 | 15 | BLOCK |
| `distractor_present` | 20 | 20 | BLOCK |
| `stale_policy_context` | 20 | 20 | BLOCK |
| `corrupted_or_missing_record` | 15 | 15 | ESCALATE |
| `ambiguous_under_policy` | 10 | 7 | AMBIGUOUS |
| total | 150 | 101 | mixed |

Label distribution:

```text
ALLOW=50, BLOCK=75, ESCALATE=15, AMBIGUOUS=10
```

Gold-verdict distribution:

```text
VERIFIED=50
CONTRADICTED=75
UNVERIFIABLE=10
SOURCE_UNRELIABLE=5
AMBIGUOUS=10
```

### Independence design

- `bench/label.py` imports nothing from `controlplane`.
- Labels are not produced by `decide`, predicates, the ladder, interception,
  or grounding.
- The independent labeler parses policy facts from clause prose in
  `policy_store.db`; the gate reads manifest scalars.
- This proves independent implementation/representation and catches drift. It
  does not prove independent authorship of the underlying policy intent.
- Construction truth is isolated in `bench/ground_truth_holdout.jsonl` and is
  not a checker input.

### Important P03 limitations

- The 50 ALLOW examples are 10 variants each of only five source orders.
- Confidence intervals must resample source-order clusters, not individual
  cases.
- Several BLOCK slices contain overlapping reasons, so correct intervention
  does not prove the named predicate fired.
- The ambiguous boundary and supervisor-discretion cutoff are the project's
  policy interpretation, not an uncontested ground truth.
- The servicing runtime originally did not exercise the five
  SOURCE_UNRELIABLE currency cases.
- Missing-record cases originally reached Zen with null `delivered_at` and
  could raise before `decide`; P08 owned that robustness fix.
- Some justification/slice wording leaks construction intent to prose-reading
  systems.

## 5. P04: frozen B0-B5 baseline

### Architecture

| baseline | architecture |
|---|---|
| B0 NoGate | unconditional ALLOW/execute |
| B1 RuleOnly | direct delivery-date read plus a hardcoded seven-day rule |
| B2 AuthOnly | identity/role plus static amount ceiling |
| B3 LLMJudge | one cached temperature-zero policy-judge call |
| B4 TraceGrounded | shared full pipeline with agent-context evidence |
| B5 ControlPlane | shared full pipeline with independent live registry queries |

B4 and B5 call the same `_run_our_pipeline(case, strategy)` implementation.
Only the injected evidence strategy differs.

### Headline P04 result

On the 140 non-ambiguous cases:

```text
B4 correct: 123/140 (87.9%)
B5 correct: 140/140 (100.0%)
B5 correct / B4 wrong: 17
B4 correct / B5 wrong: 0
McNemar exact two-sided p-value: 1.53e-05
accuracy difference: +12.1 percentage points
cluster-bootstrap 95% CI: [6.6, 19.7] percentage points
```

Sixteen discordances were stale-policy cases and one was a distractor case.
The p-value was computed over paired cases; the interval resampled public
source-order clusters. Each discordance was in a singleton source-order
cluster.

P04 also reported all 10 AMBIGUOUS cases separately and retained the original
ESCALATE/SOURCE_UNRELIABLE/UNVERIFIABLE vocabulary instead of collapsing it.

## 6. Hash ledger

### Original frozen hashes recorded earlier in this conversation

| artifact | original recorded SHA-256 |
|---|---|
| `bench/gold_set.jsonl` | `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e` |
| `bench/ground_truth_holdout.jsonl` | `204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb` |
| `bench/human_label_sample.csv` | `567abdd615edb1edc6eca7e2aa05b1c70bd926825b0aa9680471a9d3aa04ecfb` |
| `bench/label.py` | `04e4b5134b8814f8e40a3f6e9a97c4403fcf274974b76a237de4184e0ad37764` |
| `bench/baselines.py` | `fbb09ebaba1a7d436181f5e5692c45468234cda1b9dc8d70bd744a84b5664769` |
| `reports/baselines.md` | `24aefdfefcf92357d1419534152233fce43bf1addbf3a9cb0b92e39636b76751` |
| `reports/summary.json` | `a5ebf0e6c8d770daf7e535ea67bbe1232f38f74f9d4c4b4dac91c662f0db9d0c` |

### Current hashes at this handoff

| artifact | current SHA-256 | comparison |
|---|---|---|
| `bench/gold_set.jsonl` | `09deaecb374eb6b60bd03b95c90bbe1c8e3a75562eb9c59edc6c89970cd48c8e` | unchanged |
| `bench/ground_truth_holdout.jsonl` | `204e4a8e2af61d0aec109e0226018f4486451044f6de73e282f04aff7a24e3cb` | unchanged |
| `bench/human_label_sample.csv` | `ccf356a53088c4ae68562364cade01f0b02b2da6ab7daf1f206b943027c22d91` | changed by later blind-sheet work |
| `bench/label.py` | `04e4b5134b8814f8e40a3f6e9a97c4403fcf274974b76a237de4184e0ad37764` | unchanged |
| `bench/baselines.py` | `fbb09ebaba1a7d436181f5e5692c45468234cda1b9dc8d70bd744a84b5664769` | unchanged |
| `reports/baselines.md` | `eb35dbd089c2423edfc9293cbee00d81ed8944e7b2495ff4a82ed5dc90056c2e` | changed after earlier freeze snapshot |
| `reports/summary.json` | `17631b3d82e1cbd31819fac9c8f57d46332ba45c47ac0bf9b052d2c984e7e238` | expanded/changed after P05+ integration |

The gold set, holdout, independent labeler, and P04 executable baseline remain
byte-identical to the earlier frozen versions. The human sheet and reports have
later repository history and must not be described as byte-identical to the
earlier snapshot without explaining that history.

## 7. Read-only missing-channel audit findings

The classification rule used here is stricter than "the file contains similar
text." For literal P05, a usable source must be both genuinely recorded and
provably mappable to a P03 case ID.

| candidate source | what exists | provenance classification | maps to all 150? |
|---|---|---|---:|
| `bench/gold_set.jsonl` | tool call, session, agent justification, retrieved chunks | P03-constructed benchmark data; no customer-message or prior-tool-output channel | no (0/150 for each missing channel) |
| `data/fixtures/b3/*.json` | 150 cached B3 judge outputs keyed by `gs-001`…`gs-150` | authentic cached judge responses, but they are downstream judgments, not original messages or prior tool results | no |
| `data/fixtures/extract/*.json` | extracted claim-field responses | cached extraction outputs; original request/channel is not serialized in these files | no |
| top-level `data/fixtures/*.json` | recorded LLM completions with assistant reasoning/tool proposals | genuine recordings for demo/negative-control runs, but trace IDs/orders do not correspond to the P03 cases | no |
| `docs/evidence/negative_control.txt` | five recorded refund proposals | authentic summary for one demo scenario (`ORD-88461`, `CUST-2291`), not a 150-case P03 corpus; no prior tool-result history | no |
| `docs/evidence/gate_condition_check.txt` | retired/corrected gate-condition narrative | documentation, not case-level message/trace evidence | no |
| `decisions.jsonl` | 133 local receipt/log lines, four unique trace IDs | generated and untracked; contains gate evidence/query outputs but no customer messages or prior agent tool outputs; zero `gs-*` trace IDs | no |
| `agents/servicing_agent.py` | constructs user messages, order context, policy retrieval, and proposed tool call | executable construction path, not a recording of P03 interactions | no |
| `tests/**` and `bench/**` | templates, generated cases, expected values, synthetic fixtures | synthetic/reconstructed test or benchmark material unless independently recorded elsewhere | no |
| `data/stale_index/chunks.json` | both current v4.2 and superseded v3.8 policy chunks | deliberately stale retrieval corpus; not an agent prior-tool trace and not a timed store snapshot | no |
| `data/orders.db`, `data/policy_store.db` | current state plus effective-date policy rows | authoritative/current data and historical policy records, but no existing point-in-time 200 ms snapshot pair | no |

Important nuance: the top-level LLM fixtures and negative-control transcript are
genuine recordings for their own demo runs. They are still unusable for literal
P05 because they cannot be mapped to the P03 case IDs. They should not be called
synthetic, but they also do not meet the user's acceptable-A criterion.

### Mapping conclusion

```text
authentic customer messages mappable to P03:       0/150
authentic prior tool outputs mappable to P03:      0/150
genuine existing 200 ms snapshot mechanism:        none found
```

## 8. Current repository P05 artifacts discovered after the stop

Commit `b4ef009` contains:

- `bench/evidence_ablation.py`
- `bench/fixtures/p05/README.md`
- `bench/fixtures/p05/context_fixtures.jsonl`
- `docs/p05-methodology-audit.md`
- `reports/evidence-ablation.md`
- `reports/evidence-ablation-absence.png`
- `reports/evidence-ablation-staleness.png`
- `tests/test_evidence_ablation.py`
- a `p05_evidence_ablation` block in `reports/summary.json`

Current P05 hashes:

| artifact | SHA-256 |
|---|---|
| `bench/evidence_ablation.py` | `099bf5d15bd20f30de32ca24ea71a5f6438f758d84cb3d2eab2cf13490e51132` |
| `bench/fixtures/p05/context_fixtures.jsonl` | `c9cd423e20b76aa04168d5a28ba76499d01b500e6e5de70e2bf172cab1327877` |
| `reports/evidence-ablation.md` | `75e55c031d72e30fa6afea48ea585d5999d16c59be9f04e7e7d2d1d73c33aea8` |
| `tests/test_evidence_ablation.py` | `528925b9cf3902dd6a12f135699984e15f41142681d2309ec28e7b97f2f1a050` |

The fixture README states explicitly:

```text
context_fixtures.jsonl is synthetic and generated deterministically from the
frozen P03 gold set plus the current stores.
```

It constructs:

- a synthetic customer message;
- synthetic `get_order`/`get_policy` trace steps; and
- retrieved order-record chunks.

This is transparent and reproducible, but it does not satisfy the user's later
requirement that A1 and A3 use existing authentic evidence rather than fabricated
channels. It must be described as a synthetic-channel ablation, not as an
ablation over authentic P03 messages/traces.

The current repository report gives these results:

```text
A3 vs A5 at 0% absence / 0% staleness: parity at 100%
absence crossover (5-point gap):       11.7%, 95% cluster-bootstrap CI [6.6%, 34.4%]
staleness crossover (5-point gap):     40.0%, 95% cluster-bootstrap CI [9.9%, 67.0%]
A4 and A5 at the specified 200 ms:     both 100% on the frozen dataset
```

These are repository-reported measurements. They were not rerun while creating
this handoff. Their interpretation is conditional on accepting the synthetic
P05 input channels, which the user's latest audit rule does not currently allow.

### A4 caveat in the current implementation

The current P05 code creates separate replica files and can demonstrate a real
value difference when the modeled replication lag crosses the 2026-08-01 policy
cutover (14 days or more). At the specified 200 ms point, however, the replica
and live store return the same values because no store mutation occurred in that
window. The report calls the 200 ms lag modeled and adds it to timing without a
sleep.

That is useful sensitivity analysis, but it does not satisfy the user's stricter
request for an actually measured 200 ms snapshot age with an observable state
difference at that age. This needs an explicit approval/fixture decision before
claiming the literal A4 requirement is closed.

## 9. Minimum additional P05-only data required

### A1 and A3

No code-only reconstruction can make missing historical messages or traces
authentic. The minimum defensible route is a prospective P05-only capture:

1. Preserve the 150 P03 IDs, actions, and labels unchanged.
2. For each case, collect an actual customer/user turn through a declared data
   collection protocol rather than rendering it from `justification`.
3. Run the agent's actual read tools and persist the exact requests and results
   before the mutating proposal.
4. Store case ID, trace ID, timestamps, tool name/arguments/result, source-store
   hashes, model/settings, and the raw user turn.
5. Cryptographically pin the resulting P05-only corpus and publish a complete
   case-to-provenance index.
6. Keep this corpus outside P03 and document that it was collected prospectively
   for P05, not recovered from P03.

If genuine user turns cannot be collected, A1 must remain blocked. If actual
agent read-tool executions cannot be recorded, A3 must remain blocked. Calling a
generated template "authentic" after recording it would not solve the
provenance problem.

### A4

The minimum isolated temporal fixture, not yet authorized for implementation:

1. Create temporary P05-only primary and replica SQLite stores from copies of
   the production seeds; never edit `data/orders.db` or `data/policy_store.db`.
2. Take the replica snapshot through SQLite's backup API and record a monotonic
   snapshot timestamp and content hash.
3. Commit a known update to the temporary primary after the snapshot.
4. At decision time, verify with a monotonic clock that the snapshot is at least
   200 ms old.
5. Query A4 only from the earlier replica and A5 only from the updated temporary
   primary.
6. Assert an observable value difference, distinct DB paths, distinct hashes,
   and the measured age in every run record.
7. Delete or retain the temporary fixture according to a declared reproducible
   build protocol; never call a timestamp rewrite or a sleep alone "staleness."

This would be a clearly labeled P05 synthetic temporal fixture. It would satisfy
the requested A4 semantics without touching frozen or production stores, but it
must not be implemented until the user approves it.

## 10. Files that must remain untouched

The following frozen artifacts remain outside any proposed P05 repair:

- `bench/gold_set.jsonl`
- `bench/ground_truth_holdout.jsonl`
- `bench/human_label_sample.csv`
- `bench/label.py`
- `bench/baselines.py`
- `reports/baselines.md`
- all existing P04 result/metric data inside `reports/summary.json`
- every P03 label, case ID, tool call, and hash-governed construction artifact
- every P04 prediction, threshold, seed result, McNemar result, confidence
  interval, and B4/B5 architecture

Any future P05-only fixture should live under an explicitly named P05 path and
must never overwrite these inputs.

## 11. GitHub review checklist

Before pushing or merging the current local integration:

1. Decide whether P05 is allowed to be a clearly labeled synthetic-channel
   ablation. If not, do not present the current A1/A3 result as satisfying the
   literal task.
2. Decide whether A4 needs an observable state difference specifically at
   200 ms. If yes, authorize the isolated temporal fixture design first.
3. Reconcile the current branch (`b4ef009`) with `origin/main` (`6ec4261`) and
   the uncommitted P06 work; do not blindly merge the 278-file integration.
4. Recompute and document the intended frozen hash ledger, especially the
   changed blind human-label sheet and later report changes.
5. Run focused P03/P04/P05 tests and then the full suite only after the branch
   and fixture semantics are settled.
6. Run `git diff --check` and review all untracked files before staging.
7. Confirm that no `.env`, API key, operational receipt log, or local database
   artifact is staged.

## 12. Current decision gate

No new P05 fixture should be created automatically.

The next required decision is one of:

- approve a synthetic P05-only context corpus and explicitly narrow the claim;
- authorize prospective authentic message/trace collection for A1/A3;
- keep A1/A3 blocked and run only the arms whose evidence provenance is real;
- authorize the isolated, observably divergent 200 ms temporal fixture for A4;
  or
- leave P05 blocked.

Until that decision, the honest status is:

```text
P03 gold/holdout/labeler: frozen and usable
P04 executable baseline: frozen and usable
P05 current repository implementation: reproducible synthetic-channel ablation
P05 literal authentic-channel experiment: blocked
```
