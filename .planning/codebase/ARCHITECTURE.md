<!-- refreshed: 2026-05-30 -->
# Architecture

**Analysis Date:** 2026-05-30

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         Presentation (Agent E)                           │
│  React SPA — `apps/web/src/App.tsx`, Vite proxy → localhost:8001        │
├──────────────────────────────┬──────────────────────────────────────────┤
│  QueryForm / AnswerPanel     │  TocBrowser / DebugPanel / ChunkInspector │
│  `apps/web/src/components/`  │  (retrieval_debug from API when debug=true)│
└──────────────┬───────────────┴──────────────────┬───────────────────────┘
               │ POST /api/v1/query               │ GET .../topic-frequency
               ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    HTTP Layer (Agent D — API routes)                     │
│  `apps/api/app/main.py` — FastAPI, Pydantic request/response models      │
└──────────────┬──────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              RAG Orchestration (Agent D — `rag/pipeline.py`)             │
│  retrieve → rerank → gate → context expand → generate (OpenRouter)       │
└──────┬───────────────┬────────────────────┬─────────────────────────────┘
       │               │                    │
       ▼               ▼                    ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│ Agent C     │ │ Agent C     │ │ Agent C          │ │ Agent D             │
│ retrieve.py │ │ rerank.py   │ │ gate.py          │ │ generate.py         │
│ hybrid RRF  │ │ cross-enc.  │ │ min_rerank_score │ │ OpenRouter chat     │
└──────┬──────┘ └─────────────┘ └──────────────────┘ └─────────────────────┘
       │ read-only
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector — `apps/api/app/models.py`, Alembic `001_core.py` │
│  courses, documents, chunk_parents, chunks, chunk_embeddings (HNSW)      │
└─────────────────────────────────────────────────────────────────────────┘
       ▲ write (ingest only)
       │
┌─────────────────────────────────────────────────────────────────────────┐
│              Ingest Pipeline (Agent B)                                   │
│  `cli/ingest.py` → `ingestion.py` → pdf_extract → chunker → embedder    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Phase status (source of truth):** `docs/CURRENT_STATE.md` — Phases 0–2 + gates **DONE**; Phase 3C-B topic-frequency API **DONE**; Phase 3C-C heatmap UI **IN PROGRESS**; retrieval at **100%** precision@5 (40/40), OOC **10/10**.

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | HTTP routes, dependency-injected DB sessions, error mapping | `apps/api/app/main.py` |
| Ingest orchestrator | Idempotent PDF → chunks → embeddings; outline metadata for PPL notes | `apps/api/app/services/ingestion.py` |
| PDF extract | PyMuPDF text + Tesseract OCR fallback; outline annotation | `apps/api/app/services/pdf_extract.py` |
| Hierarchical chunker | Parent (page-range) + child (embed unit) chunks with metadata | `apps/api/app/services/chunker/hierarchical.py` |
| Embedder | Local FastEmbed BGE-small-en-v1.5 (384-dim); query prefix for retrieval | `apps/api/app/services/embedder.py` |
| Hybrid retrieve | pgvector + BM25/tsvector + metadata TOC search → RRF fusion | `apps/api/app/services/rag/retrieve.py` |
| Reranker | CPU cross-encoder (BAAI/bge-reranker-base) + domain boosts | `apps/api/app/services/rag/rerank.py` |
| Confidence gate | Refuse when top rerank score < `min_rerank_score` (default 0.35) | `apps/api/app/services/rag/gate.py` |
| Context expand | Attach parent text within token budget before LLM | `apps/api/app/services/rag/context.py` |
| Generator | OpenRouter chat completion; grounded study answers | `apps/api/app/services/rag/generate.py` |
| Study pipeline | End-to-end retrieve → answer orchestration | `apps/api/app/services/rag/pipeline.py` |
| Topic frequency | PYQ unit/section counts from seed YAML + keyword matcher (no LLM) | `apps/api/app/services/exam/topic_frequency.py` |
| ORM models | Courses, documents, hierarchical chunks, pgvector embeddings | `apps/api/app/models.py` |
| Web UI | Query form, answer/sources, TOC browser, debug panels | `apps/web/src/App.tsx` |
| Eval replay | Golden-set retrieval replay without LLM | `eval/replay_retrieval.py` |

