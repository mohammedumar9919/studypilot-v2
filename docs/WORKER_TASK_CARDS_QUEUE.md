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

## Wave 3.5 — Git LFS + cloud CI gate (NEXT — Lead / ops)

> Unblocks SP-003 full retrieval gate in GitHub Actions. No app code unless workflow needs a path tweak.

**Copy into Lead chat or ops-focused Composer session:**

---

You are **Lead / ops** for StudyPilot v2 — **CI fixtures only**.

## Skill invocation

- Invoke **using-superpowers** first.
- Use **verification-before-completion** — push a test branch and confirm `retrieval-gate` job runs (or document why not).

## Read first

1. `C:\Projects\studypilot-v2\docs\CURRENT_STATE.md`
2. `C:\Projects\studypilot-v2\docs\CI_SETUP.md`
3. `C:\Projects\studypilot-v2\.github\workflows\eval-gate.yml`

## You own ONLY

- `.gitattributes` (LFS track rules for `eval/fixtures/ppl/*.pdf`)
- `docs/CI_SETUP.md` (update steps after LFS)
- `docs/CURRENT_STATE.md` — mark SP-003 GitHub gate **DONE** when verified
- Optional: `.github/workflows/eval-gate.yml` if job conditions need LFS checkout

## FORBIDDEN

- `retrieve.py`, `rerank.py`, `gate.py`, `golden_set.jsonl`
- `apps/web/**`, `apps/api/**` (unless workflow env only)

## Deliverable

1. Install / enable **Git LFS** locally.
2. Track PPL PDFs: `eval/fixtures/ppl/*.pdf` (and any sibling fixtures the workflow expects, e.g. `PPL notes.pdf`).
3. Migrate existing local PDFs into LFS pointers; commit pointers (not raw blobs in git history if avoidable — use fresh commit or `git lfs migrate` per team policy).
4. Document one-time clone steps: `git lfs install` + `git lfs pull`.
5. Verify GitHub Actions `retrieval-gate` runs full gate when PDF exists in checkout.

## Acceptance

1. Fresh clone + LFS pull → `eval/fixtures/ppl/PPL notes.pdf` present locally
2. GitHub PR shows `retrieval-gate` job executing (not skipped)
3. `docs/CI_SETUP.md` updated with LFS clone instructions

## Verify (user PowerShell — long gate)

```powershell
cd C:\Projects\studypilot-v2
git lfs pull
.\scripts\quick_gate.ps1
```

**Do NOT** edit `.cursor/plans/*.plan.md`

---

## Wave 4a — Visual design pass (after 3.5 — Option A)

> **Sequence locked:** 3.5 Git LFS → **4a styling (SP-035)** → 4b upload/onboarding.  
> **Step 1 (you + Lead):** 30–60 min — pick references, type scale, primary color, density. No code yet.  
> **Step 2:** Lead writes full Agent E card below. **Step 3:** Agent E implements CSS tokens + component pass.

**Agent E card:** TBD after styling session. Will include ui-ux-pro-max, `apps/web/**` only, tie-in SP-033 mobile audit.

**Do not start 4a until Wave 3.5 acceptance** (GitHub `retrieval-gate` runs or documented blocker).

---

## Wave 4b — Upload + onboarding (after 4a)

- Agent D: `POST /api/v1/courses/{id}/documents` (SP-017) — card TBD
- Agent E: upload UI + empty states (SP-031) — inherits 4a design tokens
