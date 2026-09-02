# ControlPlane — macOS / Linux. Windows users: use .\make.ps1 instead.
PY := .venv/bin/python

.PHONY: help setup probe db test ci demo demo2 demo3 negative judge-demo judge-demo-reset bench goldset baselines ablation robustness latency report review reviewer product-demo clean
help:
	@echo "  setup     one-time: venv + install + build db"
	@echo "  probe     check the LLM provider works   <- do this first"
	@echo "  db        rebuild the SQLite stores"
	@echo "  test      run the test suite"
	@echo "  ci        test suite + the use-case-agnostic engine check"
	@echo "  demo      use case 1: servicing   (blocks ORD-88461)"
	@echo "  demo2     use case 2: knowledge assistant (cross-tenant block)"
	@echo "  demo3     use case 3: discount approval — manifest + graph data, no engine change"
	@echo "  negative  use case 1 with the gate OFF"
	@echo "  judge-demo       six-scenario judge-facing governance walkthrough (offline)"
	@echo "  judge-demo-reset reset judge-demo's local state"
	@echo "  bench     run SEB-1"
	@echo "  goldset   rebuild the P03 independent gold set + label + agreement"
	@echo "  baselines P04 baseline table B0-B5 over the gold set (B3 needs CP_MODE=live once)"
	@echo "  ablation  P05 evidence-source ablation (A1-A5) + absence/staleness sweeps"
	@echo "  robustness P08 failure injection (8 scenarios) + wrong-record crossover"
	@echo "  latency   P09 latency profile (4 configs x >=1,000 gated calls)"
	@echo "  report    regenerate every number and chart"
	@echo "  review    review pending escalations"
	@echo "  product-demo  render Evidence Health/Passport/Inspector/Timeline/Policy for one case (CASE=gs-001)"
	@echo "  clean     delete generated files"

setup:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip --quiet
	$(PY) -m pip install -r requirements.txt
	$(PY) data/build_db.py
	@test -f .env || (cp .env.example .env && echo "\nCreated .env — paste your Featherless key into it.")
	@echo "\nSetup complete. Next: make probe"

probe:    ; $(PY) scripts/probe.py
db:       ; $(PY) data/build_db.py
test:     ; $(PY) -m pytest tests -v
ci:       ; $(PY) -m pytest tests -q
demo:     ; CP_GATE=on  $(PY) -m agents.servicing_agent
demo2:    ; CP_GATE=on  $(PY) -m agents.knowledge_assistant
demo3:    ; CP_GATE=on  $(PY) -m agents.discount_agent
negative: ; CP_GATE=off $(PY) -m agents.servicing_agent
judge-demo:       ; $(PY) -m scripts.judge_demo
judge-demo-reset: ; $(PY) -m scripts.judge_demo --reset
# Exp 5 (confusion matrix) is BLOCKED until a held-out gold set exists (P03) —
# it exits non-zero on purpose; see docs/experiment-audit.md. `- ` lets bench
# continue and still run the mutation harness.
bench:
	$(PY) bench/seb1_exp3_cross_validation.py
	$(PY) bench/mutation.py
	-$(PY) bench/seb1_exp5_confusion_matrix.py
goldset:
	$(PY) bench/gold_set_build.py
	$(PY) bench/label.py
	$(PY) bench/agreement.py
baselines: ; $(PY) bench/baselines.py
ablation: ; $(PY) bench/evidence_ablation.py
robustness: ; $(PY) bench/failure_injection.py --write
latency:  ; $(PY) bench/latency.py --write
report:   ; $(PY) bench/report.py
review:   ; $(PY) bench/reviewer_console.py
reviewer: review
product-demo: ; $(PY) -m product.cli $(CASE) --replay
clean:
	rm -rf data/*.db data/stale_index reports decisions.jsonl .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
	@echo "cleaned."