## Pattern Overview

**Overall:** Layered monolith — single FastAPI service owns ingest + RAG + exam analytics; React SPA consumes REST. Data lives in Postgres/pgvector. Local ML (FastEmbed) for embed/rerank; remote LLM (OpenRouter) for generation only.

**Key Characteristics:**
- **Contract-driven parallel development:** Frozen interfaces in `docs/api-contracts.md`; Agent B writes, Agent C reads ingest output without cross-editing.
- **Hierarchical RAG:** Child chunks are retrieval units; parent page-range text expands context for rerank and LLM.
- **Study-mode corpus filter:** Retrieval excludes `past_paper` doc_kind; exam intelligence reads `past_paper` separately.
- **Multi-agent file ownership:** One file, one owner (B ingest, C retrieval, D API/generation, E web) per `AGENTS.md` and `docs/orchestrator.md`.

## Layers

**HTTP / API:**
- Purpose: Expose study query and exam analytics; map domain errors to HTTP status codes.
- Location: `apps/api/app/main.py`
- Contains: Route handlers, Pydantic `QueryRequest`/`QueryResponse`, session via `Depends(get_session)`.
- Depends on: `pipeline.run_study_query`, `exam.topic_frequency.compute_topic_frequency`.
- Used by: `apps/web/src/api/queryClient.ts` (proxied through Vite).

**RAG orchestration:**
- Purpose: Compose retrieval, gating, context, and generation into one study query.
- Location: `apps/api/app/services/rag/pipeline.py`
- Contains: `run_study_question` (retrieval-only), `run_study_query` (full pipeline).
- Depends on: `retrieve`, `rerank`, `gate`, `context`, `generate`.
- Used by: `main.py`, `retrieve.replay_golden_set`.

**Retrieval (Agent C):**
- Purpose: Hybrid candidate fetch, rerank, confidence gate; golden-set replay.
- Location: `apps/api/app/services/rag/retrieve.py`, `rerank.py`, `gate.py`, `context.py`
- Contains: `RetrievedChunk` dataclass, `fetch_hybrid_candidates`, `rerank_chunks`, `apply_confidence_gate`, `replay_golden_set`.
- Depends on: `embedder`, `config.settings`, SQLAlchemy session, outline fixtures in `eval/fixtures/ppl/`.
- Used by: `pipeline.py`, `eval/replay_retrieval.py`.

**Generation (Agent D):**
- Purpose: Build prompt from gated chunks; call OpenRouter; format sources.
- Location: `apps/api/app/services/rag/generate.py`
- Contains: `generate_study_answer`, `chunks_to_sources`, `OpenRouterGenerationError`.
- Depends on: `settings.openrouter_api_key`, httpx.
- Used by: `pipeline.run_study_query`.

**Ingest (Agent B):**
- Purpose: PDF → DB rows (documents, parents, chunks, embeddings).
- Location: `apps/api/app/services/ingestion.py`, `pdf_extract.py`, `chunker/`, `embedder.py`, `cli/ingest.py`
- Contains: `ingest_document`, `extract_pdf`, `chunk_pages`, `embed_texts`.
- Depends on: SQLAlchemy models, optional outline YAML per filename.
- Used by: CLI, `scripts/ingest_ppl.ps1`, `scripts/ingest_ppl_pyq.ps1`.

**Exam intelligence:**
- Purpose: Aggregate PYQ topic frequency for UI heatmap (Phase 3C).
- Location: `apps/api/app/services/exam/topic_frequency.py`, `cli/topic_frequency.py`
- Contains: `compute_topic_frequency` — seed from `eval/fixtures/ppl/ppl_pyq_seed.yaml` + keyword match on OCR chunks.
- Depends on: `past_paper` documents only; read-only DB.
- Used by: `GET /api/v1/courses/{course_id}/exam/topic-frequency` in `main.py`.

