# C. G1 — generality / scale assessment

## What varies, and what does not

| Axis | Count | Detail |
|---|---|---|
| Domains | **2** | customer servicing (`issue_refund`), internal knowledge assistant (`send_document`) |
| Tools governed | **2** | `_CLAIM_KINDS_BY_TOOL` in `controlplane/extract.py` has exactly two rows |
| Manifests | **2** | `manifests/servicing.yaml`, `manifests/knowledge_assistant.yaml` |
| Manifest fields that actually change behaviour | **4 of 9** | `window_days`, `authority.<role>.ceiling_paise`, `reliability_floor`, `verdict_handling`. Unread by any code: `latency_budget_ms`, `escalation_budget_pct`, `fail_posture`, `evidence_retention_days`, `risk_tier_default` |
| Predicate graphs | **2** | `servicing.json` = 6 expressions; `knowledge_assistant.json` = **2 identity aliases** |
| Source-of-truth types | **1** | SQLite, ×3 files (`orders.db`, `policy_store.db`, `entitlements.db`), all built by one script from committed JSON |
| Claim kinds | **11** | `ClaimKind` in `schema.py` |
| Datasets | **1** | `data/seed/*.json` → 109 orders (3 hand-authored + deterministic filler), one policy corpus, one entitlement set |
| Seeds | **1** | `CP_SEED=20260814`, hard-coded as the default in `build_db.py`, `mutation.py`, `bias_probe.py`, both bench scripts and `report.py` |
| Clock | **1, frozen** | `CP_DEMO_DATE=2026-08-14` |
| Models | **1** | `Qwen/Qwen3-8B` via Featherless (`.env.example`), and in the default `CP_MODE=fixture` the model is **replayed from committed fixtures**, not called |
| Evaluators | **0 external** | every scorer is in-repo |

## The knowledge-assistant "second domain" is thinner than it reads

`README.md` presents use case 2 as the generality evidence ("Same engine, different behaviour"). Inspection narrows this considerably:

1. `controlplane/predicates/graphs/knowledge_assistant.json` contains two expressions: `"classification_permitted": "evidence.classification_permitted"` and `"recipient_entitled": "evidence.recipient_entitled"`. Both are **identity functions**. No rule is evaluated in the graph.
2. The actual entitlement logic lives in `controlplane/registry/entitlements.py` as Python (`doc["classification"] in entitled_classifications`; `doc["about_customer_id"] in entitled_customers`). The resolver therefore returns a **verdict-shaped boolean**, in direct contradiction of `registry/orders.py`'s stated contract ("Each Evidence's value is the raw resolved FACT … never a verdict").
3. Neither `window_days` nor `authority.ceiling_paise` is referenced by the knowledge-assistant graph, so of the four functional manifest fields, only `reliability_floor` and `verdict_handling` differentiate the two use cases at runtime.

→ The second use case demonstrates that **the pipeline's plumbing is tool-agnostic**. It does not demonstrate that the *rule layer* generalises, because for use case 2 there is no rule layer.

## Model dependence

`CP_MODE=fixture` is the default, and `agents/llm.py::chat` raises rather than calling the network when no fixture exists. In the shipped configuration, **the LLM is a replay of 15 committed JSON fixtures** (`data/fixtures/*.json`, `data/fixtures/extract/*.json`). Nothing in the repository measures the pipeline against a second model, and nothing measures variance across repeated sampling of the same model — `temperature=0.0` plus a content-hash cache makes repeat calls free but also makes them the same call.

`docs/evidence/gate_condition_check.txt` (3/5 phrasings proposed a refund) is the only evidence of behaviour across prompt variation. It is n=5, one model, and the script that produced it does not run against the current code (`15_reproducibility.md`, D-R1).

## Evaluator dependence

Every accuracy number is scored by code in the same repository that produces the prediction, and — critically — by code that shares the *defining variable* with the gold label. See `11_information_flow_leakage.md`.

The unmerged branch's `bench/label.py` is designed precisely to break that, by re-deriving thresholds from clause **prose** in `policy_store.db` rather than the scalar in the manifest. That is a genuine, well-designed independence mechanism. **It is not committed.**

## Would repeated seeds change the inference?

