# One-command eval gate. Default: full 50 questions (~6-12 min). Smoke: .\scripts\quick_gate.ps1 -Smoke
# Requires: docker Postgres up, PPL ingested on studypilot DB (.\scripts\ingest_ppl.ps1 once).

param(
    [switch]$Smoke
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
$env:MIN_RERANK_SCORE = "0.35"
$env:EVAL_PRECISION_MIN = "1.0"
$env:EVAL_OOC_MIN = "1.0"

if ($Smoke) {
    $env:GOLDEN_LIMIT = "10"
    Write-Host "StudyPilot gate — SMOKE (10 questions, ~2-3 min)" -ForegroundColor Cyan
    Write-Host "DB: studypilot (main, ingested) | MIN_RERANK_SCORE=0.35"
    Write-Host ""
    & "$PSScriptRoot\phase_gate.ps1" -Phase 3 -Quick
    exit $LASTEXITCODE
}

Remove-Item Env:GOLDEN_LIMIT -ErrorAction SilentlyContinue
Write-Host "StudyPilot gate — FULL (50 questions, ~6-12 min)" -ForegroundColor Cyan
Write-Host "DB: studypilot | MIN_RERANK_SCORE=0.35 | EVAL_PRECISION_MIN=1.0"
Write-Host ""
& "$PSScriptRoot\phase_gate.ps1" -Phase 3
exit $LASTEXITCODE
