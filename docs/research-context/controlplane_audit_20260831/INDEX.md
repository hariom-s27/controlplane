# ControlPlane — hostile peer-review audit

Read-only forensic audit of `github.com/hariom-s27/controlplane`, `main` @ `42143cf`, 2026-08-30.
No test, benchmark, experiment or provider call was executed (§0 honoured).

**Read `00` first, then `03` — the brief's premise does not match the repository, and `03` explains what that changes.**

| File | §32 section | What it covers |
|---|---|---|
| `00_executive_conclusion.md` | A | The headline, the verdict by evidence class, the three sentences a reviewer will write |
| `01_method_scope_and_limits.md` | — | What was inspected, §1A history discipline, the cost of read-only, the three internal contradictions |
| `02_evidence_ledger.md` | B | Full claim ledger: architecture, numeric, literature, and the brief's own premise |
| `03_premise_reconciliation.md` | — | **τ² / AgentLTL / P02–P09 / C1–C3 / A1–A5 / frozen evidence: all absent.** What is executable and what is not |
| `04_G1_generality.md` | C | Domains, seeds, models, evaluators; the generality claim ladder; §18 multi-seed decisions |
| `05_G2_external_validation.md` | D | Component-by-component third-party audit; the 77.4% attribution problem |
| `06_G3_falsifiability.md` | E | The 100%-by-construction defect ×4; the M5 bug (§10); what is actually falsifiable |
| `07_G4_agentltl_primary_source.md` | F | arXiv:2607.02599v1 — κ_ground, witness requirement, §8 limitations verbatim; the comparison |
| `08_prior_art_matrix.md` | H + §8A | Reddy et al., OAP, Aegis, Policies-on-Paths, C-Trace, AgentCore Policy, Automated Reasoning checks, observability platforms; adversarial challenge |
| `09_G5_threat_model.md` | G | 17 threats; two confirmed fail-opens |
| `10_benchmark_construct_validity.md` | I | DATA→LABEL→PREDICTION→DECISION→SCORE for every benchmark |
| `11_information_flow_leakage.md` | J | Where the label reaches the prediction |
| `12_causal_identification.md` | K | What variable is actually changed; source independence vs re-derivation |
| `13_quantitative_estimand.md` | L | Every number, its numerator, denominator, and label (MEASURED/DERIVED/REPORTED) |
| `14_statistical_multiseed.md` | M | Determinism vs generalisation; why seeds are the wrong fix; clustering |
| `15_reproducibility.md` | N | What is pinned; three reproducibility breaks; the weakest link |
| `16_hostile_reviewer_objections.md` | O | 20 objections ranked, plus 5 a reviewer might raise that are invalid |
| `17_experiment_value_ranking.md` | P | The brief's list evaluated, then what the repository actually generates |
| `18_research_debt_register.md` | Q | 28 debts with cost, risk, deadline relevance and status |
| `19_claim_positioning_corrections.md` | R | 12 corrections; the claims worth keeping verbatim |
| `20_contribution_statement.md` | S + T + §28 | Atomic decomposition; safe now; stronger later; what not to claim |
| `21_top_three_resource_decisions.md` | U | Do this, then this, and do not do that |
| `22_final_gap_closure_matrix.md` | V | Every gap with its minimal closure and final decision |
| `23_independent_reader_reconstruction.md` | §25 | Can a skeptic rebuild it? |
| `24_final_hostile_review_gate.md` | §31 | This audit attacking its own conclusions; surviving counterarguments |
| `99_RESEARCH_GAP_DECISION.md` | §33 | **The decision** |

## Primary sources fetched (2026-08-30)

- AgentLTL — [arXiv:2607.02599](https://arxiv.org/abs/2607.02599) · [full text](https://arxiv.org/html/2607.02599v1)
- Reason Less, Verify More — [arXiv:2607.07405](https://arxiv.org/abs/2607.07405)
- C-Trace / Runtime Compliance Verification for AI Agents — [arXiv:2606.19242](https://arxiv.org/html/2606.19242)
- Before the Tool Call (Open Agent Passport) — [arXiv:2603.20953](https://arxiv.org/abs/2603.20953)
- Aegis — [arXiv:2603.16938](https://arxiv.org/abs/2603.16938)
- Runtime Governance for AI Agents: Policies on Paths — [arXiv:2603.16586](https://arxiv.org/html/2603.16586v1)
- Toward Safe LLM Agents (survey) — [arXiv:2608.14590](https://arxiv.org/html/2608.14590)
- Amazon Bedrock AgentCore Policy — [core concepts](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-core-concepts.html)
- Bedrock Automated Reasoning checks — [concepts](https://docs.aws.amazon.com/bedrock/latest/userguide/automated-reasoning-checks-concepts.html)
- LLM-AggreFact leaderboard — [llm-aggrefact.github.io](https://llm-aggrefact.github.io/)
- USPS OIG report 22-159-R23 — [Package Tracking Messaging](https://www.uspsoig.gov/reports/audit-reports/package-tracking-messaging)
- τ²-bench — [arXiv:2506.07982](https://arxiv.org/pdf/2506.07982) · [tau2-bench-verified](https://github.com/amazon-agi/tau2-bench-verified)
