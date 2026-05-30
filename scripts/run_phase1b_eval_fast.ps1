# Fast Phase 1B eval: single MIN_RERANK_SCORE threshold (~5-10 min on CPU).
# Default threshold: 0.40. Override: $env:MIN_RERANK_SCORE = "0.35"
# Optional smoke (10 questions): $env:GOLDEN_LIMIT = "10"
# For full 4-threshold sweep (~1+ hour), use scripts/run_phase1b_eval.ps1 instead.

$ErrorActionPreference = 'Continue'
$root = 'C:\Projects\studypilot-v2'
$reports = Join-Path $root 'eval\reports'
New-Item -ItemType Directory -Force -Path $reports | Out-Null

$log = Join-Path $reports 'phase1b_run.log'
function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Add-Content -Path $log -Value $line
    Write-Output $line
}

$env:Path = "C:\Program Files\Docker\Docker\resources\bin;" + $env:Path

Set-Location $root
Log 'docker compose up -d'
docker compose up -d 2>&1 | Out-File (Join-Path $reports 'docker_up.txt')

for ($i = 0; $i - 30; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect('127.0.0.1', 5433)
        $tcp.Close()
        Log "Postgres ready (${i}s)"
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

Set-Location (Join-Path $root 'apps\api')
& .\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = 'postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot'

Log 'pytest (retrieval tests only)'
python -m pytest tests/test_retrieval_golden.py -v 2>&1 |
    Out-File (Join-Path $reports 'pytest_out.txt')

Set-Location $root
$threshold = if ($env:MIN_RERANK_SCORE) { $env:MIN_RERANK_SCORE } else { '0.40' }
$env:MIN_RERANK_SCORE = $threshold

$limitNote = if ($env:GOLDEN_LIMIT) { " GOLDEN_LIMIT=$($env:GOLDEN_LIMIT)" } else { '' }
Log "replay MIN_RERANK_SCORE=$threshold$limitNote (expect ~5-10 min on CPU)"
python eval/replay_retrieval.py 2>&1 | Tee-Object -FilePath (Join-Path $reports "replay_$threshold.txt")
$scoreOut = python eval/score_precision.py eval/golden_set.jsonl eval/reports/latest.jsonl 2>&1
$scoreOut | Out-File (Join-Path $reports "score_$threshold.txt")
Log "score $threshold : $scoreOut"

$j = $null
try {
    $j = $scoreOut | ConvertFrom-Json
} catch {
    Log "WARN: could not parse score JSON"
}

$precision = if ($j) { [double]$j.precision_at_5 } else { 0.0 }
$ooc = if ($j) { [double]$j.ooc_refusal_rate } else { 0.0 }
$misses = if ($j) { @($j.misses) } else { @() }
$precisionMin = if ($env:EVAL_PRECISION_MIN) { [double]$env:EVAL_PRECISION_MIN } else { 0.70 }
$gatePassed = ($precision -ge $precisionMin) -and ($ooc -ge 1.0)

$metrics = [ordered]@{
    precision_at_5 = $precision
    ooc_refusal_rate = $ooc
    min_rerank_score = [double]$threshold
    phase1c_gate_passed = $gatePassed
    eval_precision_min = $precisionMin
    top_misses = $misses | Select-Object -First 10
    golden_limit = if ($env:GOLDEN_LIMIT) { [int]$env:GOLDEN_LIMIT } else { $null }
    generated_at = (Get-Date).ToString('o')
}
$metrics | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $reports 'phase1b_metrics.json')

@(
    "Phase 1B eval summary (fast, single threshold)"
    "pytest: see eval/reports/pytest_out.txt"
    "precision@5: $precision"
    "ooc_rate: $ooc"
    "phase1c_gate_passed: $gatePassed"
    "MIN_RERANK_SCORE: $threshold"
    $(if ($env:GOLDEN_LIMIT) { "GOLDEN_LIMIT: $($env:GOLDEN_LIMIT)" })
    "Top misses: $($misses -join ', ')"
) | Where-Object { $_ } | Set-Content (Join-Path $reports 'PHASE1B_SUMMARY_FOR_AGENT.txt')

Log 'DONE'


