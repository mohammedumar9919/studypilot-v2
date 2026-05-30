# Testing Patterns

**Analysis Date:** 2026-05-30

## Test Framework

**Runner (API):**
- pytest ≥8.3 with pytest-asyncio (dev deps in `apps/api/pyproject.toml`)
- Config: `[tool.pytest.ini_options]` in `apps/api/pyproject.toml` — `testpaths = ["tests"]`, `pythonpath = ["."]`
- No `pytest.ini` at repo root; all pytest runs from `apps/api/`

**Runner (Web):**
- Not detected — no Vitest, Jest, or Playwright in `apps/web/package.json`
- Web quality gates: `npm run lint` (ESLint) and `tsc -b` via `npm run build`

**Assertion library:**
- pytest built-in `assert` (no pytest-httpx or factory_boy)

**Run commands:**
```powershell
# API — from apps/api with venv active
cd C:\Projects\studypilot-v2\apps\api
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot_test"
pytest                              # full suite
pytest tests/test_smoke.py          # smoke only
pytest tests/test_query_api.py -v   # scoped
pytest tests/test_retrieval_golden.py -v  # retrieval + DB

# Phase gates (repo root, orchestrates pytest + eval)
cd C:\Projects\studypilot-v2
.\scripts\phase_gate.ps1 -Phase 0
.\scripts\phase_gate.ps1 -Phase 1a
.\scripts\phase_gate.ps1 -Phase 1c

# Fast eval harness (user terminal — not agent shell)
$env:MIN_RERANK_SCORE = "0.40"
.\scripts\run_phase1b_eval_fast.ps1
```

## Test File Organization

**Location:**
- All API tests live in `apps/api/tests/` (separate from `app/` package)
- Eval harness scripts in `eval/` (`eval/replay_retrieval.py`, `eval/score_precision.py`) — not pytest, but part of quality gates
- No co-located `*.test.tsx` under `apps/web/src/`

**Naming:**
- Files: `test_<feature>.py`
- Functions: `test_<behavior>()` with optional helper `_chunk()`, `_load_golden()`

**Structure:**
```
apps/api/tests/
├── conftest.py              # DB fixtures, migrate, truncate
├── test_smoke.py            # trivial sanity
├── test_chunker.py          # unit (no DB)
├── test_gate_refusal.py     # unit gate logic
├── test_generate.py         # mocked OpenRouter
├── test_query_api.py        # FastAPI TestClient + mocks
├── test_ingest_e2e.py       # DB + PDF fixtures
├── test_retrieval_golden.py # unit hints + DB retrieval
└── test_topic_frequency.py  # exam feature + API route
eval/
├── golden_set.jsonl         # 50-question benchmark (human-edited)
├── replay_retrieval.py      # writes eval/reports/latest.jsonl
└── score_precision.py       # precision@5 + OOC scoring CLI
scripts/
├── phase_gate.ps1           # phase acceptance orchestration
└── run_phase1b_eval_fast.ps1
```

## Test Structure

**Suite organization:**
```python
"""Tests for POST /api/v1/query (mocked generation — no network)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@patch("app.main.run_study_query")
def test_query_refusal_skips_llm(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(...)
    response = client.post("/api/v1/query", json={...})
    assert response.status_code == 200
    mock_run.assert_called_once()
```

**Patterns:**
- **Setup:** Module-level `TestClient(app)` for route tests; `db_session` fixture for DB tests (`apps/api/tests/conftest.py`)
- **Teardown:** `db_session` truncates tables in fixture `finally`; session-scoped `migrated_db` runs Alembic once
- **Assertions:** Plain `assert`; `pytest.raises` for exception paths; `assert_called_once` / `assert_not_called` on mocks
- **Skip:** `pytest.skip(...)` when Postgres unavailable or fixtures missing; `@pytest.mark.skipif(not NOTES_PDF.exists(), ...)` for PDF-dependent tests

## Mocking

**Framework:** `unittest.mock` (`patch`, `MagicMock`); `monkeypatch` for settings in `apps/api/tests/test_generate.py`

