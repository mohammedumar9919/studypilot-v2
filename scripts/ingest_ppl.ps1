# Ingest PPL fixtures (requires Docker Postgres running)

Set-Location $PSScriptRoot\..\apps\api

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]" -q

$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
python -m alembic upgrade head

$fixtures = Resolve-Path "..\..\eval\fixtures\ppl"
python -m app.cli.ingest "$fixtures\PPL notes.pdf" --course PPL --kind notes
python -m app.cli.ingest "$fixtures\PPL previous papers.pdf" --course PPL --kind past_paper

python ..\..\eval\replay_retrieval.py
