# Phase gate helper - runs pytest + eval replay + scoring for user/orchestrator gates.
# Usage: .\scripts\phase_gate.ps1 -Phase 3
# Simple smoke: .\scripts\quick_gate.ps1

param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("0", "1a", "1b", "1c", "2", "3")]
    [string]$Phase = "0",
    [switch]$SkipDocker,
    [switch]$Quick
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
$ApiRoot = Join-Path $RepoRoot "apps\api"
$GoldenPath = Join-Path $RepoRoot "eval\golden_set.jsonl"
$ReportPath = Join-Path $RepoRoot "eval\reports\latest.jsonl"
$MainDatabaseUrl = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
$TestDatabaseUrl = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot_test"

function Write-GateResult {
    param([string]$Name, [bool]$Pass, [string]$Detail = "")
    $icon = if ($Pass) { "PASS" } else { "FAIL" }
    $color = if ($Pass) { "Green" } else { "Red" }
    $line = "  [$icon] $Name"
    if ($Detail) { $line += " - $Detail" }
    Write-Host $line -ForegroundColor $color
    return $Pass
}

function Ensure-ApiVenv {
    Push-Location $ApiRoot
    try {
        if (-not (Test-Path ".venv")) { python -m venv .venv }
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & .\.venv\Scripts\Activate.ps1
        python -m pip install -e ".[dev]" -q *> $null
        $ErrorActionPreference = $prev
    }
    finally { Pop-Location }
}

function Invoke-Pytest {
    param([string[]]$PytestArgs = @())
    Ensure-ApiVenv
    $savedDb = $env:DATABASE_URL
    Push-Location $ApiRoot
    try {
        & .\.venv\Scripts\Activate.ps1
        $env:DATABASE_URL = $TestDatabaseUrl
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        if ($PytestArgs.Count -eq 0) { $output = & pytest 2>&1 }
        else { $output = & pytest @PytestArgs 2>&1 }
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        return @{ Code = $code; Output = ($output -join "`n") }
    }
    finally {
        if ($null -ne $savedDb) { $env:DATABASE_URL = $savedDb }
        else { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }
        Pop-Location
    }
}

function Invoke-EvalReplay {
    Ensure-ApiVenv
    $py = Join-Path $ApiRoot ".venv\Scripts\python.exe"
    $savedDb = $env:DATABASE_URL
    $savedMin = $env:MIN_RERANK_SCORE
    if ($Quick -and -not $env:GOLDEN_LIMIT) { $env:GOLDEN_LIMIT = "10" }
    if (-not $env:MIN_RERANK_SCORE) { $env:MIN_RERANK_SCORE = "0.35" }
    $env:DATABASE_URL = $MainDatabaseUrl
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $py (Join-Path $RepoRoot "eval\replay_retrieval.py") 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally {
        if ($null -ne $savedDb) { $env:DATABASE_URL = $savedDb }
        else { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }
        if ($null -ne $savedMin) { $env:MIN_RERANK_SCORE = $savedMin }
        elseif (-not $savedMin) { Remove-Item Env:MIN_RERANK_SCORE -ErrorAction SilentlyContinue }
        $ErrorActionPreference = $prev
    }
    return $code
}

function Get-ScoreReport {
    param([switch]$MatchResults)
    Ensure-ApiVenv
    $py = Join-Path $ApiRoot ".venv\Scripts\python.exe"
    Push-Location $RepoRoot
    try {
        $matchFlag = if ($MatchResults) { "True" } else { "False" }
        $code = @"
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path('eval')))
from score_precision import load_jsonl, score
golden = load_jsonl(Path('eval/golden_set.jsonl'))
results = load_jsonl(Path('eval/reports/latest.jsonl'))
if ${matchFlag}:
    ids = {r['id'] for r in results}
    golden = [g for g in golden if g['id'] in ids]
print(json.dumps(score(golden, results)))
"@
        $json = & $py -c $code 2>&1
        if ($LASTEXITCODE -ne 0) { return $null }
        return ($json | Out-String).Trim() | ConvertFrom-Json
    }
    finally { Pop-Location }
}

