# StudyPilot v2 — Master Plan (runtime companion)

**Effective:** 2026-06-02  
**Source:** [Flex Study master plan](C:\Users\Owner\.cursor\plans\flex_study_master_plan_17723ead.plan.md) + [Phase B SP-012 plan](C:\Users\Owner\.cursor\plans\phase_b_sp-012_auth_168f8090.plan.md)  
**Runtime truth for status:** [CURRENT_STATE.md](CURRENT_STATE.md)

---

## Product model

Three study layers, one chatbox:

1. **Quick Study (corpus)** — default for new non-PPL courses; Sources panel; no TOC sidebar required
2. **Organized Study** — user topics or course structure tree; optional `topic_ids` / structure scope on query
3. **Course Map (mapped)** — syllabus-driven outline sidebar + heatmap; PPL/Chemistry fixtures unchanged

Hybrid retrieval invariant: **RRF + rerank + gate**; study presets exclude `past_paper`; local FastEmbed only.

---

## Phase completion

| Phase | Status | Notes |
|-------|--------|-------|
| A — Study workspace | **DONE** | Presets, outline pipeline, exam mode |
| A.5 — Exam Truth | **DONE** | Wave 9; frozen baseline |
| **S — Flex Study** | **DONE** | SP-050a–053d; user UAT CN + Data Science PASS |
| **B — Product shell** | **ACTIVE** | SP-012 Clerk auth + multi-page UI |
| C — Platform | Open | SP-013 queue, SP-045 router, SP-014 |
| E — Exam expansion | **DEFER** | SP-042d, exam golden — after Phase B |

---

## Phase S deliverables (complete)

| Slice | Deliverable |
|-------|-------------|
| SP-050a | `GET .../study-layout`; corpus Sources panel |
| SP-050b | `GET .../documents`; `source_ids` query filter |
| SP-050c | Upload intent metadata |
| SP-051a | `study_topics` + `structure_mode` |
| SP-051b | Organized Study UI + `topic_ids` |
| SP-052 | Course Map promotion gate |
| SP-052.1 | Syllabus extract on promote + rebuild-outline |
| SP-053a | Course units/subtopics schema + import preview/confirm |
| SP-053a.1 | `course_parts` + hierarchical parser |
| SP-053a.1b | CN live-shape parser hotfix |
| SP-053b | M2M document assignment + structure query scope |
| SP-053c | Unified Course structure web tab |
| SP-053d | Modular syllabus depth (flat vs parts per unit) |

**Phase S success criteria (met):**

- Any uploaded PDF works in Quick Study without correct TOC
- Source and structure scope filter retrieval correctly
- PPL/Chemistry mapped courses unchanged
- Eval: **100% precision@5**, **OOC 10/10** (smoke on 053d; no gate/retrieve changes)
- CN + Data Science course structure UAT PASS

---

## Phase B — SP-012 (active)

**Human Gate 0:** Clerk — React SDK on web; FastAPI JWT verification; dev bypass `STUDYPILOT_AUTH_DISABLED=1` for pytest/eval.

**Sequential slices (no parallel 012b + 012d):**

| Slice | Owner | Goal |
|-------|-------|------|
| SP-012a | Agent D | Alembic 007: users, workspaces, workspace_members; `courses.workspace_id`; System Demo backfill |
| SP-012b | Agent D | Clerk JWT middleware + route guards on all course/query routes |
| SP-012c | Agent D | `GET/POST .../workspaces/me/courses`; workspace-scoped upload create |
| SP-012d | Agent E | react-router + Clerk React; Login / Courses / Study pages |

**Forbidden:** `retrieve.py`, `rerank.py`, `gate.py` (except auth wiring in `main.py`); `eval/golden_set.jsonl`.

**Phase B done when:** Clerk sign-in, workspace-scoped courses, study UI parity, smoke eval **100%/10/10**.

---

## Deferred (do not assign during Phase B)

- SP-042d PYQ unit classification
- `eval/exam_golden_set.jsonl` expansion
- Exam prediction / heatmap balance work (Phase E)
- SP-012 blocked Phase C items (SP-013, SP-045, SP-014)

---

## Council governance

Every schema/auth slice: **Stage 2 mandatory** (`models.py`, `api-contracts.md`, `main.py`).  
Skills: `.cursor/skills/council-propose-slice`, `council-review-slice`, `council-merge-slice`.

---

## Environment

| Service | URL |
|---------|-----|
| API | `localhost:8002` |
| Web | `localhost:5173` |
| Postgres | `localhost:5433` |

Eval: `scripts/run_phase1b_eval_fast.ps1` only (never 4-sweep). Smoke: `scripts/quick_gate.ps1 -Smoke`.
