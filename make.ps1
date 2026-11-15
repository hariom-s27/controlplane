<#
  ControlPlane task runner for Windows PowerShell.
  `make` is not installed on Windows by default, so use this instead.

      .\make.ps1 setup      one-time: venv + install + build db
      .\make.ps1 probe      check the LLM provider works (calls the provider: needs a paid key)
      .\make.ps1 db         rebuild the three SQLite stores
      .\make.ps1 test       run the test suite
      .\make.ps1 demo       use case 1: servicing   (blocks ORD-88461)
      .\make.ps1 demo2      use case 2: knowledge assistant (cross-tenant block)
      .\make.ps1 demo3      use case 3: discount approval — manifest + graph data, no engine change
      .\make.ps1 negative   run with the gate OFF (the money moves)
      .\make.ps1 judge-demo         eight-scenario judge-facing governance walkthrough (offline)
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

  If a step fails, make.ps1 stops and exits with that step's exit code.

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

# P07a Q7: every native command runs through Invoke-Native. A non-zero exit
# code stops make.ps1 with that code ("make.ps1: <task> failed (exit N)");
# -AllowFailure is used once, for exp5 in bench. $ErrorActionPreference is
# 'Continue' only inside this function, so a native program writing to stderr
# is not a PowerShell error. The choice depends on redirection, not on the
# task: with stderr not redirected the command runs directly (interactive
# prompts, e.g. review, work as usual); with stderr redirected, Windows
# PowerShell before 7.2 would wrap each native stderr line as an error record
# (NativeCommandError), so those lines are printed as plain text instead.
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Command,
        [switch]$AllowFailure
    )
    $v = $PSVersionTable.PSVersion
    $wrapsStderr = ($v.Major -lt 7) -or ($v.Major -eq 7 -and $v.Minor -lt 2)
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $global:LASTEXITCODE = 0
    try {
        if ([Console]::IsErrorRedirected -and $wrapsStderr) {
            & $Command 2>&1 | ForEach-Object ToString
        } else {
            & $Command
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $saved
    }
    if ($null -eq $code) { $code = 0 }
    $script:NativeExit = $code
    if ($code -ne 0 -and -not $AllowFailure) {
        Write-Host "make.ps1: $Task failed (exit $code)" -ForegroundColor Red
        exit $code
    }
}

# P07a G7: UTF-8 between PowerShell and Python for this run (output such as
# the rupee sign is not garbled); both settings are restored in finally.
$SavedConsoleEncoding = [Console]::OutputEncoding
$SavedPyIoEncoding = $env:PYTHONIOENCODING
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
$env:PYTHONIOENCODING = "utf-8"

