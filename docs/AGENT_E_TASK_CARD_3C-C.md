# Agent E — Task Card: Phase 3C-C Exam Heatmap + Student UX (Wave 1)

**Copy everything below the line into a new Cursor Composer chat (Agent E worker).**

---

You are **Agent E** for StudyPilot v2 — **web UI only**.

## Read first (mandatory)

1. `C:\Projects\studypilot-v2\docs\CURRENT_STATE.md`
2. `C:\Projects\studypilot-v2\docs\GAP_BACKLOG.md` (Wave 1 items SP-030, SP-034, MedX B2/B6)
3. `C:\Projects\studypilot-v2\docs\api-contracts.md` — `GET /api/v1/courses/{course_id}/exam/topic-frequency`
4. `C:\Projects\studypilot-v2\docs\failures-checklist.md`
5. `C:\Projects\studypilot-v2\AGENTS.md` — ownership table

## You own ONLY

- `C:\Projects\studypilot-v2\apps\web\**`

## FORBIDDEN

- `apps/api/**` (API already ships topic-frequency — do not change backend)
- `eval/golden_set.jsonl`
- `rag/retrieve.py`, `ingestion.py`, chunker, etc.

## Context (live API)

Topic frequency is **working** after OCR re-ingest:

```powershell
Invoke-RestMethod "http://localhost:8001/api/v1/courses/PPL/exam/topic-frequency"
```

Expect ~50 `total_questions_estimated`, 5 units, `coverage_note` about 26/30 pages readable, `source_documents[0].readable_pages` with many pages.

Restart uvicorn on **8001** if 404.

## Deliverables

### 1. TopicFrequencyPanel

- New component: fetch `GET /api/v1/courses/{courseId}/exam/topic-frequency` on mount / when courseId changes
- Show:
  - **Coverage warning** banner from `coverage_note` (amber if partial, green if full)
  - **Bar chart or heatmap** — unit totals; expandable or nested section counts
  - **Total** estimated questions
- Handle loading, 404, network error gracefully
- Add types + `api/topicFrequencyClient.ts` (mirror `queryClient.ts` pattern)

### 2. Student mode (SP-030)

- `debugEnabled` default **`false`** in `App.tsx`
- When debug off, **hide**: `ChunkInspector`, `DebugPanel`, golden-miss footer text
- When debug off, **still show**: `TopicFrequencyPanel`, query form, answer + sources
- `TocBrowser` may stay visible only when debug on OR when last query has chunks (your call — prefer debug-only for TOC-from-query)

### 3. MedX trust surface (B2, SP-034)

- Hero/subtitle or footer trust row:
  - “Answers cite your PDF page”
  - “Local embeddings — notes stay on your machine”
  - “Won’t answer outside your materials” (OOC gate)
- Replace footer line “N golden misses loaded” with trust bullets

### 4. Citation cards (B3/B6)

- Enhance `SourcesList.tsx`: card layout with filename, page, excerpt
- If `retrieval_debug.chunks` available, match source to chunk by filename+page and show `section_title` / `toc_path` when present

### 5. Example question chips (optional, quick win)

- 2–3 clickable example questions under query form (e.g. “What is a lexeme?”) that prefill the textarea

### 6. Cleanup

- `goldenMisses.ts` — empty array + comment that eval is 100%; ChunkInspector handles empty list

## UX rules (MedX B7 — do NOT)

- No fake match percentages or AI hype
- Only show counts from API (`total_questions_estimated`, unit counts)
- Every nav/link must work or be hidden

## Styling

- Match existing `App.css` panel/card patterns
- Mobile: usable at 390px width on main path (query + answer + heatmap)

## Acceptance

1. `npm run build` in `apps/web` passes
2. With API on 8001, heatmap shows PPL unit bars without running a query
3. Default view has **no** rerank scores or golden miss inspector
4. Debug checkbox reveals dev panels
5. Paste screenshot or confirm: student can ask question and see answer + citations only

## Verify

```powershell
cd C:\Projects\studypilot-v2\apps\web
npm run dev
# Browser: http://localhost:5173
```

## Return to lead chat

- Files changed list
- Screenshot description
- Any API contract gaps (should be none)

**Do NOT** edit `.cursor/plans/*.plan.md`