**Patterns:**
```python
@patch("app.main.run_study_query")
def test_query_ok_returns_contract_shape(mock_run) -> None:
    mock_run.return_value = StudyQueryResult(status="ok", ...)
    response = client.post("/api/v1/query", json={...})

@patch("app.services.rag.generate._complete")
def test_generate_study_answer_calls_openrouter(mock_complete) -> None:
    mock_complete.return_value = "A lexeme is..."
    answer = generate_study_answer("What is a lexeme?", chunks, preset="study")

@patch("app.services.rag.generate.httpx.Client")
def test_complete_maps_openrouter_429(mock_client_cls) -> None:
    # simulate HTTPStatusError → OpenRouterGenerationError
```

**Replay stub pattern** (`apps/api/tests/test_retrieval_golden.py`):
- Temporarily monkey-patch `pipeline_mod.run_study_question` for deterministic replay tests without DB

**What to mock:**
- OpenRouter HTTP (`_complete`, `httpx.Client`) — never hit network in CI
- Pipeline boundaries in API tests (`app.main.run_study_query`, `run_study_question`, `generate_study_answer`)
- Topic frequency route: `@patch("app.main.compute_topic_frequency")` in `apps/api/tests/test_topic_frequency.py`

**What NOT to mock:**
- Pure functions: `apply_confidence_gate`, `section_page_hints`, `estimate_tokens`, chunker logic
- DB integration tests when Postgres is available: ingest + retrieval paths use real SQLAlchemy session against `studypilot_test`
- Golden PDF fixtures on disk: `eval/fixtures/ppl/PPL notes.pdf` (required for ingest/retrieval e2e)

## Fixtures and Factories

**Test data:**
```python
# conftest.py — session DB with truncate per test
@pytest.fixture()
def db_session(migrated_db):
    engine = create_engine(settings.test_database_url)
    session = sessionmaker(bind=engine)()
    for table in ("chunk_embeddings", "chunks", "chunk_parents", "documents", "courses"):
        session.execute(text(f"TRUNCATE {table} CASCADE"))
    session.commit()
    yield session
    session.close()

# Inline factory in test_query_api.py
def _chunk(*, unit: str | None = None, ...) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=uuid.uuid4(), ...)
```

**Location:**
- Shared fixtures: `apps/api/tests/conftest.py`
- PDF/outline fixtures: `eval/fixtures/ppl/` (referenced via `Path(__file__).resolve().parents[3] / "eval" / ...`)
- Golden questions: `eval/golden_set.jsonl` (loaded in `apps/api/tests/test_retrieval_golden.py` and eval scripts)
- Seed YAML: `eval/fixtures/ppl/ppl_pyq_seed.yaml`, `eval/fixtures/ppl/ppl_outline.yaml`

**Environment:**
- Test DB URL default: `settings.test_database_url` in `apps/api/app/config.py` → `studypilot_test` on port 5433
- `scripts/phase_gate.ps1` sets `DATABASE_URL` to test DB before pytest
- Docker Postgres: `docker-compose.yml` (pgvector on host port 5433)

## Coverage

**Requirements:** None enforced — no `coverage.py`, no CI coverage thresholds