try {
switch ($Task) {
    "setup" {
        Write-Host "[1/4] creating virtualenv..." -ForegroundColor Cyan
        Invoke-Native { python -m venv .venv }
        Write-Host "[2/4] upgrading pip..." -ForegroundColor Cyan
        Invoke-Native { & $Py -m pip install --upgrade pip --quiet }
        Write-Host "[3/4] installing packages (this takes a few minutes)..." -ForegroundColor Cyan
        Invoke-Native { & $Py -m pip install -r requirements.txt }
        Write-Host "[4/4] building databases..." -ForegroundColor Cyan
        Invoke-Native { & $Py data\build_db.py }
        # P05b Y12: write .env from .env.example with a new random CP_RECEIPT_SECRET, only if .env
        # does not exist; an existing .env is never changed; the key is never printed.
        # The code goes to Python on stdin so PowerShell does not rewrite its quotes.
        $EnvCode = 'import pathlib,secrets,sys; e=pathlib.Path(".env"); sys.exit(print("Kept the existing .env (not changed).")) if e.exists() else None; k="CP_RECEIPT_SECRET="; L=[(k+secrets.token_hex(32) if l.startswith(k) else l) for l in pathlib.Path(".env.example").read_text(encoding="utf-8").splitlines()]; assert sum(l.startswith(k) for l in L)==1, "expected one CP_RECEIPT_SECRET line in .env.example"; open(e,"x",encoding="utf-8",newline="\n").write("\n".join(L)+"\n"); print("Created .env with a new random CP_RECEIPT_SECRET (not shown). Paste your Featherless key into it.")'
        # The pipe line below is kept byte-identical (tests/test_setup_env.py reads it).
        Invoke-Native {
        $EnvCode | & $Py -
        }
        Write-Host ""
        Write-Host "Setup complete. Next:  .\make.ps1 test" -ForegroundColor Green
    }
    "probe"    { Need-Venv; Invoke-Native { & $Py scripts\probe.py } }
    "db"       { Need-Venv; Invoke-Native { & $Py data\build_db.py } }
    "test"     { Need-Venv; Invoke-Native { & $Py -m pytest tests -v } }
    "ci"       { Need-Venv; Invoke-Native { & $Py -m pytest tests -q } }
    "demo"     { Need-Venv; $env:CP_GATE = "on";  Invoke-Native { & $Py -m agents.servicing_agent } }
    "demo2"    { Need-Venv; $env:CP_GATE = "on";  Invoke-Native { & $Py -m agents.knowledge_assistant } }
    "demo3"    { Need-Venv; $env:CP_GATE = "on";  Invoke-Native { & $Py -m agents.discount_agent } }
    "negative" { Need-Venv; $env:CP_GATE = "off"; Invoke-Native { & $Py -m agents.servicing_agent } }
    "judge-demo"       { Need-Venv; Invoke-Native { & $Py -m scripts.judge_demo } }
    "judge-demo-reset" { Need-Venv; Invoke-Native { & $Py -m scripts.judge_demo --reset } }
    "bench" {
        Need-Venv
        Invoke-Native { & $Py bench\seb1_exp3_cross_validation.py }
        Invoke-Native { & $Py bench\mutation.py }
        # Exp 5 (confusion matrix) is BLOCKED until a held-out gold set exists
        # (P03) — it exits non-zero on purpose. See docs/experiment-audit.md.
        # It is the one step allowed to fail: bench prints a note and continues.
        Invoke-Native -AllowFailure { & $Py bench\seb1_exp5_confusion_matrix.py }
        if ($script:NativeExit -ne 0) {
            Write-Host "note: exp5 exited $($script:NativeExit) on purpose (BLOCKED, see docs/experiment-audit.md); bench continues." -ForegroundColor Yellow
        }
    }
    "goldset" {
        Need-Venv
        Invoke-Native { & $Py bench\gold_set_build.py }
        Invoke-Native { & $Py bench\label.py }
        Invoke-Native { & $Py bench\agreement.py }
    }
    "baselines" { Need-Venv; Invoke-Native { & $Py bench\baselines.py } }
    "ablation" { Need-Venv; Invoke-Native { & $Py bench\evidence_ablation.py } }
    "robustness" { Need-Venv; Invoke-Native { & $Py bench\failure_injection.py --write } }
    "latency"  { Need-Venv; Invoke-Native { & $Py bench\latency.py --write } }
    "report"   { Need-Venv; Invoke-Native { & $Py bench\report.py } }
    "review"   { Need-Venv; Invoke-Native { & $Py bench\reviewer_console.py } }
    "reviewer" { Need-Venv; Invoke-Native { & $Py bench\reviewer_console.py } }
    "product-demo" {
        Need-Venv
        $CaseId = if ($env:CASE) { $env:CASE } else { "gs-001" }
        Invoke-Native { & $Py -m product.cli $CaseId --replay }
    }
    "clean" {
        # PR-05 (P05 V8): generated, untracked outputs only; reports\ holds committed reports.
        Remove-Item -Recurse -Force -EA SilentlyContinue `
            data\*.db, data\stale_index, decisions.jsonl, .pytest_cache
        Get-ChildItem -Recurse -Directory -Filter __pycache__ |
            Remove-Item -Recurse -Force -EA SilentlyContinue
        Write-Host "cleaned." -ForegroundColor Green
    }
    default {
        Write-Host ""
        Write-Host "ControlPlane tasks" -ForegroundColor Cyan
        Write-Host "  setup     one-time: venv + install + build db"
        Write-Host "  probe     check the LLM provider works (calls the provider: needs a paid key)"
        Write-Host "  db        rebuild the SQLite stores"
        Write-Host "  test      run the test suite"
        Write-Host "  demo      use case 1: servicing"
        Write-Host "  demo2     use case 2: knowledge assistant"
        Write-Host "  demo3     use case 3: discount approval (manifest + graph, no engine change)"
        Write-Host "  negative  run with the gate OFF"
        Write-Host "  judge-demo         eight-scenario judge-facing governance walkthrough (offline)"
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
} finally {
    try { [Console]::OutputEncoding = $SavedConsoleEncoding } catch { }
    if ($null -eq $SavedPyIoEncoding) { Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue } else { $env:PYTHONIOENCODING = $SavedPyIoEncoding }
}
