# API & schema contracts (frozen)

**Version:** 1.0.0  
**Status:** Frozen for Phase 1 parallel work (Agent B ingest ∥ Agent C retrieval prep).  
**Change process:** Orchestrator + human approval only. Bump version and notify all active agents.

Agents B and C must implement against these interfaces without cross-editing each other's modules.

---

## Database schema (Alembic 001)

Owned by orchestrator. Workers **read**; propose migrations via orchestrator only.

| Table | Purpose |
|-------|---------|
| `courses` | `id` (str PK), `name` |
| `documents` | `course_id`, `filename`, `doc_kind`, `status`, `page_count`, `extraction_quality` (JSONB) |
| `chunk_parents` | Page-range parent text for hierarchical RAG |
| `chunks` | Child chunks; `page`, `text`, `text_tsv` (generated tsvector), `metadata` JSONB |
| `chunk_embeddings` | `embedding` Vector(384), `embedding_model`, HNSW index |

**doc_kind enum (ingest CLI):** `notes` | `textbook` | `syllabus` | `past_paper`

**document.status:** `pending` | `processing` | `ready` | `failed`

**Study retrieval filter (mandatory):** `doc_kind IN ('notes', 'textbook', 'syllabus')` — exclude `past_paper`.

---

## Ingest contract (Agent B)

### CLI

```
python -m app.cli.ingest <pdf_path> --course <course_id> --kind <doc_kind> [--name <display_name>]
```

**Success:** `Document.status == "ready"`, `page_count` set, `extraction_quality` JSONB populated, child `chunks` + `chunk_embeddings` rows exist.

### Python entrypoint

```python
def ingest_document(
    session: Session,
    *,
    file_path: Path,
    course_id: str,
    doc_kind: str,
    course_name: str | None = None,
) -> Document: ...
```

**Idempotency:** Re-ingest same `(course_id, filename, doc_kind)` deletes prior chunks/embeddings/parents for that document, then re-indexes.

### HTTP upload (Phase 4 Wave 4b — SP-017)

**Version note:** Additive route (2026-05-30); contract remains **1.0.0**.

`POST /api/v1/courses/{course_id}/documents`

**Request:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `file` | PDF file | yes |
| `doc_kind` | string | yes — `notes` \| `textbook` \| `syllabus` \| `past_paper` |

**Behavior:** Save PDF to server upload dir → call `ingest_document()` synchronously (v1 pilot). Auto-creates course if missing (same as CLI). Re-upload same `(course_id, filename, doc_kind)` replaces chunks (idempotent).

**Response (201):**

```json
{
  "document_id": "uuid",
  "course_id": "PPL",
  "filename": "PPL notes.pdf",
  "doc_kind": "notes",
  "status": "ready",
  "page_count": 94,
  "extraction_quality": { "nonempty_pages": 90, "outline": { "unit_count": 5 } }
}
```

**Errors:**

| Status | When |
|--------|------|
| 400 | Invalid `doc_kind`, non-PDF filename, unsupported content type |
| 422 | Ingest failed (`status: failed` or pipeline exception) — `detail` string |

**Future:** Async job queue if ingest routinely exceeds ~30s (not v1).

**Manual verify:**

```powershell
curl.exe -X POST http://localhost:8001/api/v1/courses/PPL/documents `
  -F "file=@C:\Projects\studypilot-v2\eval\fixtures\ppl\PPL notes.pdf" `
  -F "doc_kind=notes"
```

### PDF extract

```python
@dataclass
class PageText:
    page: int          # 0-based PDF page index (matches golden_set expected_pages)
    text: str
    char_count: int

@dataclass
class ExtractionResult:
    pages: list[PageText]
    page_count: int
    nonempty_pages: int
    quality_flags: dict[str, bool | str | int]

def extract_pdf(path: Path) -> ExtractionResult: ...
```

### Chunker

```python
def chunk_pages(pages: list[PageText], doc_kind: str) -> ChunkingResult: ...
# ChunkingResult.parents: list[ParentChunk]
# ChunkingResult.children: list[ChildChunk]  — embed unit; page on each child for eval scoring
```

### Embedder

```python
def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    # Model: BAAI/bge-small-en-v1.5, 384 dims
    # is_query=True → BGE query prefix for retrieval
```

---

## Retrieval contract (Agent C)

Retrieval **must not** call ingest or mutate documents. Read-only DB access + embedder for query vectors.

### Golden-set replay (eval harness)

```python
def replay_golden_set(golden: list[dict]) -> list[dict]:
    """
    Input: rows from eval/golden_set.jsonl
    Output: one dict per golden row (see Replay result schema)
    """
```

