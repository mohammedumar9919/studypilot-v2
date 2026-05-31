# Agent D — Task Card: Outline API (Wave 2 — after Agent E)

**Copy below into a new Cursor chat when Wave 1 heatmap is merged.**

> **Wave 1 complete (2026-05-30).** Agent E shipped heatmap + student UX. Proceed with outline API.

---

You are **Agent D** for StudyPilot v2 — **API only**.

## Read first

- `docs/CURRENT_STATE.md`, `docs/GAP_BACKLOG.md` (SP-010)
- `docs/api-contracts.md` — add new route with version note
- `eval/fixtures/ppl/ppl_outline.yaml`

## Own ONLY

- `apps/api/app/main.py` (new route)
- `apps/api/app/services/` — new small module e.g. `course_outline.py` OR extend existing outline loader
- `apps/api/tests/test_course_outline.py`

## FORBIDDEN

- `apps/web/**` (Agent E consumes API)
- `retrieve.py`, `ingestion.py` unless orchestrator approves

## Deliverable

`GET /api/v1/courses/{course_id}/outline`

Response: units with id, title, page ranges, sections (from `ppl_outline.yaml` for PPL v1).

404 if unknown course. No LLM.

## Acceptance

- pytest new test passes
- `curl http://localhost:8001/api/v1/courses/PPL/outline` returns 5 units
- Document in `api-contracts.md`

## Handoff to Agent E

Paste response JSON shape for TOC sidebar task.

---

# Agent E — Task Card: Course TOC Sidebar (Wave 2 — after outline API)

**Copy below after Agent D ships outline endpoint.**

> **Wave 2 complete (2026-05-30).** Agent D outline API + Agent E `CourseOutlineSidebar`. Wave 3 next.

---

You are **Agent E** — **web only**.

## Read first

- `docs/AGENT_E_TASK_CARD_3C-C.md` (same ownership rules)
- New outline API contract in `api-contracts.md`

## Deliverable

- Sidebar tree: Unit → Section from **outline API** (not `retrieval_debug.chunks`)
- Works **before** any query is run
- Click section → prefill question textarea with section title
- MedX “browse before search” pattern (GAP B1)

## Own ONLY

- `apps/web/**`

## Acceptance

- Open app, select PPL, see full 5-unit tree without submitting a query
- Click “Unit 2 > Expressions…” → question prefilled

---

# Agent C / B — no active task

Retrieval at **100%**. PYQ OCR done. Do not assign unless regression or new course ingest.

---

## Wave 3 — COMPLETE (2026-05-31)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | `POST /api/v1/query/stream` (SSE) | pytest 13/13 |
| E | Stream UI + fallback | `npm run build` PASS |

Archived cards: Wave 3 Agent D/E sections in git history. Contract: [api-contracts.md](api-contracts.md).

---

## Wave 3.5 — COMPLETE (2026-05-31)

