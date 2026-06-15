# API & schema contracts (frozen)

**Version:** 1.6.0  
**Status:** Frozen for Phase 1 parallel work (Agent B ingest ∥ Agent C retrieval prep).  
**Change process:** Orchestrator + human approval only. Bump version and notify all active agents.

**1.6.0 (2026-06-14 — SP-012c):** Workspace-scoped course APIs: `GET /api/v1/workspaces/me`, `GET /api/v1/workspaces/me/courses`, `POST /api/v1/workspaces/me/courses`. Course ids validated with `^[A-Z0-9][A-Z0-9_-]{0,62}$` (**422** on invalid). Duplicate id in active workspace or id registered in another workspace → **409**. Upload route `POST /api/v1/courses/{course_id}/documents` auto-creates missing courses in the active workspace (same validation/conflict rules); existing courses still require workspace access (**404** when course belongs to another workspace). `ensure_course(..., workspace_id=...)` defaults to System Demo for CLI compat.

**1.5.0 (2026-06-14 — SP-012b):** Clerk JWT auth on all `/api/v1/courses/{course_id}/...`, `/api/v1/query`, `/api/v1/query/stream`, and `PATCH /api/v1/documents/{document_id}`. `/health` remains public. Dev bypass: `STUDYPILOT_AUTH_DISABLED=1` when `environment=development` skips Bearer verification and scopes requests to System Demo workspace (`auth_disabled()`). Production requires `Authorization: Bearer <Clerk session JWT>`; invalid/missing token → **401**; course not in active workspace → **404**.

**1.4.0 (2026-06-14 — SP-012a):** Additive workspace schema: `users`, `workspaces`, `workspace_members`. `courses.workspace_id` NOT NULL FK → `workspaces` (migration backfills existing courses to System Demo workspace `slug=system-demo`, fixed UUID `00000000-0000-4000-a000-000000000001`). Helpers: `get_or_create_system_demo_workspace()`, `ensure_course_workspace()`. **Route guards and auth middleware deferred to SP-012b** — all existing API routes remain unauthenticated in this slice.

**1.3.0 (2026-06-14 — SP-053b):** Document M2M assignment APIs for units/parts/subtopics (`PUT .../structure/{units|parts|subtopics}/{id}/documents`). GET structure returns populated `document_ids` (including subtopics). Query/stream body adds optional `unit_ids`, `part_ids`, `subtopic_ids` (study presets only); mutually exclusive with `source_ids` and `topic_ids`. Structure scope expands to `document_id` set via M2M links + inheritance (subtopic → part → unit; part → unit + subtopics; unit → full subtree) and filters retrieval via existing `document_ids` SQL filter (hybrid RRF unchanged).

**1.2.0 (2026-06-13 — SP-053a.1):** Additive `course_parts`, nullable `course_subtopics.part_id`, `document_part_links` schema. Nested structure API: `units[].parts[].subtopics[]` or flat `units[].subtopics[]`. Paste import supports 3-level indent (0=unit, 2=part, 4=topic/comma line). Confirm/import-syllabus accept nested preview payloads; flat `{ title, subtopics }` remains valid.

**1.1.0 (2026-06-07 — SP-053a):** Additive course structure schema (`course_units`, `course_subtopics`, document link tables) and `/structure/*` preview/confirm APIs. `study_topics` retained (deprecated path, not removed).

Agents B and C must implement against these interfaces without cross-editing each other's modules.

---

## Database schema (Alembic 001)

Owned by orchestrator. Workers **read**; propose migrations via orchestrator only.

| Table | Purpose |
|-------|---------|
| `users` | `id` (UUID PK), `clerk_user_id` (String 128, unique nullable), `email`, `display_name`, `created_at` (SP-012a) |
| `workspaces` | `id` (UUID PK), `name`, `slug` (String 128 unique), `created_at` (SP-012a) |
| `workspace_members` | Composite PK (`workspace_id`, `user_id`); `role` (String 32, default `member`) (SP-012a) |
| `courses` | `id` (str PK), `name`, `outline_data` (JSONB), `structure_mode` (`corpus` \| `organized` \| `mapped`), `workspace_id` NOT NULL FK → `workspaces` (SP-012a; migration backfills to System Demo `slug=system-demo`) |
| `study_topics` | `id` (UUID PK), `course_id` FK, `title`, `sort_order` — **deprecated** in favor of `course_units`/`course_subtopics`; retained for SP-051b compat |
| `course_units` | `id` (UUID PK), `course_id` FK, `title`, `sort_order` (SP-053a) |
| `course_parts` | `id` (UUID PK), `unit_id` FK → `course_units`, `title`, `sort_order` (SP-053a.1) |
| `course_subtopics` | `id` (UUID PK), `unit_id` FK → `course_units`, `part_id` nullable FK → `course_parts`, `title`, `sort_order` (SP-053a; `part_id` SP-053a.1) |
| `document_unit_links` | Composite PK (`document_id`, `unit_id`) — M2M assignment (SP-053b) |
| `document_part_links` | Composite PK (`document_id`, `part_id`) — M2M assignment schema only (SP-053a.1); API wiring SP-053b |
| `document_subtopic_links` | Composite PK (`document_id`, `subtopic_id`) — M2M assignment (SP-053b) |
| `documents` | `course_id`, `filename`, `doc_kind`, `status`, `page_count`, `extraction_quality` (JSONB), `topic_id` (nullable FK → `study_topics`) |
| `chunk_parents` | Page-range parent text for hierarchical RAG |
| `chunks` | Child chunks; `page`, `text`, `text_tsv` (generated tsvector), `metadata` JSONB |
| `chunk_embeddings` | `embedding` Vector(384), `embedding_model`, HNSW index |