Called by `eval/replay_retrieval.py` — must run without LLM/network (except local FastEmbed).

### Planned module surface

```python
@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    doc_kind: str
    page: int
    text: str
    parent_text: str | None
    vector_score: float | None
    bm25_score: float | None
    rrf_score: float | None
    rerank_score: float | None

def retrieve_study(
    session: Session,
    *,
    course_id: str,
    question: str,
    top_k: int = 5,
) -> list[RetrievedChunk]: ...

def apply_confidence_gate(
    chunks: list[RetrievedChunk],
    *,
    min_rerank_score: float,
) -> tuple[list[RetrievedChunk], str]:
    # Returns (chunks, status) where status is "ok" | "not_in_materials"
```

**Pipeline order:** hybrid candidate fetch (vector + BM25 → RRF) → CPU cross-encoder rerank → gate → optional parent expansion for downstream LLM (Phase 1c).

### Replay result schema (JSONL)

Each line written to `eval/reports/latest.jsonl`:

```json
{
  "id": "ppl-001",
  "status": "ok",
  "retrieved_pages": [4, 5, 6],
  "retrieved_doc": "PPL notes.pdf",
  "top_k": 5,
  "note": ""
}
```

| Field | Type | Required |
|-------|------|----------|
| `id` | string | yes — matches golden row |
| `status` | string | yes — `ok` \| `not_in_materials` \| `pending_retrieval` (stub only) |
| `retrieved_pages` | int[] | yes — pages from top-k chunks (for precision@5) |
| `retrieved_doc` | string | no |
| `top_k` | int | no |
| `note` | string | no — debug only |

**OOC rows:** `status` must be `not_in_materials`, `retrieved_pages` empty.

---

## Golden set row schema

Each line in `eval/golden_set.jsonl`:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Stable id |
| `course` | string | e.g. `PPL` |
| `question` | string | User query |
| `query_mode` | string | `study` for Phase 1 |
| `expected_doc` | string \| null | Filename; null for OOC |
| `expected_pages` | int[] | 0-based PDF pages; ±1 tolerance in scorer |
| `category` | string | `notes` \| `lexical` \| `pyq_style` \| `out_of_corpus` |
| `unit` | string \| null | Optional |
| `expected_keywords` | string[] | Optional lexical check |
| `expected_status` | string | OOC only: `not_in_materials` |

---

## Eval scoring contract

`eval/score_precision.py` computes:

| Metric | Target (Phase 1c gate) |
|--------|------------------------|
| `precision_at_5` | ≥ 0.70 (in-corpus categories) |
| `ooc_refusal_rate` | 1.0 (10/10) |

Page hit: any retrieved page within ±1 of an `expected_pages` entry.

---

## HTTP API (frozen for Phase 2 — not implemented yet)

Agent E and D implement to this shape; **no breaking changes** without contract version bump.

### `POST /api/v1/query`

**Request:**

```json
{
  "course_id": "PPL",
  "question": "What is a lexeme?",
  "preset": "study",
  "debug": false
}
```

**Response (200):**

```json
{
  "status": "ok",
  "answer": "…",
  "sources": [
    {
      "document_id": "uuid",
      "filename": "PPL notes.pdf",
      "page": 11,
      "excerpt": "…"
    }
  ],
  "rerank_scores": [0.82, 0.71],
  "retrieval_debug": null
}
```

**Response (refusal):**

```json
{
  "status": "not_in_materials",
  "answer": null,
  "sources": [],
  "rerank_scores": []
}
```

**presets (Phase 1c):** `study` | `summary` | `flashcards` — start with `study` only.

---

### `POST /api/v1/query/stream` (Phase 4 Wave 3 — SSE streaming)

Same request body as `POST /api/v1/query`. **Additive route** (2026-05-30); non-stream endpoint unchanged.

**Response:** `Content-Type: text/event-stream` — standard SSE frames (`event:` + `data:` JSON per frame).

**Event types:**

| Event | When | `data` shape |
|-------|------|----------------|
| `retrieval_complete` | After retrieve→rerank→gate (~10–15s) | `{ "sources": [...], "chunk_count": N, "rerank_scores": [...], "retrieval_debug": object \| null }` |
| `token` | Each OpenRouter delta during generation | `{ "delta": "..." }` |
| `done` | Stream finished (success or refusal) | Same as non-stream `QueryResponse`: `{ "status", "answer", "sources", "rerank_scores", "retrieval_debug" }` |
| `error` | Generation failed after retrieval | `{ "detail": "...", "status_code": 502 \| 429 \| 503 }` |

