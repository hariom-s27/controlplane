# ControlPlane — macOS / Linux. Windows users: use .\make.ps1 instead.
PY := .venv/bin/python

.PHONY: help setup probe db test ci demo demo2 demo3 negative judge-demo judge-demo-reset bench goldset baselines ablation robustness latency report review reviewer product-demo clean
help:
	@echo "  setup     one-time: venv + install + build db"
	@echo "  probe     check the LLM provider works (calls the provider: needs a paid key)"
	@echo "  db        rebuild the SQLite stores"
	@echo "  test      run the test suite"
	@echo "  ci        test suite, quiet output (pytest -q)"
	@echo "  demo      use case 1: servicing   (blocks ORD-88461)"
	@echo "  demo2     use case 2: knowledge assistant (cross-tenant block)"
	@echo "  demo3     use case 3: discount approval — manifest + graph data, no engine change"
	@echo "  negative  use case 1 with the gate OFF"
	@echo "  judge-demo       eight-scenario judge-facing governance walkthrough (offline)"
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
	@# P05b Y12: write .env from .env.example with a new random CP_RECEIPT_SECRET, only if .env
	@# does not exist; an existing .env is never changed; the key is never printed.
	@$(PY) -c 'import pathlib,secrets,sys; e=pathlib.Path(".env"); sys.exit(print("Kept the existing .env (not changed).")) if e.exists() else None; k="CP_RECEIPT_SECRET="; L=[(k+secrets.token_hex(32) if l.startswith(k) else l) for l in pathlib.Path(".env.example").read_text(encoding="utf-8").splitlines()]; assert sum(l.startswith(k) for l in L)==1, "expected one CP_RECEIPT_SECRET line in .env.example"; open(e,"x",encoding="utf-8",newline="\n").write("\n".join(L)+"\n"); print("Created .env with a new random CP_RECEIPT_SECRET (not shown). Paste your Featherless key into it.")'
	@echo "\nSetup complete. Next: make test"

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
# PR-05 (P05 V8): clean removes generated, untracked outputs only. reports/ holds
# committed reports, so it is never deleted here.
clean:
	rm -rf data/*.db data/stale_index decisions.jsonl .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
	@echo "cleaned."