**doc_kind enum (ingest CLI):** `notes` | `textbook` | `syllabus` | `past_paper`

**document.status:** `pending` | `processing` | `ready` | `failed`

**Study retrieval filter (mandatory):** `doc_kind IN ('notes', 'textbook', 'syllabus')` — exclude `past_paper`.

### Workspace helpers (SP-012a)

Internal service (`app/services/workspaces.py`); no HTTP routes in this slice.

| Constant / function | Purpose |
|---------------------|---------|
| `SYSTEM_DEMO_WORKSPACE_ID` | Fixed UUID `00000000-0000-4000-a000-000000000001` for dev/eval tenancy |
| `SYSTEM_DEMO_WORKSPACE_SLUG` | `system-demo` |
| `get_or_create_system_demo_workspace(session)` | Idempotent demo workspace row |
| `ensure_course_workspace(session, course)` | Assigns demo workspace when `course.workspace_id` is unset |
| `list_workspace_courses(session, workspace_id)` | Courses scoped to one workspace |
| `validate_course_id(course_id)` | Raises on invalid id pattern (SP-012c) |
| `create_workspace_course(session, workspace_id, course_id, name?)` | Create course in workspace; **409** if duplicate/conflict (SP-012c) |
| `get_or_create_workspace_course(session, workspace_id, course_id, name?)` | Upload auto-create helper (SP-012c) |

**SP-012c (done):** HTTP workspace course routes + upload auto-create. See **Workspace courses** below.

**SP-012b (done):** Clerk JWT middleware + `require_course_access` on all `/api/v1/courses/{course_id}/...` and `/api/v1/query*` routes. See **Authentication** below.

---

## Authentication (SP-012b)

| Route pattern | Auth |
|---------------|------|
| `GET /health` | **Public** — no Bearer token |
| `GET /api/v1/workspaces/me`, `GET/POST /api/v1/workspaces/me/courses` | Bearer JWT (or dev bypass); active workspace scope |
| `/api/v1/courses/{course_id}/...` | Bearer JWT (or dev bypass) + course must belong to active workspace (upload auto-creates missing course in active workspace) |
| `POST /api/v1/query`, `POST /api/v1/query/stream` | Bearer JWT (or dev bypass) + `course_id` in body must belong to active workspace |
| `PATCH /api/v1/documents/{document_id}` | Bearer JWT (or dev bypass) + document's course must belong to active workspace |

**Header:** `Authorization: Bearer <Clerk session JWT>`

**Config (`app/config.py`):**

| Setting | Env | Purpose |
|---------|-----|---------|
| `clerk_jwks_url` | `CLERK_JWKS_URL` | JWKS endpoint for JWT signature verification |
| `clerk_issuer` | `CLERK_ISSUER` | Optional JWT `iss` claim validation |
| `studypilot_auth_disabled` | `STUDYPILOT_AUTH_DISABLED=1` | Dev/test bypass (requires `environment=development`) |

**Dev bypass:** When `settings.auth_disabled()` is true (`environment=development` **and** `STUDYPILOT_AUTH_DISABLED=1`), routes accept requests without `Authorization`. Active workspace is always System Demo; dev user `clerk_user_id=dev-bypass` is created on first request.

**Errors:**

| Condition | Status |
|-----------|--------|
| Auth enabled, missing/invalid Bearer | **401** |
| Course/document not in active workspace | **404** (`Course not found: {course_id}`) |

**Modules:** `app/auth/clerk_jwt.py` (`verify_clerk_jwt`), `app/deps/auth.py` (`AuthContext`, `require_course_access_dep`).

---

## Workspace courses (SP-012c)

Bearer JWT (or dev bypass) required. Active workspace from auth context (System Demo when bypass enabled).

### `GET /api/v1/workspaces/me`

**Response (200):**

```json
{
  "id": "00000000-0000-4000-a000-000000000001",
  "name": "System Demo",
  "slug": "system-demo"
}
```

### `GET /api/v1/workspaces/me/courses`

**Response (200):** array ordered by course `id`.

```json
[
  {
    "id": "PPL",
    "name": "Programming Languages",
    "structure_mode": "mapped",
    "created_at": "2026-06-14T12:00:00+00:00"
  }
]
```

### `POST /api/v1/workspaces/me/courses`

**Request (201):** `{ "id": string, "name"?: string }` — `id` must match `^[A-Z0-9][A-Z0-9_-]{0,62}$`.

**Response (201):** same shape as list item (`structure_mode` defaults to `corpus`).

**Errors:**

| Status | When |
|--------|------|
| 422 | Invalid course id pattern |
| 409 | Course id already exists in active workspace, or id registered in another workspace |

### Upload auto-create

`POST /api/v1/courses/{course_id}/documents` — when `course_id` does not exist, validates id and creates course in active workspace before ingest. When course exists in another workspace, returns **404** (same as other course routes). Invalid id → **422**.

