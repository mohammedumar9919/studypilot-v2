# Start StudyPilot API (SP-042c+). Uses :8002 by default if :8001 is blocked by an orphan process.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..\apps\api

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1

$Port = if ($env:STUDYPILOT_API_PORT) { [int]$env:STUDYPILOT_API_PORT } else { 8002 }
$inUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse -and -not $env:STUDYPILOT_API_FORCE) {
    Write-Host "Port $Port already in use (PID $($inUse.OwningProcess)). Set STUDYPILOT_API_FORCE=1 or pick another port." -ForegroundColor Yellow
}

Write-Host "=== StudyPilot API on http://127.0.0.1:$Port ===" -ForegroundColor Cyan
Write-Host "Health check: exam_questions_ppl should be >= 377 after PYQ re-ingest." -ForegroundColor Cyan
Write-Host "Web proxy: vite default is http://localhost:$Port (override with VITE_API_PROXY_TARGET)." -ForegroundColor Cyan

uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
