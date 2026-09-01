<#
  ControlPlane task runner for Windows PowerShell.
  `make` is not installed on Windows by default, so use this instead.

      .\make.ps1 setup      one-time: venv + install + build db
      .\make.ps1 probe      check the LLM provider works
      .\make.ps1 db         rebuild the three SQLite stores
      .\make.ps1 test       run the test suite
      .\make.ps1 demo       run the gate (blocks ORD-88461)
      .\make.ps1 negative   run with the gate OFF (the money moves)
      .\make.ps1 judge-demo         six-scenario judge-facing governance walkthrough (offline)
      .\make.ps1 judge-demo-reset   reset judge-demo's local state
      .\make.ps1 bench      run SEB-1
      .\make.ps1 report     regenerate every number and chart
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
    "demo"     { Need-Venv; $env:CP_GATE = "on";  & $Py -m agents.servicing_agent }
    "negative" { Need-Venv; $env:CP_GATE = "off"; & $Py -m agents.servicing_agent }
    "judge-demo"       { Need-Venv; & $Py -m scripts.judge_demo }
    "judge-demo-reset" { Need-Venv; & $Py -m scripts.judge_demo --reset }
    "bench"    { Need-Venv; & $Py bench\seb1_exp3_cross_validation.py; & $Py bench\seb1_exp5_confusion_matrix.py }
    "report"   { Need-Venv; & $Py bench\report.py }
    "reviewer" { Need-Venv; & $Py bench\reviewer_console.py }
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
        Write-Host "  demo      run the gate (blocks ORD-88461)"
        Write-Host "  negative  run with the gate OFF"
        Write-Host "  judge-demo         six-scenario judge-facing governance walkthrough (offline)"
        Write-Host "  judge-demo-reset   reset judge-demo's local state"
        Write-Host "  bench     run SEB-1"
        Write-Host "  report    regenerate every number and chart"
        Write-Host "  clean     delete generated files"
        Write-Host ""
    }
}