**Manual verify:**

```powershell
curl.exe http://127.0.0.1:8002/api/v1/workspaces/me
curl.exe http://127.0.0.1:8002/api/v1/workspaces/me/courses
curl.exe -X POST http://127.0.0.1:8002/api/v1/workspaces/me/courses `
  -H "Content-Type: application/json" `
  -d "{\"id\":\"BIO101\",\"name\":\"Intro Biology\"}"
```

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
| `upload_intent` | string | no — `quick` \| `topic` \| `past_paper` \| `syllabus`; default **`quick`** when omitted |

**upload_intent validation (400):**

| Rule | Detail |
|------|--------|
| Invalid value | Must be one of `quick`, `topic`, `past_paper`, `syllabus` |
| `doc_kind=past_paper` | `upload_intent` must be `past_paper` |
| `doc_kind=syllabus` | `upload_intent` must be `syllabus` |
| `doc_kind` in `notes` \| `textbook` | `upload_intent` in `quick` \| `topic` \| `syllabus` |

**Ingest behavior:** `upload_intent=quick` on `notes` skips auto TOC extraction into `courses.outline_data` (corpus layout). `topic` stores metadata only (no topic-scoped retrieval in 050c). Chunking, embeddings, PYQ parse, and PPL fixture outlines unchanged.

**Behavior:** Save PDF to server upload dir → call `ingest_document()` synchronously (v1 pilot). Auto-creates course in active workspace when missing (SP-012c); existing courses require workspace access. Re-upload same `(course_id, filename, doc_kind)` replaces chunks (idempotent).

**Response (201):**

```json
{
  "document_id": "uuid",
  "course_id": "PPL",
  "filename": "PPL notes.pdf",
  "doc_kind": "notes",
  "status": "ready",
  "page_count": 94,
  "upload_intent": "quick",
  "extraction_quality": { "nonempty_pages": 90, "upload_intent": "quick", "outline": { "unit_count": 5 } }
}
```

**Errors:**

