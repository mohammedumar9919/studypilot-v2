# StudyPilot v2

**Retrieval-backed study assistant** — answers from your own notes, syllabus, and past papers. Not a generic chatbot.

Hybrid search (keyword + vector), rerank step, and a confidence gate so weak matches are **refused** instead of hallucinated. Local embeddings via FastEmbed. Eval-first development with a golden question set in CI.

## Highlights

| Area | Detail |
|------|--------|
| Retrieval | BM25 + pgvector RRF, rerank, score cutoff |
| Embeddings | FastEmbed (local, no cloud embedding API required) |
| Backend | FastAPI, SQLAlchemy, Alembic, Postgres + pgvector |
| Frontend | React 19, TypeScript, Vite, Clerk auth |
| Quality | 40/40 precision@5 on golden set; 10/10 off-topic refusals; 300+ pytest |
| CI | GitHub Actions eval gate on PRs |
| Infra | Docker Compose |

## Features

- PDF and document ingest with OCR path for scanned papers
- Course outline and structure-aware study modes
- Exam mode: past-paper analytics, heatmaps, concept extraction
- SSE streaming answers to the UI
- Workspace / course scoped retrieval

## Quick start

```powershell
# Postgres + pgvector (port 5433)
docker compose up -d

cd apps/api
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
alembic upgrade head

cd ..\..
# Ingest your own PDFs via scripts/ingest — sample fixture PDFs are not in the public repo
.\scripts\ingest_ppl.ps1   # requires local fixture files if you add them

cd apps/web
npm install
npm run dev
```

## Layout

| Path | Purpose |
|------|---------|
| `apps/api/` | FastAPI, RAG pipeline, ingest |
| `apps/web/` | React study workspace |
| `eval/` | Golden set + replay harness |
| `docs/` | Architecture and orchestration docs |
| `scripts/` | Ingest, phase gates, fast eval |

## Development

See `docs/CURRENT_STATE.md` and `docs/LEAD_ORCHESTRATOR.md` for internal execution status.

Run fast eval (after ingest):

```powershell
$env:MIN_RERANK_SCORE = "0.35"
.\scripts\run_phase1b_eval_fast.ps1
```

## Author

Mohammed Umar Salam — [Portfolio](https://mohammedumar9919.github.io) · [GitHub](https://github.com/mohammedumar9919)

## License

MIT — see [LICENSE](LICENSE).
