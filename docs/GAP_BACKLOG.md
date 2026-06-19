# StudyPilot v2 — Gap Backlog (reconciled)

**Source:** `StudyPilot-v2-Gap-Backlog-and-MedX-Learnings.md` (2026-05-29)  
**Reconciled:** 2026-06-15 against repo state (Phase S DONE; **Phase B SP-012 DONE**)  
**MedX reference:** UX/information architecture only — not backend model

---

## Status legend

| Status | Meaning |
|--------|---------|
| **DONE** | Shipped and verified |
| **PARTIAL** | Started; gap remains |
| **OPEN** | Not started |
| **DEFER** | Post pilot-ready |

---

## P0 — Accuracy and correctness

| ID | Item | Status | Notes |
|----|------|--------|-------|
| SP-001 | 90% precision@5 | **DONE** | **100%** (40/40) @ 0.35; see `PHASE1B_SUMMARY` |
| SP-002 | Golden miss UI workflow | **DONE** | Dev-only via checkbox; `GOLDEN_MISSES` empty at 100% eval |
| SP-003 | CI regression gate | **DONE** | Git LFS + `retrieval-gate` executes in CI; `api-and-web` 56/56; merge [PR #1](https://github.com/mohammedumar9919/studypilot-v2/pull/1) |
| SP-004 | ~60s query latency | **PARTIAL** | SSE + progressive UI DONE; SP-004a adds `retrieval_debug.timings_ms` + optional retrieval timeout |

---

## P1 — Plan phases

| ID | Item | Status | Notes |
|----|------|--------|-------|
| SP-010 | Course TOC browse (pre-query) | **DONE** | Outline API (Agent D) + `CourseOutlineSidebar` (Agent E) |
| SP-011 | PYQ topic frequency | **DONE** | OCR + API + CLI + heatmap UI (Agent E Wave 1) |
| SP-012 | Auth + workspace + multi-page UI | **DONE** | Phase B Wave 10 — 012a `c94ab42`, 012b `6a79564`, 012c `a93bf2b`, 012d `921a63b` |
| SP-013 | Durable ingest queue | **DONE** | SP-013a–c complete (worker + async API + web poll) |
| SP-014 | Observability / RAGAS | **DEFER** | After CI stable |
| SP-015 | Exam intelligence | **DONE** | Exam preset + heatmap (SP-015 D+E) |
| SP-016 | 95% pre-installer | **DONE** | 100% on golden set; CI lock next |
| SP-017 | In-app PDF upload | **DONE** | API (D) + UI (E) Wave 4b |
| SP-018 | Second course (Chemistry) | **DONE** | Waves 6.5–7 + SP-044/044.1 outline fixes |
| SP-019 | Contextual chunk prefixes | **OPEN** | Quality uplift if regressions appear |
| SP-020 | docker-compose full profile | **OPEN** | Wave 3 |

---

## P2 — Product and UX (MedX-informed)

| ID | Item | Status | Wave |
|----|------|--------|------|
| SP-030 | Student mode (hide debug) | **DONE** | 1 |
| SP-031 | Onboarding / empty states | **DONE** | Wave 4b — `EmptyCourseState`, upload journey |
| SP-032 | Cram presets (summary, flashcards) | **DONE** | Wave 6 — study / summary / flashcards (D+E) |
| SP-033 | Mobile responsive audit | **DONE** | Wave 5 — 390px full pass; 320px tight labels noted |
| SP-034 | Trust / branding surface | **DONE** | 1 |
| SP-035 | Visual design / polish pass | **DONE** | Wave 4a — `tokens.css`, warm+teal, NTR-inspired motion, CSS-only |
| SP-036 | Generic course outline + PYQ heatmap | **DONE** | Wave 6.5 — page-stub fallback; 6.6 adds real TOC |
| SP-037 | Real TOC extraction + topic-aware heatmap | **DONE** | Wave 6.6 |
| SP-038 | Chapter-level outline rollup (PPL-like density) | **DONE** | Wave 6.7 |
| SP-039 | Universal outline pipeline (heading fallback, quality score, dynamic retrieval) | **DONE** | Wave 7 |
| SP-041 | LLM outline assist (auto low + manual improve) | **OPEN** | Wave 8 — optional |

### Phase A.5 — Exam Truth (Wave 9)

| ID | Item | Status | Notes |
|----|------|--------|-------|
| SP-015.2 | Exam index status + exam gate | **DONE** | `exam/status`, preset-scoped gate 0.25 |
| SP-043 | PPL OCR 29/30 | **DONE** | `ingest_ppl_pyq.ps1` |
| SP-044 | Chemistry syllabus TOC merge | **DONE** | Page-number syllabus merge |
| SP-044.1 | Chemistry UNIT X.Y rollup | **DONE** | Body anchors, sparse units, math-safe X.Y |
| SP-042a | `exam_questions` schema + ingest parser | **DONE** | 25/25 page-3 parity |
| SP-042b | Exam retrieval over question records | **DONE** | preset-scoped; smoke PASS |
| SP-042a.1 | Web `parsed` heatmap source | **DONE** | types + banner |
| SP-042 | PYQ truth layer (umbrella) | **DONE** | 042a + 042b + 042a.1 |
| SP-042c | PYQ parser expansion (377 questions) | **DONE** | Parser + fixtures; classification deferred (042d) |
| SP-042d | PYQ unit classification backfill | **DEFER** | Phase S — after flex study UX stable |

### Phase S — Flex Study

| ID | Item | Status | Notes |
|----|------|--------|-------|
| SP-050a | Quick Study default — layout API + Sources panel | **DONE** | `study-layout`; corpus hides TOC/heatmap; pytest 8/8; smoke PASS |
| SP-050b | Document list + `source_ids` query filter | **DONE** | pytest 25/25; UAT subset filter PASS; smoke 100% |
| SP-050c | Upload intent metadata | **DONE** | quick skips outline extract; pytest 31/31; build PASS |
| SP-051a | `study_topics` + `structure_mode` | **DONE** | Alembic 004; CRUD API; pytest 18/18 |
| SP-051b | Organized Study UI | **DONE** | TopicsPanel + topic_ids; pytest 34/34; build PASS |
| SP-052 | Course Map promotion gate | **DONE** | Eligibility + promote + UI tabs; pytest 19/19 |
| SP-052.1 | Syllabus-driven promote outline | **DONE** | promote + rebuild-outline in course_map.py |
| SP-053a | Course structure schema + import | **DONE** | Alembic 005; preview/confirm |
| SP-053a.1 | Hierarchical parts + parser | **DONE** | Alembic 006; CN live UAT |
| SP-053a.1b | Parser hotfix | **DONE** | CN engineering syllabus |
| SP-053b | M2M assignments + structure scope | **DONE** | unit/part/subtopic_ids query |
| SP-053c | Unified Course structure UI | **DONE** | Sources \| Course structure tabs |
| SP-053d | Modular syllabus depth | **DONE** | Data Science + CN regression |

### MedX borrow list (actionable)

| Pattern | StudyPilot task | Wave | Status |
|---------|-----------------|------|--------|
| Hero + CTA | Example question chips + “Ask your notes” | 1 | DONE |
| Trust badges | Citations, local embed, OOC messaging | 1 | DONE |
| Unit landing cards | 5 PPL unit cards | 2 | DONE |
| Exam focus stats | Topic frequency heatmap | 1 | DONE |
| Citation cards | Section + page in SourcesList | 1 | DONE |
| 6-step journey | Upload → index → ask → cite → review → exam | 4 | **DONE** (all presets + journey focus) |

---

## P3 — Campus (unchanged)

SP-040–046 remain **DEFER** until CI @ 100% + student pilot.

---

## Anti-patterns (still enforce)

See [failures-checklist.md](failures-checklist.md): no vector-only, no past_paper in study, no exam LLM JSON extract, no sanitizer ladder, no golden_set edits without human approval.

---

## Implementation waves

| Wave | Focus |
|------|--------|
| **0** | Docs + council skills/rules |
| **1** | Agent E: heatmap + student UX + trust — **DONE** |
| **2** | Outline API + course TOC sidebar — **DONE** |
| **3** | CI gate + streaming — **DONE** |
| **3.5** | Git LFS + cloud CI retrieval gate — **DONE** (2026-05-31) |
| **4a** | Visual design pass (SP-035) — **DONE** (2026-05-31) |
| **4b** | Upload + onboarding (SP-017, SP-031) — **DONE** (2026-05-31) |
| **5** | Mobile audit (SP-033) — **DONE** (2026-05-31) |
| **5.5** | Course naming on upload — **DONE** (2026-05-31) |
| **6** | Cram presets (SP-032) — **DONE** (2026-05-28) |
| **6.5** | Generic outline + PYQ heatmap (SP-036) — **DONE** (2026-05-28) |
| **6.6** | Real TOC + keyword heatmap (SP-037) — **DONE** |
| **6.7** | Chapter rollup (SP-038) — **DONE** |
| **7** | Universal outline pipeline (SP-039) — **DONE** |
| **8** | LLM outline assist (SP-041) — optional |
| **9** | Phase A.5 — Exam Truth — **DONE** (2026-06-04) |
| **S** | Phase S — Flex Study (SP-050a–053d) — **DONE** (2026-06-02) |
| **10** | Phase B — auth + multi-page UI (SP-012) — **DONE** (2026-06-02; reconciled 2026-06-15) |
| **SP-015** | Exam preset — **DONE** |

See [CURRENT_STATE.md](CURRENT_STATE.md) and [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md).