**Refusal (OOC / gate):** single `done` event only — no `retrieval_complete` or `token` events.

```json
{"status": "not_in_materials", "answer": null, "sources": [], "rerank_scores": [], "retrieval_debug": null}
```

**Example sequence (success):**

```
event: retrieval_complete
data: {"sources":[{"document_id":"…","filename":"PPL notes.pdf","page":11,"excerpt":"…"}],"chunk_count":5,"rerank_scores":[0.82,0.71],"retrieval_debug":null}

event: token
data: {"delta":"A "}

event: token
data: {"delta":"lexeme"}

event: done
data: {"status":"ok","answer":"A lexeme…","sources":[…],"rerank_scores":[0.82,0.71],"retrieval_debug":null}
```

**Manual verify (PowerShell, API on 8001):**

```powershell
curl.exe -N -X POST http://localhost:8001/api/v1/query/stream `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"PPL\",\"question\":\"What is a lexeme?\",\"preset\":\"study\",\"debug\":false}"
```

---

### `GET /api/v1/courses/{course_id}/exam/topic-frequency` (Phase 3C-B)

Read-only PYQ topic/unit frequency for exam-prediction UI. **No LLM**, no side effects.

**Response (200):**

```json
{
  "course_id": "PPL",
  "total_questions_estimated": 50,
  "coverage_note": "partial — 26/30 pages readable after OCR; 4 page(s) still low-text; seed covers page(s) [3]",
  "units": [
    {
      "unit": "1",
      "title": "Preliminary Concepts",
      "count": 14,
      "sections": [{ "section_title": "Preliminary Concepts", "count": 8 }]
    }
  ],
  "source_documents": [
    {
      "filename": "PPL previous papers.pdf",
      "readable_pages": [3, 4, 5, 6, 7, 8, 9, 10],
      "chunk_count": 80
    }
  ]
}
```

**Response (404):** unknown `course_id`.

**Response (200, empty):** course exists but no `past_paper` docs ingested — `total_questions_estimated: 0`, empty `source_documents`.

**Data sources:** `eval/fixtures/ppl/ppl_pyq_seed.yaml` (primary v1) + keyword match on readable past_paper chunk text for unseeded pages. Study retrieval unchanged (`past_paper` excluded).

---

### `GET /api/v1/courses/{course_id}/outline` (Phase 3 Wave 2 — SP-010)

Read-only course table-of-contents for pre-query browse (Agent E TOC sidebar). **No LLM**, no side effects.

**Version note:** Additive route (2026-05-30); contract remains **1.0.0** — no breaking changes to existing endpoints.

**Response (200):**

```json
{
  "course_id": "PPL",
  "document": "PPL notes.pdf",
  "page_index_base": 0,
  "page_count": 94,
  "front_matter": {
    "title": "Front matter",
    "page_start": 0,
    "page_end": 2
  },
  "units": [
    {
      "id": "1",
      "title": "Preliminary Concepts",
      "page_start": 3,
      "page_end": 16,
      "sections": [
        {
          "title": "Preliminary Concepts",
          "page_start": 3,
          "page_end": 9
        },
        {
          "title": "Syntax and Semantics",
          "page_start": 10,
          "page_end": 16
        }
      ]
    }
  ]
}
```

**Response (404):** unknown `course_id`, or course exists but no outline fixture (v1: PPL only via `eval/fixtures/ppl/ppl_outline.yaml`).

**Page indices:** 0-based PDF pages (matches golden set and chunk `page` metadata from notes ingest).

---

## Cross-agent dependencies

```
Agent B (ingest) ──writes──► chunks + embeddings + tsvector
                                    │
Agent C (retrieve) ◄──reads────────┘
        │
        └──► replay_golden_set ──► eval/reports/latest.jsonl
```

Agent C may develop against a **fixture DB** populated by `scripts/ingest_ppl.ps1` or ingest E2E tests. Agent C must not change ingest behavior to make retrieval pass.

---

## Test contract

| Test path | Owner | Proves |
|-----------|-------|--------|
| `tests/test_ingest_e2e.py` | B | Fixtures → ready docs, idempotency |
| `tests/test_chunker.py` | B | Hierarchical chunk shapes |
| `tests/test_retrieval.py` (to add) | C | Hybrid + gate on golden subset |
| `tests/test_smoke.py` | Orchestrator | CI sanity |
| `tests/test_course_outline.py` | D | Course TOC outline API |
| `tests/test_query_stream.py` | D | SSE query stream |
| `tests/test_document_upload.py` | D | Multipart document upload API |

All tests: run from `apps/api` with Postgres test DB (`studypilot_test` on port 5433).