| Deliverable | Verification |
|-------------|--------------|
| Git LFS for PPL PDFs | Fresh clone → real PDFs (not pointers) |
| `retrieval-gate` in CI | Executes (skip step not run); [PR #1](https://github.com/mohammedumar9919/studypilot-v2/pull/1) |
| `api-and-web` | pytest 56/56 PASS |

Repo: `https://github.com/mohammedumar9919/studypilot-v2.git` — merge PR #1 to land on `main`.

---

## Wave 4a — COMPLETE (2026-05-31)

| Deliverable | Verification |
|-------------|--------------|
| Design tokens (`tokens.css`, `wave4a-theme.css`) | Warm dark-charcoal + teal system |
| Premium motion (CSS-only) | Ambient streaks, journey strip, slide-in sources, bar-grow heatmap |
| `StudyJourneyStrip` + stage pill | Synced to SSE stages |
| Behavior preserved | Stream, fallback, debug, heatmap, outline |
| Build | `npm run build` PASS |

---

## Wave 4b — COMPLETE (2026-05-31)

| Agent | Deliverable | Verification |
|-------|-------------|--------------|
| D | `POST .../documents` upload API | pytest 10/10 |
| E | Upload UI + empty states (SP-031) | `npm run build` PASS |

Key files: `uploadClient.ts`, `DocumentUploadPanel.tsx`, `EmptyCourseState.tsx`, journey strip Upload/Index sync, outline+heatmap `refreshToken`.

---

## Wave 5 — Mobile audit (NEXT — Agent E, SP-033)

> Pilot polish before cram modes / auth. Target **390px** width (iPhone 12/13/14).

**Copy into new Agent E Composer chat:**

---

You are **Agent E** for StudyPilot v2 — **web UI only** (Wave 5, SP-033).

## Skill invocation (mandatory)

- Invoke **using-superpowers** first.
- Invoke **ui-ux-pro-max** before layout changes.
- Use **verification-before-completion** — `npm run build` + manual check at **390px** and **480px**.

## Read first

1. `C:\Projects\studypilot-v2\docs\CURRENT_STATE.md`
2. `C:\Projects\studypilot-v2\docs\DESIGN_DIRECTION_WAVE4A.md`
3. `C:\Projects\studypilot-v2\apps\web\src\wave4a-theme.css` — existing `@media (max-width: 390px)` rules
4. `C:\Projects\studypilot-v2\apps\web\src\App.css`, `App.tsx`
5. All main-path components: upload, query, answer, sources, journey strip, outline, heatmap

## You own ONLY

- `C:\Projects\studypilot-v2\apps\web\**`

## FORBIDDEN

- `apps/api/**`
- Breaking Wave 4a motion or Wave 4b upload/stream behavior

## Audit checklist (fix what fails)

Test at **390px** in Chrome DevTools — student mode (`debugEnabled: false`):

| Flow | Must work |
|------|-----------|
| Empty state + upload panel | No horizontal scroll; readable text; tappable CTAs (≥44px touch) |
| Indexing state | Stage pill + timer visible; CTA disabled clear |
| Journey strip (5 steps) | Horizontal scroll OK; active step visible; no overlap with header |
| Query form + example chips | Chips wrap; submit reachable |
| Streaming query | Sources slide-in; answer readable; cursor visible |
| Outline sidebar | Collapsible or stacks below main column — full tree usable |
| Heatmap | Bars + labels readable; card not clipped |
| Trust badges / header | Wrap cleanly; gradient title not truncated badly |

Also spot-check **900px** breakpoint (`App.css`) — two-column → single column transition smooth.

## Deliverables

1. CSS fixes in `wave4a-theme.css` / `App.css` (prefer tokens; minimal JSX unless collapse toggle needed)
2. If sidebar needs mobile toggle — small `useMediaQuery` or CSS-only collapse (match existing patterns)
3. Document any remaining known limits in handoff (e.g. heatmap table on 320px)

## Acceptance

1. `npm run build` PASS
2. No horizontal overflow on main column @ 390px for full student journey
3. Upload → query → stream path usable one-handed
4. Wave 4a theme/motion preserved; `prefers-reduced-motion` still honored

## Verify

```powershell
cd C:\Projects\studypilot-v2\apps\web
npm run build
npm run dev
# DevTools → 390 × 844, student mode
```

## Return to Lead chat

- Checklist pass/fail table
- Files changed
- Screenshots description @ 390px

**Do NOT** edit `.cursor/plans/*.plan.md`

---

## Optional next waves (after Wave 5)

| ID | Item | Notes |
|----|------|-------|
| SP-033 | Mobile audit @ 390px | Wave 5 — **active** (see above) |
| SP-032 | Cram presets | Summary / flashcards — card TBD |
| SP-020 | docker-compose full profile | Ops |
| SP-012 | Auth + workspace | Defer pilot |

**Agents B/C/D/E:** idle unless regression or new feature wave.

---

## Wave 4b — archived

Agent D + E cards in git history. Contract: [api-contracts.md](api-contracts.md).

## Wave 4a — archived

Design brief: [DESIGN_DIRECTION_WAVE4A.md](DESIGN_DIRECTION_WAVE4A.md). Agent E card in git history.