**Presentation (Agent E):**
- Purpose: Student-facing query UI; debug/TOC panels for retrieval inspection.
- Location: `apps/web/src/`
- Contains: React components, `useStudyQuery` hook, fetch client.
- Depends on: API contracts in `docs/api-contracts.md`.
- Used by: Browser at `localhost:5173`.

**Persistence:**
- Purpose: Course-scoped document store with vector + full-text search.
- Location: `apps/api/app/models.py`, `apps/api/app/database.py`, `apps/api/alembic/versions/001_core.py`
- Contains: `Course`, `Document`, `ChunkParent`, `Chunk`, `ChunkEmbedding`; generated `text_tsv` column on chunks (Alembic).
- Depends on: Docker Postgres (`docker-compose.yml`, port 5433).

## Data Flow

### Primary Request Path — Study Query

1. User submits question in `QueryForm` → `useStudyQuery.submit` posts to `/api/v1/query` (`apps/web/src/hooks/useStudyQuery.ts`, `apps/web/src/api/queryClient.ts`).
2. FastAPI handler validates preset `study`, calls `run_study_query` (`apps/api/app/main.py:40-72`, `apps/api/app/services/rag/pipeline.py:91-124`).
3. **Retrieve:** `fetch_hybrid_candidates` embeds query (BGE query prefix), runs pgvector cosine search + BM25/tsvector + focus/metadata searches, RRF-fuses to `rrf_output_top_k=24` (`retrieve.py:865-952`).
4. **Rerank:** Cross-encoder scores candidates with lexical/metadata/section boosts; keeps top `rerank_output_top_k=6` (`rerank.py:291-332`).
5. **Gate:** If top `rerank_score` < `min_rerank_score` (0.35), return `not_in_materials` with empty answer (`gate.py:9-23`, `pipeline.py:57-61`).
6. **Context:** `expand_parent_context` attaches parent text within char budget (`context.py:9-53`).
7. **Generate:** `generate_study_answer` sends excerpts + question to OpenRouter; returns answer + `chunks_to_sources` (`generate.py:131-151`).
8. Optional `debug=true` adds `retrieval_debug` with chunk metadata for `TocBrowser`/`DebugPanel` (`pipeline.py:68-88`).

### Ingest Path (offline / CLI)

1. `python -m app.cli.ingest <pdf> --course PPL --kind notes|past_paper` (`apps/api/app/cli/ingest.py`).
2. `ingest_document` ensures course, deletes prior chunks if re-ingesting same `(course_id, filename, doc_kind)` (`ingestion.py:49-87`).
3. `extract_pdf` extracts per-page text; OCR via Tesseract when below char threshold (`pdf_extract.py:67+`).
4. For PPL notes, `ppl_outline.yaml` annotates pages with unit/section metadata (`ingestion.py:100-104`, `eval/fixtures/ppl/ppl_outline.yaml`).
5. `chunk_pages` builds hierarchical parents/children with doc_kind-specific token budgets (`chunker/hierarchical.py:72+`).
6. `embed_texts` writes `chunk_embeddings` rows; document status → `ready` (`ingestion.py:143-158`).

### Eval / Retrieval-Only Path

1. Human runs `scripts/run_phase1b_eval_fast.ps1` → `eval/replay_retrieval.py`.
2. `replay_golden_set` calls `run_study_question` per golden row (no LLM) (`retrieve.py:972-1008`).
3. Results written to `eval/reports/latest.jsonl`; scored by `eval/score_precision.py`.

### Exam Topic Frequency Path

1. Client calls `GET /api/v1/courses/{course_id}/exam/topic-frequency` (`main.py:75-81`).
2. `compute_topic_frequency` loads seed questions from `eval/fixtures/ppl/ppl_pyq_seed.yaml`, counts by unit/section.
3. For readable `past_paper` chunks on pages not in seed, keyword-matches against outline section titles (`topic_frequency.py:327-342`).
4. Returns JSON with `units[]`, `total_questions_estimated`, `coverage_note`, `source_documents` — study retrieval unchanged.

