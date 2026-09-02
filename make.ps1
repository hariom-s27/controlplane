<#
  ControlPlane task runner for Windows PowerShell.
  `make` is not installed on Windows by default, so use this instead.

      .\make.ps1 setup      one-time: venv + install + build db
      .\make.ps1 probe      check the LLM provider works
      .\make.ps1 db         rebuild the three SQLite stores
      .\make.ps1 test       run the test suite
      .\make.ps1 demo       use case 1: servicing   (blocks ORD-88461)
      .\make.ps1 demo2      use case 2: knowledge assistant (cross-tenant block)
      .\make.ps1 demo3      use case 3: discount approval — manifest + graph data, no engine change
      .\make.ps1 negative   run with the gate OFF (the money moves)
      .\make.ps1 judge-demo         six-scenario judge-facing governance walkthrough (offline)
      .\make.ps1 judge-demo-reset   reset judge-demo's local state
      .\make.ps1 bench      run SEB-1
      .\make.ps1 goldset    rebuild the P03 independent gold set + label + agreement
      .\make.ps1 baselines  P04 baseline table B0-B5 (B3 needs CP_MODE=live once)
      .\make.ps1 ablation   P05 evidence-source ablation (A1-A5) + sweeps
      .\make.ps1 robustness P08 failure injection (8 scenarios) + wrong-record crossover
      .\make.ps1 latency    P09 latency profile (4 configs x >=1,000 gated calls)
      .\make.ps1 report     regenerate every number and chart
      .\make.ps1 review     review pending escalations
      .\make.ps1 product-demo  render Evidence Health/Passport/Inspector/Timeline/Policy for one case (env:CASE=gs-001)
      .\make.ps1 clean      delete generated files

  If PowerShell refuses to run this, once per machine:
      Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
param([Parameter(Position = 0)][string]$Task = "help")

$ErrorActionPreference = "Stop"
$Py = ".\.venv\Scripts\python.exe"

function Need-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "No virtualenv found. Run:  .\make.ps1 setup" -ForegroundColor Red
        exit 1
    }
}

switch ($Task) {
    "setup" {
        Write-Host "[1/4] creating virtualenv..." -ForegroundColor Cyan
        python -m venv .venv
        Write-Host "[2/4] upgrading pip..." -ForegroundColor Cyan
        & $Py -m pip install --upgrade pip --quiet
        Write-Host "[3/4] installing packages (this takes a few minutes)..." -ForegroundColor Cyan
        & $Py -m pip install -r requirements.txt
        Write-Host "[4/4] building databases..." -ForegroundColor Cyan
        & $Py data\build_db.py
        if (-not (Test-Path ".env")) {
            Copy-Item .env.example .env
            Write-Host ""
            Write-Host "Created .env -- open it and paste your Featherless key." -ForegroundColor Yellow
        }
        Write-Host ""
        Write-Host "Setup complete. Next:  .\make.ps1 probe" -ForegroundColor Green
    }
    "probe"    { Need-Venv; & $Py scripts\probe.py }
    "db"       { Need-Venv; & $Py data\build_db.py }
    "test"     { Need-Venv; & $Py -m pytest tests -v }
    "ci"       { Need-Venv; & $Py -m pytest tests -q }
    "demo"     { Need-Venv; $env:CP_GATE = "on";  & $Py -m agents.servicing_agent }
    "demo2"    { Need-Venv; $env:CP_GATE = "on";  & $Py -m agents.knowledge_assistant }
    "demo3"    { Need-Venv; $env:CP_GATE = "on";  & $Py -m agents.discount_agent }
    "negative" { Need-Venv; $env:CP_GATE = "off"; & $Py -m agents.servicing_agent }
    "judge-demo"       { Need-Venv; & $Py -m scripts.judge_demo }
    "judge-demo-reset" { Need-Venv; & $Py -m scripts.judge_demo --reset }
    "bench" {
        Need-Venv
        & $Py bench\seb1_exp3_cross_validation.py
        & $Py bench\mutation.py
        # Exp 5 (confusion matrix) is BLOCKED until a held-out gold set exists
        # (P03) — it exits non-zero on purpose. See docs/experiment-audit.md.
        try { & $Py bench\seb1_exp5_confusion_matrix.py } catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
    }
    "goldset" {
        Need-Venv
        & $Py bench\gold_set_build.py
        & $Py bench\label.py
        & $Py bench\agreement.py
    }
    "baselines" { Need-Venv; & $Py bench\baselines.py }
    "ablation" { Need-Venv; & $Py bench\evidence_ablation.py }
    "robustness" { Need-Venv; & $Py bench\failure_injection.py --write }
    "latency"  { Need-Venv; & $Py bench\latency.py --write }
    "report"   { Need-Venv; & $Py bench\report.py }
    "review"   { Need-Venv; & $Py bench\reviewer_console.py }
    "reviewer" { Need-Venv; & $Py bench\reviewer_console.py }
    "product-demo" {
        Need-Venv
        $CaseId = if ($env:CASE) { $env:CASE } else { "gs-001" }
        & $Py -m product.cli $CaseId --replay
    }
    "clean" {
        Remove-Item -Recurse -Force -EA SilentlyContinue `
            data\*.db, data\stale_index, reports, decisions.jsonl, .pytest_cache
        Get-ChildItem -Recurse -Directory -Filter __pycache__ |
            Remove-Item -Recurse -Force -EA SilentlyContinue
        Write-Host "cleaned." -ForegroundColor Green
    }
    default {
        Write-Host ""
        Write-Host "ControlPlane tasks" -ForegroundColor Cyan
        Write-Host "  setup     one-time: venv + install + build db"
        Write-Host "  probe     check the LLM provider works        <- do this first"
        Write-Host "  db        rebuild the SQLite stores"
        Write-Host "  test      run the test suite"
        Write-Host "  demo      use case 1: servicing"
        Write-Host "  demo2     use case 2: knowledge assistant"
        Write-Host "  demo3     use case 3: discount approval (manifest + graph, no engine change)"
        Write-Host "  negative  run with the gate OFF"
        Write-Host "  judge-demo         six-scenario judge-facing governance walkthrough (offline)"
        Write-Host "  judge-demo-reset   reset judge-demo's local state"
        Write-Host "  bench     run SEB-1"
        Write-Host "  goldset   rebuild the P03 independent gold set + label + agreement"
        Write-Host "  baselines P04 baseline table B0-B5 over the gold set"
        Write-Host "  ablation  P05 evidence-source ablation (A1-A5) + absence/staleness sweeps"
        Write-Host "  robustness P08 failure injection (8 scenarios) + wrong-record crossover"
        Write-Host "  latency   P09 latency profile (4 configs x >=1,000 gated calls)"
        Write-Host "  report    regenerate every number and chart"
        Write-Host "  review    review pending escalations"
        Write-Host "  product-demo  render Evidence Health/Passport/Inspector/Timeline/Policy for one case (env:CASE=gs-001)"
        Write-Host "  clean     delete generated files"
        Write-Host ""
    }
}