| Status | When |
|--------|------|
| 400 | Invalid `doc_kind`, invalid `upload_intent`, `upload_intent`/`doc_kind` mismatch, non-PDF filename, unsupported content type |
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
  "debug": false,
  "source_ids": null
}
```

**Optional field — `source_ids` (Phase S — SP-050b):** `list[str] | null` — UUID strings restricting retrieval to specific documents. Omitted or `null` → unchanged behavior (all course docs for the preset's `doc_kinds`). Non-empty → hybrid retrieval filtered to `c.document_id IN (...)`. Empty list `[]` → **400** `source_ids must not be empty when provided`.

**Validation (400 when `source_ids` provided):**

| Rule | Detail |
|------|--------|
| UUID format | Each entry must be a valid UUID string |
| Course ownership | Document must exist and belong to `course_id` |
| Status | `ready` or `processing` only |
| Study presets | `doc_kind` in `notes` \| `textbook` \| `syllabus` |
| Exam preset | `doc_kind` must be `past_paper` |

When `source_ids` is omitted, RRF weights, rerank, and gate thresholds are unchanged (golden eval invariant).

**Optional field — `topic_ids` (Phase S — SP-051b):** `list[str] | null` — study topic UUID strings; restricts retrieval to documents with `documents.topic_id IN (...)`. Study presets only (`study`, `summary`, `flashcards`). Omitted or `null` → unchanged. Empty `[]` → **400**. Cannot combine with `source_ids` (400).

**Validation (400 when `topic_ids` provided):**

| Rule | Detail |
|------|--------|
| UUID format | Each entry must be a valid UUID string |
| Course ownership | Topic must exist and belong to `course_id` |
| Preset | Not allowed for `exam` preset |
| Mutual exclusion | Cannot use with `source_ids` on the same request |

When `topic_ids` is omitted, RRF weights, rerank, and gate thresholds are unchanged (golden eval invariant).

**Optional fields — structure scope (Phase S — SP-053b):** `unit_ids`, `part_ids`, `subtopic_ids` — each `list[str] | null` of course-structure UUID strings. Study presets only (`study`, `summary`, `flashcards`). Omitted or `null` → unchanged. Empty `[]` on any provided field → **400**. Mutually exclusive with `source_ids` and `topic_ids` (400). Multiple structure fields may be combined on one request (union of expanded document sets).

**Expansion (read-only, no RRF change):** Resolved to `document_id IN (...)` before hybrid retrieval:

| Scope | Document set |
|-------|----------------|
| `subtopic_ids` | Docs linked to subtopic + parent part + parent unit |
| `part_ids` | Docs linked to part + parent unit + all subtopics under that part |
| `unit_ids` | Docs linked to unit, any part, or any subtopic under the unit |

**Validation (400 when structure scope provided):**

| Rule | Detail |
|------|--------|
| UUID format | Each entry must be a valid UUID string |
| Course ownership | Unit/part/subtopic must exist and belong to `course_id` |
| Preset | Not allowed for `exam` preset |
| Mutual exclusion | Cannot combine with `source_ids` or `topic_ids` |
| Non-empty expansion | At least one assigned document must match expanded set |

When structure scope is omitted, RRF weights, rerank, and gate thresholds are unchanged (golden eval invariant).

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

**Refusal debug (`debug: true`, Wave 9.1 — SP-015.2):** when `status` is `not_in_materials`, `retrieval_debug` may include:

| Field | Values |
|-------|--------|
| `refusal_reason` | `empty_corpus` (no candidates before rerank) \| `below_threshold` (top rerank score below gate) |
| `top_rerank_score` | float \| null — best rerank score before gate (if rerank ran) |
| `exam_question_hits` | exam preset + `debug: true` only — parsed `exam_questions` matches (see exam retrieval note above) |

Exam preset uses `min_rerank_score_exam` (**0.25**, env `MIN_RERANK_SCORE_EXAM`); study/summary/flashcards use `min_rerank_score` (**0.35**).

**presets (Wave 6 — SP-032; Wave 8 — SP-015 exam):** `study` | `summary` | `flashcards` | `exam`. Study presets (`study`, `summary`, `flashcards`) share the same retrieval → rerank → gate path over **notes, textbook, and syllabus only** — **`past_paper` is excluded**. The `exam` preset uses the same rerank → gate → context path but retrieves **`past_paper` documents only** (notes/textbook/syllabus excluded). Only the generation prompt differs per preset. Unknown presets → **400** `Unsupported preset: …`.

| Preset | Retrieval scope | Output |
|--------|-----------------|--------|
| `study` | notes, textbook, syllabus | Grounded Q&A answer with inline citations `[filename p.N]` |
| `summary` | notes, textbook, syllabus | Concise bullet summary (`-` markdown bullets) focused on the question topic |
| `flashcards` | notes, textbook, syllabus | 3–8 Q/A pairs in markdown (`**Q:**` / `**A:**`) from retrieved material |
| `exam` | **past_paper only** | PYQ-focused answer: question style, similar past questions, brief note-review pointers; cite `[filename p.N]` |

**Exam retrieval (Wave 9.5 — SP-042b):** When `exam_questions` rows exist for the course, the `exam` preset hybrid-fuses parsed question matches (BM25 + vector on `prompt_text`) with existing past_paper chunk RRF. Parsed questions rank candidates; **chunks on the same page supply citation text**. When no parsed rows exist, behavior is unchanged (chunk-only exam retrieval). Study presets are unaffected.

**Debug (`debug: true`, exam preset only):** `retrieval_debug.exam_question_hits` — optional array of `{id, page, part, question_number, prompt_snippet}` from parsed question matches.

**Example — `preset: summary` (200):**

```json
{
  "status": "ok",
  "answer": "- Lexeme: abstract linguistic unit [PPL notes.pdf p.11]\n- Token: surface form belonging to a lexeme [PPL notes.pdf p.12]",
  "sources": […],
  "rerank_scores": [0.82, 0.71]
}
```

**Example — `preset: flashcards` (200):**

```json
{
  "status": "ok",
  "answer": "**Q:** What is a lexeme?\n**A:** The abstract unit of meaning. [PPL notes.pdf p.11]\n\n**Q:** How does a token relate to a lexeme?\n**A:** A token is a surface form that belongs to a lexeme category. [PPL notes.pdf p.12]",
  "sources": […],
  "rerank_scores": [0.82, 0.71]
}
```

**Example — `preset: exam` (200):**

```json
{
  "status": "ok",
  "answer": "Past papers ask short-answer questions on lexemes vs tokens [PPL previous papers.pdf p.3]. Similar: \"Define lexeme and token with examples.\" Review vocabulary terminology in your course notes.",
  "sources": [
    {
      "document_id": "uuid",
      "filename": "PPL previous papers.pdf",
      "page": 3,
      "excerpt": "…"
    }
  ],
  "rerank_scores": [0.85, 0.72]
}
```

**Example — `preset: exam` refusal (no past papers ingested):**

```json
{
  "status": "not_in_materials",
  "answer": null,
  "sources": [],
  "rerank_scores": []
}
```

**Manual verify (PowerShell, API on 8001):**

```powershell
# study (unchanged)
curl.exe -X POST http://localhost:8001/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"PPL\",\"question\":\"What is a lexeme?\",\"preset\":\"study\"}"

# summary
curl.exe -X POST http://localhost:8001/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"PPL\",\"question\":\"Summarize lexemes and tokens\",\"preset\":\"summary\"}"

# flashcards
curl.exe -X POST http://localhost:8001/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"PPL\",\"question\":\"Lexemes and tokens\",\"preset\":\"flashcards\"}"