**State Management:**
- **Server:** Stateless per request; SQLAlchemy session scoped to request via FastAPI dependency. Process-level singletons for embedder/reranker (`lru_cache` in `embedder.py`, `rerank.py`).
- **Client:** React `useState` in `App.tsx` for form, debug toggle, selected chunk; `useStudyQuery` tracks stage (`idle` → `retrieving` → `generating` → `done`) with elapsed timer heuristics (~60s E2E per `CURRENT_STATE.md`).

## Key Abstractions

**RetrievedChunk:**
- Purpose: Unified retrieval unit flowing through rerank, gate, context, and generation.
- Examples: Defined in `apps/api/app/services/rag/retrieve.py:86-103`; copied immutably in rerank/context.
- Pattern: Dataclass with scores (`vector_score`, `bm25_score`, `rrf_score`, `rerank_score`) and outline metadata (`unit`, `section_title`, `toc_path`).

**Document doc_kind:**
- Purpose: Separates study corpus from exam corpus.
- Examples: `notes`, `textbook`, `syllabus` (study); `past_paper` (exam only, excluded from `STUDY_DOC_KINDS` in `retrieve.py:21`).
- Pattern: Filter enforced in SQL via `_study_doc_filter_sql()` — mandatory for all retrieval queries.

**Hierarchical chunks:**
- Purpose: Small child chunks for embedding/search; large parent spans for LLM context.
- Examples: `ChunkParent` + `Chunk` in `models.py:41-69`; built by `chunker/hierarchical.py`.
- Pattern: Child carries `page` (0-based, matches golden set); parent carries `page_start`/`page_end`.

**StudyQuestionResult / StudyQueryResult:**
- Purpose: Pipeline output types separating retrieval-only from full answer.
- Examples: `apps/api/app/services/rag/pipeline.py:18-31`.
- Pattern: `status` of `ok` | `not_in_materials` drives API response shape.

**Outline fixtures:**
- Purpose: Course structure for metadata retrieval and exam mapping.
- Examples: `eval/fixtures/ppl/ppl_outline.yaml`, `eval/fixtures/ppl/ppl_pyq_seed.yaml`.
- Pattern: Loaded at runtime by path constants in ingest/retrieve/exam modules.

## Entry Points

**FastAPI server:**
- Location: `apps/api/app/main.py` (run via uvicorn on port 8001 per `CURRENT_STATE.md`)
- Triggers: `uvicorn app.main:app --reload --port 8001` from `apps/api`
- Responsibilities: `/health`, `POST /api/v1/query`, `GET /api/v1/courses/{id}/exam/topic-frequency`

**Ingest CLI:**
- Location: `apps/api/app/cli/ingest.py`
- Triggers: `python -m app.cli.ingest`, `scripts/ingest_ppl.ps1`, `scripts/ingest_ppl_pyq.ps1`
- Responsibilities: Populate Postgres for a course from PDF fixtures

**Topic frequency CLI:**
- Location: `apps/api/app/cli/topic_frequency.py`
- Triggers: `python -m app.cli.topic_frequency --course PPL`
- Responsibilities: Print exam frequency JSON to stdout (same logic as HTTP endpoint)

**Eval replay:**
- Location: `eval/replay_retrieval.py`
- Triggers: `scripts/run_phase1b_eval_fast.ps1`, direct `python eval/replay_retrieval.py`
- Responsibilities: Batch retrieval replay against `eval/golden_set.jsonl`

**Web dev server:**
- Location: `apps/web/src/main.tsx`
- Triggers: `npm run dev` in `apps/web` (port 5173, proxies `/api` → 8001 per `vite.config.ts`)
- Responsibilities: Single-page study query UI

**Phase gates:**
- Location: `scripts/phase_gate.ps1`
- Triggers: Human terminal after agent slices
- Responsibilities: pytest + eval thresholds per phase

## Architectural Constraints