function Test-GoldenSet {
    if (-not (Test-Path $GoldenPath)) { return @{ Pass = $false; Detail = "missing file" } }
    $lines = @(Get-Content $GoldenPath | Where-Object { $_.Trim() -ne "" })
    $count = $lines.Count
    $ooc = ($lines | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.category -eq "out_of_corpus" }).Count
    $pass = ($count -ge 50) -and ($ooc -ge 10)
    return @{ Pass = $pass; Detail = "$count rows, $ooc out_of_corpus" }
}

function Test-Alembic {
    if ($SkipDocker) { return @{ Pass = $true; Detail = "skipped (-SkipDocker)" } }
    Ensure-ApiVenv
    $savedDb = $env:DATABASE_URL
    Push-Location $ApiRoot
    try {
        & .\.venv\Scripts\Activate.ps1
        $env:DATABASE_URL = $TestDatabaseUrl
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $out = python -m alembic upgrade head 2>&1
        $pass = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = $prev
        $detail = if ($pass) { "head" } else { ($out -join " ").Substring(0, [Math]::Min(120, ($out -join " ").Length)) }
        return @{ Pass = $pass; Detail = $detail }
    }
    finally {
        if ($null -ne $savedDb) { $env:DATABASE_URL = $savedDb }
        else { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }
        Pop-Location
    }
}

Write-Host ""
Write-Host "StudyPilot v2 - Phase gate: $Phase$(if ($Quick) { ' (quick)' })" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

$allPass = $true

