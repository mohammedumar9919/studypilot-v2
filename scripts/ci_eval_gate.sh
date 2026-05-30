#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_ROOT="$REPO_ROOT/apps/api"
FIXTURES="$REPO_ROOT/eval/fixtures/ppl"
NOTES_PDF="$FIXTURES/PPL notes.pdf"
REPORTS="$REPO_ROOT/eval/reports"
MIN_RERANK_SCORE="${MIN_RERANK_SCORE:-0.35}"
EVAL_PRECISION_MIN="${EVAL_PRECISION_MIN:-1.0}"
EVAL_OOC_MIN="${EVAL_OOC_MIN:-1.0}"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot_test}"
mkdir -p "$REPORTS"
log() { echo "[$(date +%H:%M:%S)] $*"; }
wait_for_postgres() {
  log "Waiting for Postgres on localhost:5433..."
  for i in $(seq 1 30); do
    if python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',5433)); s.close()"; then
      log "Postgres ready (${i}s)"; return 0
    fi
    sleep 2
  done
  echo "Postgres not available on :5433" >&2; return 1
}
ensure_test_db() {
  PGPASSWORD=studypilot psql -h localhost -p 5433 -U studypilot -d studypilot -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'studypilot_test'" | grep -q 1 || \
    PGPASSWORD=studypilot psql -h localhost -p 5433 -U studypilot -d studypilot -c \
    "CREATE DATABASE studypilot_test;"
}
setup_api() {
  cd "$API_ROOT"
  python -m pip install -e ".[dev]" -q
  export DATABASE_URL
  python -m alembic upgrade head
}
ingest_fixtures() {
  if [[ ! -f "$NOTES_PDF" ]]; then
    echo "Missing fixture: $NOTES_PDF" >&2
    echo "Add PPL PDFs under eval/fixtures/ppl/ or see docs/CI_SETUP.md" >&2
    return 1
  fi
  cd "$API_ROOT"
  export DATABASE_URL
  log "Ingesting PPL notes..."
  python -m app.cli.ingest "$NOTES_PDF" --course PPL --kind notes
  if [[ -f "$FIXTURES/PPL previous papers.pdf" ]]; then
    log "Ingesting PPL past papers..."
    python -m app.cli.ingest "$FIXTURES/PPL previous papers.pdf" --course PPL --kind past_paper
  fi
}
run_pytest() {
  cd "$API_ROOT"
  export DATABASE_URL="$TEST_DATABASE_URL"
  log "pytest (retrieval golden + smoke)..."
  python -m pytest tests/test_retrieval_golden.py tests/test_smoke.py -v --tb=short
}
run_replay_and_gate() {
  cd "$REPO_ROOT"
  export DATABASE_URL MIN_RERANK_SCORE EVAL_PRECISION_MIN EVAL_OOC_MIN
  limit_note=""
  if [[ -n "${GOLDEN_LIMIT:-}" ]]; then limit_note=" GOLDEN_LIMIT=$GOLDEN_LIMIT"; fi
  log "replay MIN_RERANK_SCORE=$MIN_RERANK_SCORE$limit_note"
  python eval/replay_retrieval.py | tee "$REPORTS/replay_${MIN_RERANK_SCORE}.txt"
  python eval/ci_gate.py | tee "$REPORTS/ci_gate.txt"
}
log "StudyPilot CI eval gate — repo=$REPO_ROOT"
wait_for_postgres
ensure_test_db
setup_api
ingest_fixtures
run_pytest
run_replay_and_gate
log "DONE"