# exam (past_paper sources only)
curl.exe -X POST http://127.0.0.1:8001/api/v1/query/stream `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"PPL\",\"question\":\"Questions on lexemes and tokens\",\"preset\":\"exam\",\"debug\":false}"
```

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

### `GET /api/v1/courses/{course_id}/exam/status` (Wave 9.1 — SP-015.2)

Read-only unified exam index / heatmap readiness. **No LLM**, no side effects.

**Response (200):**

```json
{
  "course_id": "PPL",
  "documents_ready": true,
  "document_count": 1,
  "readable_pages": 20,
  "total_pages": 30,
  "chunk_count": 80,
  "embedded_chunk_count": 80,
  "embeddings_ready": true,
  "parsed_questions": 42,
  "question_count_source": "exam_questions",
  "has_pyq_seed": true,
  "exam_index_ready": true,
  "heatmap_available": true,
  "heatmap_source": "parsed",
  "readable_char_threshold": 100,
  "source_documents": [
    {
      "filename": "PPL previous papers.pdf",
      "readable_pages": [3, 4, 5],
      "chunk_count": 80
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `exam_index_ready` | `documents_ready` AND `chunk_count > 0` AND `embeddings_ready` |
| `heatmap_available` | `documents_ready` AND (`parsed_questions > 0` OR `has_pyq_seed` OR `readable_pages > 0`) |
| `heatmap_source` | `parsed` \| `seed` \| `keyword` \| `none` — **`parsed`** when `exam_questions` rows exist; else seed YAML; else keyword proxy |
| `parsed_questions` | Live `COUNT(*)` from `exam_questions` for the course (Wave 9.4 — SP-042a) |
| `question_count_source` | `exam_questions` when `parsed_questions > 0`; else `none` |

**Response (404):** unknown `course_id`.

**Response (200, empty corpus):** course exists, no `past_paper` docs — `documents_ready: false`, `exam_index_ready: false`, `heatmap_source: "none"`.

---

### `GET /api/v1/courses/{course_id}/exam/topic-frequency` (Phase 3C-B)

Read-only PYQ topic/unit frequency for exam-prediction UI. **No LLM**, no side effects.

**Query params (Wave 6.7):** `detail=sections` — include per-section counts (default for generic courses with >12 sections: unit-level chapter counts only). Every unit object always includes a `sections` array; it is empty when rolled up to chapter level.

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

**Data sources (priority, Wave 9.4 — SP-042a):**

1. **`exam_questions` table** — when rows exist for the course, counts are exact (`total_questions_estimated` = row count; field name kept for contract compat). `coverage_note` summarizes extraction methods (`regex`, `seed_import`, `llm_assist`).
2. **PPL seed YAML** — `eval/fixtures/ppl/ppl_pyq_seed.yaml` when no `exam_questions` rows (unchanged).
3. **Keyword/page proxy** — generic courses: match chunk text to outline section titles.

Keyword matching is at **section** level internally; response aggregates to **unit/chapter** counts when outline has >12 sections unless `?detail=sections`. Unmatched → `"Unclassified"`. Study retrieval unchanged.

**Ingest idempotency (Agent B):** On `past_paper` re-ingest, delete existing `exam_questions` for that document before inserting parsed rows.

**Example — generic Chemistry heatmap (unit rollup, default):**

```json
{
  "course_id": "TEST101",
  "total_questions_estimated": 8,
  "coverage_note": "Matched 8 past-paper question(s) to outline topics by keyword (no PYQ seed).",
  "units": [
    { "unit": "1", "title": "Thermodynamics 1", "count": 3, "sections": [] },
    { "unit": "2", "title": "Thermodynamics 2", "count": 2, "sections": [] }
  ]
}
```

---

### `GET /api/v1/courses/{course_id}/documents` (Phase S — SP-050b)

Read-only ingested document list for Flex Study source picker. **No LLM**, no side effects.

**Response (200):**

```json
{
  "course_id": "CHEM",
  "documents": [
    {
      "document_id": "uuid-string",
      "filename": "Chemistry notes.pdf",
      "page_count": 25,
      "status": "ready",
      "doc_kind": "notes"
    }
  ]
}
```

Documents with `status` in `ready` \| `processing` only; ordered by `created_at`, then `filename`. Same visibility rules as `study-layout` `sources`.

**Response (404):** unknown `course_id`.

**Manual verify:**

```powershell
curl.exe http://127.0.0.1:8002/api/v1/courses/chemistry/documents
```

---

### `GET /api/v1/courses/{course_id}/study-layout` (Phase S — SP-050a, updated SP-051a)

Read-only Flex Study sidebar mode and ingested document list. **No LLM**, no side effects.

**Response (200):**

```json
{
  "mode": "mapped",
  "structure_mode": "mapped",
  "course_id": "PPL",
  "sources": [
    {
      "document_id": "uuid-string",
      "filename": "PPL notes.pdf",
      "page_count": 94,
      "status": "ready",
      "doc_kind": "notes"
    }
  ],
  "sidebar_views": {
    "sources": false,
    "topics": false,
    "course_map": true
  },
  "outline_available": true
}
```

| Field | Meaning |
|-------|---------|
| `mode` | Web sidebar mode: `mapped` or `corpus`. **`organized` → `corpus`** for 051a backward compat |
| `structure_mode` | Persisted course mode: `corpus` \| `organized` \| `mapped` (Alembic 004 backfill: PPL, `chemistry`, `outline_quality=high` → `mapped`) |
| `sources` | Documents with `status` in `ready` \| `processing`; ordered by `created_at`, then `filename` |
| `sidebar_views` | Tab visibility flags (SP-052.2): which Flex Study sidebar views to show |
| `sidebar_views.sources` | `true` when ready/processing documents exist; **PPL fixture → always `false`** (mapped-only sidebar) |
| `sidebar_views.topics` | `true` when `study_topics.length > 0` **or** `structure_mode === "organized"`; PPL fixture → `false` |
| `sidebar_views.course_map` | `true` when `GET .../outline` would return 200 (same as `outline_available` except PPL fixture → always `true`) |
| `outline_available` | `true` when course outline is resolvable (fixture, stored outline, auto-stub, etc.) |
| `promotion_hint` | Optional (SP-052): present when `structure_mode` is `corpus` and Course Map promotion is eligible |

**Response (404):** unknown `course_id`.

**Response (200, empty corpus):** course exists, no ready/processing documents — `sources: []` (mode still set per rules above).

**Example — generic Chemistry (`corpus`):**

```json
{
  "mode": "corpus",
  "structure_mode": "corpus",
  "course_id": "CHEM",
  "sources": [
    {
      "document_id": "uuid-string",
      "filename": "Chemistry notes.pdf",
      "page_count": 25,
      "status": "ready",
      "doc_kind": "notes"
    }
  ],
  "sidebar_views": {
    "sources": true,
    "topics": false,
    "course_map": true
  },
  "outline_available": true
}
```

**Manual verify:**

```powershell
curl.exe http://127.0.0.1:8002/api/v1/courses/PPL/study-layout
curl.exe http://127.0.0.1:8002/api/v1/courses/CHEM/study-layout
```

---

### Study topics CRUD (Phase S — SP-051a)

User-defined topic buckets for **organized** mode. Additive routes; no retrieval changes until SP-051b.

**GET `/api/v1/courses/{course_id}/study-topics` (200):**

```json
{
  "course_id": "CHEM",
  "topics": [
    { "id": "uuid", "course_id": "CHEM", "title": "Thermodynamics", "sort_order": 1 }
  ]
}
```

**POST `/api/v1/courses/{course_id}/study-topics` (201):** body `{ "title": string, "sort_order": int }` (default 0).

**PATCH `/api/v1/courses/{course_id}/study-topics/{topic_id}`:** body `{ "title"?: string, "sort_order"?: int }`.

**DELETE `/api/v1/courses/{course_id}/study-topics/{topic_id}` (204):** deletes topic; `documents.topic_id` set null.

**PATCH `/api/v1/documents/{document_id}`:** body `{ "topic_id": uuid-string | null }` — assign or clear topic (topic must belong to document's course).

**Errors:** 404 unknown course/topic/document; 400 empty title or invalid UUID.

**PATCH `/api/v1/courses/{course_id}/structure-mode` (SP-051b):** body `{ "structure_mode": "organized" | "corpus" }`. Promotes corpus → organized. Cannot demote PPL/mapped fixture courses to corpus (400). Response includes `structure_mode` and web `mode` (`organized` → `mode: corpus` until topic UI ships).

**POST `/api/v1/courses/{course_id}/study-topics/bulk` (201, SP-051b):** body `{ "titles": ["Unit 1", "Unit 2", ...] }`. Creates topics with `sort_order` by index; sets `structure_mode=organized` when course was `corpus`.

### Course structure (Phase S — SP-053a, SP-053a.1)

Hierarchical units → optional parts → subtopics for Organized Study. **Preview endpoints do not persist.** **Confirm** replaces the entire tree for the course and sets `structure_mode=organized`. Document M2M links are wired via assignment endpoints (SP-053b); GET returns populated `document_ids` on units, parts, and subtopics.

**GET `/api/v1/courses/{course_id}/structure` (200):**

Nested when parts exist; flat subtopics when a unit has no parts:

```json
{
  "course_id": "CHEM",
  "units": [
    {
      "id": "uuid-string",
      "title": "Unit 1 Thermodynamics",
      "sort_order": 0,
      "parts": [
        {
          "id": "uuid-string",
          "title": "Laws of Thermodynamics",
          "sort_order": 0,
          "subtopics": [
            { "id": "uuid-string", "title": "Heat", "sort_order": 0, "document_ids": [] }
          ],
          "document_ids": []
        }
      ],
      "document_ids": []
    },
    {
      "id": "uuid-string",
      "title": "Unit 2 Atomic Structure",
      "sort_order": 1,
      "subtopics": [
        { "id": "uuid-string", "title": "Orbitals", "sort_order": 0, "document_ids": [] }
      ],
      "document_ids": []
    }
  ]
}
```

**PUT `/api/v1/courses/{course_id}/structure/units/{unit_id}/documents` (200):** body `{ "document_ids": ["uuid-string", ...] }` — replaces all unit-level M2M links. Same shape for **PUT** `.../parts/{part_id}/documents` and **PUT** `.../subtopics/{subtopic_id}/documents`. Returns GET structure shape. Documents must belong to `course_id`, `status` in `ready` \| `processing`, `doc_kind` in `notes` \| `textbook` \| `syllabus`. **404** unknown course/node; **400** invalid UUID, wrong course document, or empty/invalid list.

**Manual verify (assignment + scoped query):**

```powershell
curl.exe -X PUT http://127.0.0.1:8002/api/v1/courses/CHEM/structure/units/{unit_id}/documents `
  -H "Content-Type: application/json" `
  -d "{\"document_ids\":[\"{document_id}\"]}"

curl.exe -X POST http://127.0.0.1:8002/api/v1/query `
  -H "Content-Type: application/json" `
  -d "{\"course_id\":\"CHEM\",\"question\":\"Explain heat transfer\",\"preset\":\"study\",\"unit_ids\":[\"{unit_id}\"]}"
```

Units with parts omit top-level `subtopics`; units without parts omit `parts`. **404** unknown course. **200** with `"units": []` when no structure confirmed yet.

**POST `/api/v1/courses/{course_id}/structure/import-paste` (200):** body `{ "text": string }`. Indent rules: **0** = unit title; **2** = part title (when any line in the unit uses indent ≥4) or flat subtopic; **4** = subtopic (comma-separated topics allowed on one line). Returns preview only:

```json
{
  "preview": true,
  "units": [
    {
      "title": "Unit 1 Thermodynamics",
      "parts": [
        { "title": "Laws", "subtopics": ["Heat", "Work"] }
      ]
    },
    {
      "title": "Unit 2 Atomic Structure",
      "subtopics": ["Orbitals"]
    }
  ]
}
```

**400** empty/invalid paste; **404** unknown course.

**POST `/api/v1/courses/{course_id}/structure/import-syllabus` (200):** body optional `{ "document_id": "uuid" }`; when omitted uses `find_syllabus_document`. Calls Agent B syllabus structure parser (`parse_syllabus_course_structure` when present, else engineering syllabus parser). Accepts v2 parser shape with `parts[]` per unit when present. Returns:

```json
{
  "preview": true,
  "units": [
    {
      "title": "UNIT - I Introduction to Computer Networks",
      "subtopics": ["Network models", "..."]
    }
  ],
  "parse_warning": "optional string when parse is partial"
}
```

**404** unknown course/document; **422** `syllabus_document_not_found` or `syllabus_parse_failed`.

**POST `/api/v1/courses/{course_id}/structure/confirm` (200):** body `{ "units": [...] }` where each unit is either `{ "title", "subtopics": [string] }` (flat, backward compatible) or `{ "title", "parts": [{ "title", "subtopics": [string] }] }`. Idempotent replace (delete+insert). Sets `structure_mode=organized`. Returns GET structure shape.

**400** invalid units payload; **404** unknown course.

**Manual verify (CN engineering syllabus — 5 units):**

```powershell
curl.exe -X POST http://127.0.0.1:8002/api/v1/courses/CN/structure/import-syllabus -H "Content-Type: application/json" -d "{}"
curl.exe -X POST http://127.0.0.1:8002/api/v1/courses/CN/structure/confirm -H "Content-Type: application/json" -d "{\"units\":[{\"title\":\"Unit 1\",\"subtopics\":[\"A\"]}]}"
curl.exe http://127.0.0.1:8002/api/v1/courses/CN/structure
```

### Course Map promotion (Phase S — SP-052, SP-052.1)

**GET `/api/v1/courses/{course_id}/course-map-eligibility` (200):**

```json
{
  "eligible": true,
  "outline_quality": "medium",
  "structure_mode": "organized",
  "reason": null,
  "syllabus_filename": "CN syllabus.pdf",
  "outline_preview": {
    "outline_source": "extracted",
    "unit_count": 5,
    "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"]
  }
}
```

| Field | Meaning |
|-------|---------|
| `eligible` | `true` when `structure_mode` is `corpus` or `organized` (not already `mapped`) AND a ready syllabus document exists AND (`outline_quality` is `high`/`medium` with `outline_source` `extracted`/`uploaded` OR dry-run syllabus TOC extraction would succeed) |
| `reason` | `null` when eligible; else `already_mapped`, `no_syllabus_document`, `no_outline`, or `outline_quality_not_high` |
| `syllabus_filename` | Best-match syllabus PDF filename, or `null` |
| `outline_preview` | Up to 5 unit titles from stored outline or dry-run extraction |

**POST `/api/v1/courses/{course_id}/course-map/promote` (200):** extracts syllabus TOC into `courses.outline_data` (merges `study_topics` document assignments into unit `assigned_document_ids`), then sets `structure_mode=mapped`. Idempotent when already mapped with valid outline. **Repair path:** when `structure_mode=mapped` but `outline_data` is missing/invalid and a syllabus doc exists, re-runs extraction without changing mode (`promoted: false`, `repaired: true`). **422** when not eligible or syllabus extraction fails.

```json
{
  "course_id": "CN",
  "structure_mode": "mapped",
  "mode": "mapped",
  "promoted": true,
  "repaired": false,
  "outline_summary": {
    "unit_count": 5,
    "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"],
    "outline_quality": "medium",
    "outline_source": "extracted"
  }
}
```

**POST `/api/v1/courses/{course_id}/course-map/rebuild-outline` (200, SP-052.1b):** re-extracts syllabus TOC into `outline_data` without changing `structure_mode`. For stuck mapped courses (e.g. pre-052.1 promote). **404** unknown course; **422** no syllabus or extraction failure.

**Engineering syllabus (SP-052.3):** syllabi with Roman/dash `UNIT` blocks and prose topics (no page numbers, no `1.1` subsections) extract via `syllabus_block` parser. Units use synthetic 0-based page stubs (`unit N` → page `N-1`); topic paragraphs become section titles. Stored metadata: `outline_extraction_method: syllabus_block`.

```json
{
  "course_id": "CN",
  "rebuilt": true,
  "outline_summary": {
    "unit_count": 5,
    "unit_titles": ["Unit 1 Thermodynamics", "Unit 2 Atomic Structure"],
    "outline_quality": "medium",
    "outline_source": "extracted"
  }
}
```

**PATCH `/api/v1/courses/{course_id}/structure-mode` demote rules (SP-052.1b):** user-promoted mapped courses (CN, chemistry, etc.) may demote to `corpus` or `organized`. **Fixture courses only** (`course_id=PPL` or `outline_path_for_course` YAML) cannot demote — **400**.

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
  "outline_source": "fixture",
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

**Outline resolution order (Wave 6.5 — SP-036, updated Wave 6.6 — SP-037):**

| Priority | Source | `outline_source` |
|----------|--------|------------------|
| 1 | Course fixture YAML (PPL) | `fixture` |
| 2 | `courses.outline_data` (manual upload) | `uploaded` |
| 3 | `courses.outline_data` (TOC extracted on notes ingest or rebuild) | `extracted` |
| 4 | Live auto-stub from notes page buckets | `auto_stub` |

**TOC extraction (Wave 6.6 — no LLM; Wave 6.7 — chapter rollup; Wave 9.3 — SP-044 syllabus merge):** On `notes` ingest, the API tries PDF bookmarks then textual TOC. **`normalize_outline_chapters()`** rolls flat 20+ bookmark lists into chapter units when `Chapter`/`Unit`/`Module` markers are detected. **`syllabus_unit_merge`** (SP-044): when early pages parse as a printed syllabus TOC with page numbers (`Unit 1 … 12`, `1. Atomic Structure … 15`), sections are bucketed into those unit page spans instead of one sidebar unit per bookmark (fixes OU Chemistry 8→5 units). Fallback: merge adjacent units to 5 when outline has 6–12 units and ≥15 sections. Rejects outlines with >30 sections and no chapter structure. PPL fixture path unchanged; uploaded outlines are never overwritten.

**Optional field — `outline_granularity`:** `"chapter"` | `"section"` | `"page_stub"` — indicates display density. Stored in `courses.outline_data` for extracted/uploaded outlines; inferred as `chapter` for PPL fixture, `page_stub` for auto-stub.

**Optional field — `outline_quality` (Wave 7 — SP-039):** `"high"` | `"medium"` | `"low"` — extraction confidence. **high** = 3–12 chapter units, ≥2 sections, avg span ≥3 pages; **low** = auto_stub or page buckets.

**Extraction pipeline (Wave 7):** bookmarks → text TOC → **body heading detection** (`page.get_text("dict")`, larger/bold fonts, numbered headings) → auto-stub. All successful extracts pass `normalize_outline_chapters()` then `normalize_outline()` (merge <3-page sections, cap ≤30 sections / ≤12 units).

```json
{
  "course_id": "TEST101",
  "outline_source": "extracted",
  "outline_granularity": "chapter",
  "units": [
    { "id": "1", "title": "Thermodynamics 1", "sections": [{ "title": "Subtopic 1.1", "...": "..." }] }
  ]
}
```

**Response (404):** unknown `course_id`, or course exists with no fixture/upload/extracted/notes to derive an outline.

**Page indices:** 0-based PDF pages (matches golden set and chunk `page` metadata from notes ingest).

---

### `POST /api/v1/courses/{course_id}/outline/rebuild` (Wave 6.6 — SP-037)

Re-extract outline from existing ingested `notes` PDFs without re-upload. Useful after SP-036 auto-stub or when notes were ingested before extraction shipped.

**Response (201):** Same shape as GET, with `"outline_source": "extracted"`.

**Errors:** 404 unknown course; 409 uploaded outline locked or fixture-backed course; 422 no notes or extraction failed.

```powershell
curl.exe -X POST http://localhost:8001/api/v1/courses/TEST101/outline/rebuild
```

---

### `POST /api/v1/courses/{course_id}/outline` (Wave 6.5 — SP-036, optional upload)

Upload outline JSON matching the `DocumentOutline` shape (same fields as GET response minus `course_id` / `outline_source`). Overrides auto-stub for that course.

**Request (201):** JSON body with `document`, `page_index_base`, `page_count`, `units[]` (required).

**Response (201):** Same shape as GET, with `"outline_source": "uploaded"`.

**Errors:** 404 unknown course; 400 invalid/missing units.

```powershell
curl.exe -X POST http://localhost:8001/api/v1/courses/TEST101/outline `
  -H "Content-Type: application/json" `
  -d "{\"document\":\"Chemistry notes.pdf\",\"page_index_base\":0,\"page_count\":25,\"units\":[{\"id\":\"1\",\"title\":\"Organic Chemistry\",\"page_start\":0,\"page_end\":24,\"sections\":[{\"title\":\"Alkanes\",\"page_start\":0,\"page_end\":12}]}]}"
```

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
| `tests/test_study_layout.py` | D | Flex Study layout mode + sources API |
| `tests/test_course_documents.py` | D | Course documents list API |
| `tests/test_study_topics.py` | D | Study topics CRUD + structure_mode |
| `tests/test_topic_scoped_retrieval.py` | D | topic_ids validation + structure-mode |
| `tests/test_course_map_promotion.py` | D | Course Map eligibility + promote |
| `tests/test_course_structure.py` | D | Course structure import/confirm APIs (SP-053a) |
| `tests/test_workspace_courses.py` | D | Workspace course list/create + upload auto-create (SP-012c) |

All tests: run from `apps/api` with Postgres test DB (`studypilot_test` on port 5433).
