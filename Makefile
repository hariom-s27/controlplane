# ControlPlane — macOS / Linux. Windows users: use .\make.ps1 instead.
PY := .venv/bin/python

.PHONY: help setup probe db test demo negative bench report clean
help:
	@echo "  setup     one-time: venv + install + build db"
	@echo "  probe     check the LLM provider works   <- do this first"
	@echo "  db        rebuild the SQLite stores"
	@echo "  test      run the test suite"
	@echo "  demo      run the gate (blocks ORD-88461)"
	@echo "  negative  run with the gate OFF"
	@echo "  bench     run SEB-1"
	@echo "  report    regenerate every number and chart"
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
demo:     ; CP_GATE=on  $(PY) -m agents.servicing_agent
negative: ; CP_GATE=off $(PY) -m agents.servicing_agent
bench:    ; $(PY) bench/seb1_v2_recoverability.py
report:   ; $(PY) bench/report.py
clean:
	rm -rf data/*.db data/stale_index reports decisions.jsonl .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
	@echo "cleaned."
