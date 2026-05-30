# PYQ-only re-ingest for PPL past papers (OCR). Does NOT touch notes or golden replay.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..\apps\api

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,ocr]" -q

Write-Host "=== OCR preflight ===" -ForegroundColor Cyan
$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tesseract) {
    $defaultPath = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    if (Test-Path $defaultPath) {
        $env:PATH = "C:\Program Files\Tesseract-OCR;$env:PATH"
        Write-Host "Added Tesseract-OCR to PATH for this session."
    } else {
        Write-Error "tesseract not found. Install via: winget install UB-Mannheim.TesseractOCR"
    }
}
tesseract --version
python -c "import pytesseract; print('pytesseract OK')"

$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
python -m alembic upgrade head

$fixtures = Resolve-Path "..\..\eval\fixtures\ppl"
$pdf = Join-Path $fixtures "PPL previous papers.pdf"
if (-not (Test-Path $pdf)) {
    Write-Error "Missing fixture: $pdf"
}

Write-Host "=== Ingesting PYQ (OCR may take 30-60 min) ===" -ForegroundColor Cyan
python -m app.cli.ingest $pdf --course PPL --kind past_paper

Write-Host "=== Done. Verify with topic-frequency CLI or API. ===" -ForegroundColor Green
