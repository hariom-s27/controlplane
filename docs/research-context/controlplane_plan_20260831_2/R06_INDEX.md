# ControlPlane — verification of your status document, corrections, and the plan

**2026-08-31.** Public repo re-fetched live: unchanged since 29 Aug (4 commits, 2 branches). Nothing you describe has been pushed.

| File | What it is |
|---|---|
| `R00_VERIFICATION_OF_YOUR_STATUS.md` | Your status doc checked claim by claim — 15 confirmed, 9 corrected/sharpened, 8 unverifiable |
| `R01_MY_CORRECTIONS.md` | **My audit was wrong twice.** AEGIS identifier (you were right) and LedgerAgent (exists, and it is your nearest competitor) |
| `R02_PRIOR_ART_V2.md` | Corrected + extended matrix: 5 new papers, updated §8A verdicts, the positioning paragraph that survives |
| `R03_GAPS_AND_RETHINK.md` | What your plan is missing — fault localisation, request-side evidence, preregistration, and **the strategic reframe** |
| `R04_PLAN_AND_SCHEDULE.md` | Two tracks, four phases, hard gates, day-by-day to 6 Sept |
| `R05_CLAUDE_CODE_PROMPTS.md` | 13 paste-ready prompts with guardrails, run order and gates |

## The five things that matter

1. **Nothing is pushed.** `p11-readme-reconciliation` is not on origin; `b4ef009` is not in public history; no `tau2`, no `ORDER_STATUS_SUPPORTS_ACTION`, no `bench/label.py`. The only auditable ControlPlane is still the 29 Aug repo whose README carries the retired 100%/75% figure. Downgrade "C1/C2 FROZEN" to **SEALED LOCALLY** until a hash manifest is on a public ref.
2. **You were right about AEGIS and I was wrong.** The relevant paper is **arXiv:2603.12621** — a pre-execution firewall with composable policy validation, **Ed25519 + SHA-256 hash-chained** audit, 48/48 attacks blocked, 1.2% FPR, 8.3 ms median, 14 frameworks. Your receipt design is now *strictly weaker* than published prior art, not merely un-novel.
3. **LedgerAgent (arXiv:2606.20529) is your nearest competitor and I failed to find it.** Same stale-context motivation, checks policy constraints *before environment-changing tool calls*, four customer-service domains, pass^k. Your distinction survives as one clause: its ledger is trace-derived; yours is a fresh query. In your own A1–A5 vocabulary, **LedgerAgent is A4 and your claim is A5 vs A4.**
4. **You have not localised the zero-tool-call fault.** Model / provider / harness / adapter — half that space is free to fix. The discriminating probe is ~10 minutes. Run it before committing to a new track.
5. **The strategic reframe: your thesis does not need τ².** The A1–A5 ladder over your independently-labelled gold set measures "when does independent re-query change adjudication" — offline, deterministic, provider-proof — and **A5−A4 is the LedgerAgent boundary while A5−A3 is the AgentLTL boundary**, so your related work becomes an experiment. τ² is the external-validity arm, not the experiment. You have had these the wrong way round.

## Run order

`CC-1` probe → **GATE A** → `CC-2`,`CC-3`,`CC-4` → `CC-5` fixes → `CC-6` P11 → **GATE B** → `CC-7` → **GATE C** → `CC-8`,`CC-9` A-ladder → `CC-12`,`CC-13` → (only if GATE A allows) `CC-10` → `CC-11`.

**If you run only three: CC-1, CC-5, CC-6.**