- **Threading:** Single-process FastAPI + synchronous SQLAlchemy; CPU-bound rerank and embed run in request thread (no worker pool). E2E query ~60s LLM-bound (`docs/CURRENT_STATE.md`).
- **Global state:** `@lru_cache` singletons for `TextEmbedding` (`embedder.py:10-12`) and `TextCrossEncoder` (`rerank.py:24-27`) — ~400MB reranker loaded once per process.
- **Circular imports:** `retrieve.py` imports `pipeline.run_study_question` only inside `replay_golden_set` to avoid cycle at module load (`retrieve.py:976`).
- **Retrieval read-only:** Agent C modules must not call ingest or mutate documents (`docs/api-contracts.md`).
- **Study filter invariant:** All hybrid SQL must include `doc_kind IN ('notes','textbook','syllabus') AND status='ready'`.
- **0-based pages:** PDF page indices match `eval/golden_set.jsonl` `expected_pages`; page refinement in `_refine_page_from_parent` maps multi-page parents for eval scoring.

## Anti-Patterns

### Retrieval agent editing ingest to pass eval

**What happens:** Changing chunk boundaries or doc_kind filters in `ingestion.py` to fix retrieval misses.
**Why it's wrong:** Violates Agent C/B boundary; masks real retrieval tuning needs; breaks parallel contract in `docs/api-contracts.md`.
**Do this instead:** Tune `retrieve.py`, `rerank.py`, `gate.py` only; propose ingest changes via orchestrator to Agent B.

### Vector-only search

**What happens:** Skipping BM25/tsvector leg or RRF fusion.
**Why it's wrong:** Project requires hybrid retrieval; lexical queries (definitions, "evaluation criteria") fail without BM25 + metadata TOC search.
**Do this instead:** Extend `fetch_hybrid_candidates` extra lists pattern in `retrieve.py:910-941`.

### Using OpenRouter for embeddings

**What happens:** Remote embedding API for ingest or query vectors.
**Why it's wrong:** Engineering constraint in `AGENTS.md` — local FastEmbed only; adds cost/latency and breaks offline eval replay.
**Do this instead:** Use `embed_texts` from `apps/api/app/services/embedder.py`.

### Including past_paper in study retrieval

**What happens:** Removing or bypassing `STUDY_DOC_KINDS` filter.
**Why it's wrong:** PYQ content pollutes study answers; exam corpus has separate analytics path via `topic_frequency.py`.
**Do this instead:** Keep study filter; use `past_paper` only in exam endpoints and seed/keyword pipeline.

## Error Handling

**Strategy:** Domain exceptions at service layer; HTTP mapping in `main.py`; structured refusal for low-confidence retrieval.

**Patterns:**
- **Gate refusal:** `apply_confidence_gate` returns `not_in_materials` — not an HTTP error; `answer: null`, empty sources (`pipeline.py:104-111`).
- **OpenRouter failures:** `OpenRouterGenerationError` mapped to 401/402/429 or 502; missing API key → 503 with setup hint (`main.py:55-64`).
- **Validation:** `ValueError` for unsupported preset → HTTP 400 (`main.py:53-54`).
- **Ingest failures:** Document `status=failed` with `error_message`; exception re-raised after DB update (`ingestion.py:163-171`).

## Cross-Cutting Concerns

**Logging:** Python `logging` in `generate.py` for OpenRouter token usage; ingest/extract use module loggers. Web uses inline error panels, no centralized logger.

**Validation:** Pydantic models at API boundary (`QueryRequest` min_length on question); config via `pydantic-settings` in `apps/api/app/config.py` (env vars for thresholds, models, DB URL).

**Authentication:** Not implemented (Phase 4 per `CURRENT_STATE.md`). API is open on localhost dev ports.

**Configuration:** Retrieval/rerank/gate knobs in `Settings` (`config.py:21-33`): `rrf_output_top_k=24`, `min_rerank_score=0.35`, `study_output_top_k=5`. Override at eval time via `$env:MIN_RERANK_SCORE`.

**Multi-agent governance:** Ownership matrix in `AGENTS.md`, phase gates in `docs/orchestrator.md`, execution status in `docs/CURRENT_STATE.md`. Cursor rules: `.cursor/rules/lead-orchestrator.mdc`, `.cursor/rules/council-governance.mdc`.

---

*Architecture analysis: 2026-05-30*