**No, and this is important to state plainly rather than recommending seeds for the sake of it.**

For Exp 3, Exp 5, the mutation corpus and the bias probe, the mapping from generator variable to gold label to prediction is deterministic and total (`13_quantitative_estimand.md`). Changing the seed changes *which* cases are drawn, not the accuracy: Exp 5 and mutation are 1.000 for every seed; Exp 3's "without check" figure converges to `1 − P(wrong resolution)`, whose expectation is fixed at 0.25 by two hard-coded `rng.random() < 0.5` draws. Multi-seed runs would report a binomial jitter around a number that is analytically known.

→ **Adding seeds here would be statistical decoration on a tautology.** §18 records this as `NO ADDITIONAL SEEDS REQUIRED` for exactly this reason — the estimand is degenerate, not the sample small.

## GENERALITY CLAIM LADDER

| Level | Definition | Met? | Evidence |
|---|---|---|---|
| **0** | One internal setup | **YES** | servicing gate end-to-end, `intercept.py` → `receipt.py` |
| **1** | Repeated cases within one setup | **PARTIAL** | n=200 in Exp 3 / mutation, n=200 in Exp 5 — but all synthetically generated by the scorer's own code, so "repeated cases" without independent variation. The branch's 150-case gold set would satisfy Level 1 properly; it is not committed, and its ALLOW slice is 50 cases on **5 source orders** (`docs/gold-set.md` §2) |
| **2** | Independent external benchmark | **NO** | no external dataset, benchmark, evaluator or scorer exists in any commit |
| **3** | Multiple policies / domains | **PARTIAL, weak** | 2 manifests, 2 tools; but the second domain's rule layer is two identity aliases and only 2 manifest fields differentiate behaviour |
| **4** | Cross-domain generalisation | **NO** | no held-out domain; both domains were authored together against the same seed data |
| **5** | Broad generality | **NO** | — |

**Placement: Level 0, reaching toward Level 1.** The repository's own `docs/gold-set.md` §5 states the same conclusion in its own words ("Single domain. One tool (`issue_refund`), one manifest").

## Generality claims that are currently unsupported

| Claim as written | Where | Status |
|---|---|---|
| "A runtime verification layer for **enterprise** AI agents" | `README.md` line 3 | **NOT ESTABLISHED.** One synthetic retailer, three SQLite files, 109 rows |
| "check the claims inside it against the **enterprise's own live systems of record**" | `README.md` line 4 | **PARTIALLY ESTABLISHED.** "Live" here means a fresh read of the same SQLite file at decision time. For orders, the agent read the *same file* (`agents/servicing_agent.py::_recent_orders`). See `12_causal_identification.md` |
| "Same engine, **different behaviour**" | README, both manifests' header comments | **PARTIALLY ESTABLISHED** — 2 of 9 manifest fields differentiate use case 2 |
| "the four loggers" | README, `telemetry.py` | **PARTIALLY ESTABLISHED** — logger 2 is `"status": "not_measured"` by design, which the repo states honestly |

## §18 multi-seed decision, per experiment

| Experiment | Decision | Evidence-based reason |
|---|---|---|
| Exp 3 (cross-validation) | **NO ADDITIONAL SEEDS REQUIRED** | Estimand is degenerate; both arms are analytic functions of one generator variable. Seeds cannot repair construct invalidity |
| Exp 5 (confusion matrix) | **NO ADDITIONAL SEEDS REQUIRED** | Accuracy is 1.000 for all seeds by construction |
| Mutation corpus | **NO ADDITIONAL SEEDS REQUIRED** | Score is 1.000 for all seeds; already correctly framed as a regression signal |
| Bias probe | **NO ADDITIONAL SEEDS REQUIRED** | Null is structural, not sampled |
| Gold-set-scored Exp 5 (*if `label.py` is committed*) | **USEFUL BUT OPTIONAL**, and **cluster-robust resampling is required before more seeds are** | `docs/gold-set.md` §2 states the ALLOW slice is 50 cases on 5 source orders; the correct first move is a case-cluster bootstrap over `source_order_id`, not more seeds |
| Latency percentiles | **SCIENTIFICALLY REQUIRED** if any latency figure is ever published | `bench/report.py` currently charts n=1 per bar from three hard-coded constants |