**View coverage:**
```powershell
# Optional — not configured in repo
cd apps\api
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

## Test Types

**Unit tests:**
- Scope: single module, no DB (`apps/api/tests/test_gate_refusal.py`, `apps/api/tests/test_chunker.py`, hint functions in `apps/api/tests/test_retrieval_golden.py`)
- Run fast without Docker

**Integration tests:**
- Scope: SQLAlchemy + Alembic + real PDFs (`apps/api/tests/test_ingest_e2e.py`, DB-marked tests in `apps/api/tests/test_retrieval_golden.py`)
- Require `docker compose up -d` and migrated `studypilot_test`
- Skip gracefully when DB or fixtures missing

**API contract tests:**
- `apps/api/tests/test_query_api.py` — validates JSON shape for `/api/v1/query` (status, sources keys, debug payload)
- `apps/api/tests/test_topic_frequency.py` — `/api/v1/courses/{course_id}/exam/topic-frequency`

**Eval / regression (not pytest):**
- `eval/replay_retrieval.py` — runs full hybrid retrieve → rerank → gate over `eval/golden_set.jsonl` (no LLM)
- `eval/score_precision.py` — computes `precision_at_5` (in-corpus, ±1 page) and `ooc_refusal_rate`
- Phase 1c gate: precision ≥ 70% and 10/10 OOC refusals (`scripts/phase_gate.ps1` Phase `1c`)
- Prefer `scripts/run_phase1b_eval_fast.ps1` over `scripts/run_phase1b_eval.ps1` (single threshold; multi-sweep is slow)

**E2E tests:**
- Not used for web UI
- Closest equivalent: `apps/api/tests/test_ingest_e2e.py` (ingest PDF → assert chunk counts/metadata)

## Phase Gate Scripts

**`scripts/phase_gate.ps1`** — acceptance by phase:

| Phase | pytest scope | Other checks |
|-------|----------------|--------------|
| `0` | full (fallback `test_smoke.py` if skips) | golden set ≥50 + ≥10 OOC, alembic head, `eval/replay_retrieval.py` |
| `1a` | `test_ingest_e2e.py`, `test_chunker.py`, `test_smoke.py` | golden set present |
| `1b` | `test_smoke.py` | replay + report file; optional `test_retrieval.py` if added |
| `1c` | full pytest | replay + `score_precision.py` ≥70% P@5 + 10/10 OOC |
| `2` | full pytest | replay + score + `apps/web` exists |

**`scripts/run_phase1b_eval_fast.ps1`:**
- Docker up → pytest `tests/test_retrieval_golden.py` → replay → score → writes `eval/reports/phase1b_metrics.json`
- Env: `MIN_RERANK_SCORE` (default 0.40), optional `GOLDEN_LIMIT` for smoke subset

## Common Patterns

**Async testing:**
- pytest-asyncio is a dependency but current tests are synchronous
- No `@pytest.mark.asyncio` tests detected in `apps/api/tests/`

**Error testing:**
```python
def test_generate_study_answer_rejects_unsupported_preset() -> None:
    with pytest.raises(ValueError, match="Unsupported preset"):
        generate_study_answer("Q?", [_chunk()], preset="flashcards")

def test_complete_raises_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        _complete(...)
```

**HTTP error mapping test:**
```python
with pytest.raises(OpenRouterGenerationError, match="rate limit") as exc_info:
    _complete(...)
assert exc_info.value.status_code == 429
```

**Conditional DB tests:**
```python
@pytest.mark.skipif(not NOTES_PDF.exists(), reason="PPL notes fixture missing")
def test_study_retrieval_lexeme_question(db_session) -> None:
    ingest_document(db_session, file_path=NOTES_PDF, ...)
    outcome = run_study_question(db_session, course_id="PPL", question="...", preset="study")
    assert outcome.status in ("ok", "not_in_materials")
```

**Autouse fixture guard:**
```python
@pytest.fixture(autouse=True)
def _require_fixtures():
    if not NOTES_PDF.exists():
        pytest.skip(f"Missing fixture: {NOTES_PDF}")
```

## Adding New Tests

**New API behavior:**
1. Place tests in `apps/api/tests/test_<area>.py` matching service ownership (`AGENTS.md`)
2. Mock external HTTP/LLM; use `db_session` only when persistence is required
3. Reference golden data via `eval/` paths — do not duplicate golden rows in test code
4. Run scoped pytest before phase gate: `pytest tests/test_<file>.py -x`

**New eval criteria:**
1. Add rows to `eval/golden_set.jsonl` (human approval per `eval/README.md`)
2. Re-run `eval/replay_retrieval.py` + `eval/score_precision.py`
3. Update `eval/score_precision.py` and `apps/web/src/utils/pageMatch.ts` together if page-matching rules change

**New web UI:**
- No test runner configured — validate with `npm run lint`, `npm run build`, and manual query against proxied API
- Keep request/response types aligned with `docs/api-contracts.md` and `apps/web/src/types.ts`

---

*Testing analysis: 2026-05-30*