switch ($Phase) {
    "0" {
        $g = Test-GoldenSet
        $allPass = (Write-GateResult "Golden set (>=50 rows, >=10 OOC)" $g.Pass $g.Detail) -and $allPass
        $a = Test-Alembic
        $allPass = (Write-GateResult "Alembic upgrade head" $a.Pass $a.Detail) -and $allPass
        $pt = Invoke-Pytest
        $pytestPass = ($pt.Code -eq 0)
        if (-not $pytestPass -and $pt.Output -match "skipped") {
            $ptSmoke = Invoke-Pytest -PytestArgs @("tests/test_smoke.py")
            $pytestPass = ($ptSmoke.Code -eq 0)
        }
        $allPass = (Write-GateResult "pytest" $pytestPass $(if ($pytestPass) { "exit 0" } else { "exit $($pt.Code)" })) -and $allPass
        $replayCode = Invoke-EvalReplay
        $allPass = (Write-GateResult "eval/replay_retrieval.py" ($replayCode -eq 0) "exit $replayCode") -and $allPass
    }
    "1a" {
        $pt = Invoke-Pytest -PytestArgs @("tests/test_ingest_e2e.py", "tests/test_chunker.py", "tests/test_smoke.py")
        $allPass = (Write-GateResult "pytest ingest + chunker" ($pt.Code -eq 0) "exit $($pt.Code)") -and $allPass
        $g = Test-GoldenSet
        $allPass = (Write-GateResult "Golden set present" $g.Pass $g.Detail) -and $allPass
    }
    "1b" {
        $pt = Invoke-Pytest -PytestArgs @("tests/test_smoke.py")
        $allPass = (Write-GateResult "pytest smoke" ($pt.Code -eq 0)) -and $allPass
        $replayCode = Invoke-EvalReplay
        $allPass = (Write-GateResult "replay_retrieval.py runs" ($replayCode -eq 0) "exit $replayCode") -and $allPass
        $allPass = (Write-GateResult "eval report written" (Test-Path $ReportPath) $ReportPath) -and $allPass
    }
    "1c" {
        $pt = Invoke-Pytest
        $allPass = (Write-GateResult "pytest full" ($pt.Code -eq 0) "exit $($pt.Code)") -and $allPass
        $replayCode = Invoke-EvalReplay
        $allPass = (Write-GateResult "replay_retrieval.py" ($replayCode -eq 0)) -and $allPass
        $score = Get-ScoreReport
        if ($null -eq $score) { $allPass = (Write-GateResult "score_precision.py" $false "could not score") -and $allPass }
        else {
            $allPass = (Write-GateResult "precision_at_5 >= 70%" ($score.precision_at_5 -ge 0.70) ("{0:P1} ({1}/{2})" -f $score.precision_at_5, $score.hits, $score.total_in_corpus)) -and $allPass
            $allPass = (Write-GateResult "OOC refusal 10/10" ($score.ooc_refusal_rate -ge 1.0) ("{0}/{1}" -f $score.ooc_hits, $score.ooc_total)) -and $allPass
        }
    }
    "2" {
        $pt = Invoke-Pytest
        $allPass = (Write-GateResult "pytest full" ($pt.Code -eq 0)) -and $allPass
        $replayCode = Invoke-EvalReplay
        $allPass = (Write-GateResult "eval replay" ($replayCode -eq 0)) -and $allPass
        $score = Get-ScoreReport
        if ($score) {
            $allPass = (Write-GateResult "precision_at_5 >= 70%" ($score.precision_at_5 -ge 0.70) ("{0:P1}" -f $score.precision_at_5)) -and $allPass
            $allPass = (Write-GateResult "OOC refusal" ($score.ooc_refusal_rate -ge 1.0) ("{0}/{1}" -f $score.ooc_hits, $score.ooc_total)) -and $allPass
        }
        $webDir = Join-Path $RepoRoot "apps\web"
        $allPass = (Write-GateResult "apps/web exists" (Test-Path $webDir) "") -and $allPass
    }
    "3" {
        if ($Quick) {
            $pt = Invoke-Pytest -PytestArgs @("tests/test_smoke.py", "tests/test_retrieval_golden.py", "-k", "not test_study_retrieval and not test_ooc_question")
            $allPass = (Write-GateResult "pytest smoke (quick)" ($pt.Code -eq 0) "exit $($pt.Code)") -and $allPass
        } else {
            $pt = Invoke-Pytest
            $allPass = (Write-GateResult "pytest full" ($pt.Code -eq 0) "exit $($pt.Code)") -and $allPass
        }
        $replayCode = Invoke-EvalReplay
        $limitNote = if ($env:GOLDEN_LIMIT) { "GOLDEN_LIMIT=$($env:GOLDEN_LIMIT)" } else { "50 questions" }
        $allPass = (Write-GateResult "replay_retrieval.py ($limitNote, db=studypilot)" ($replayCode -eq 0)) -and $allPass
        $matchResults = $Quick -or [bool]$env:GOLDEN_LIMIT
        $score = Get-ScoreReport -MatchResults:$matchResults
        if ($null -eq $score) {
            $allPass = (Write-GateResult "score_precision.py" $false "could not score") -and $allPass
        } else {
            $precMin = if ($env:EVAL_PRECISION_MIN) { [double]$env:EVAL_PRECISION_MIN } else { 1.0 }
            $precPass = $score.precision_at_5 -ge $precMin
            $allPass = (Write-GateResult "precision_at_5 >= $([int]($precMin * 100))%" $precPass ("{0:P1} ({1}/{2})" -f $score.precision_at_5, $score.hits, $score.total_in_corpus)) -and $allPass
            if ($matchResults -and $score.ooc_total -eq 0) {
                $allPass = (Write-GateResult "OOC refusal (smoke: none in subset)" $true "skipped") -and $allPass
            } else {
                $oocMin = if ($env:EVAL_OOC_MIN) { [double]$env:EVAL_OOC_MIN } else { 1.0 }
                $oocPass = $score.ooc_refusal_rate -ge $oocMin
                $allPass = (Write-GateResult "OOC refusal" $oocPass ("{0}/{1}" -f $score.ooc_hits, $score.ooc_total)) -and $allPass
            }
        }
    }
}

Write-Host ""
if ($allPass) {
    Write-Host "GATE RESULT: PASS (Phase $Phase)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "GATE RESULT: FAIL (Phase $Phase) - fix checks above before merge" -ForegroundColor Red
    exit 1
}

