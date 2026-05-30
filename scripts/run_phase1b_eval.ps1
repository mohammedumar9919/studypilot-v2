# Full Phase 1B eval — DEPRECATED for normal use
#
# This script sweeps MIN_RERANK_SCORE 0.30/0.35/0.40/0.45 (4 full replays).
# With 50 golden questions + CPU cross-encoder rerank, expect 1+ HOUR.
#
# USE INSTEAD:  .\scripts\run_phase1b_eval_fast.ps1
#
# If you really need a multi-threshold sweep, run fast script manually per threshold:
#   foreach ($t in 0.30,0.35,0.40,0.45) { $env:MIN_RERANK_SCORE="$t"; .\scripts\run_phase1b_eval_fast.ps1 }

Write-Host "Redirecting to run_phase1b_eval_fast.ps1 (single threshold)..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot "run_phase1b_eval_fast.ps1")
