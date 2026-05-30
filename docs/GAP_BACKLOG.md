# StudyPilot v2 — Gap Backlog (reconciled)

**Source:** `StudyPilot-v2-Gap-Backlog-and-MedX-Learnings.md` (2026-05-29)  
**Reconciled:** 2026-05-31 against repo state  
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
| SP-003 | CI regression gate | **PARTIAL** | Local gate @ 100% verified; GitHub CI needs PDF fixtures (Git LFS) |
| SP-004 | ~60s query latency | **PARTIAL** | SSE + progressive UI DONE (Wave 3); wall-clock still ~60s; Phase 4 GPU optional |

---

## P1 — Plan phases

| ID | Item | Status | Notes |
|----|------|--------|-------|
| SP-010 | Course TOC browse (pre-query) | **DONE** | Outline API (Agent D) + `CourseOutlineSidebar` (Agent E) |
| SP-011 | PYQ topic frequency | **DONE** | OCR + API + CLI + heatmap UI (Agent E Wave 1) |
| SP-012 | Auth + workspace | **DEFER** | Phase 4 |
| SP-013 | Durable ingest queue | **DEFER** | Phase 4 |
| SP-014 | Observability / RAGAS | **DEFER** | After CI stable |
| SP-015 | Exam intelligence | **PARTIAL** | Frequency done; exam preset later |
| SP-016 | 95% pre-installer | **DONE** | 100% on golden set; CI lock next |
| SP-017 | In-app PDF upload | **OPEN** | **4b** (after SP-035) |
| SP-018 | Second course (Chemistry) | **DEFER** | Phase 5+ |
| SP-019 | Contextual chunk prefixes | **OPEN** | Quality uplift if regressions appear |
| SP-020 | docker-compose full profile | **OPEN** | Wave 3 |

---

## P2 — Product and UX (MedX-informed)

| ID | Item | Status | Wave |
|----|------|--------|------|
| SP-030 | Student mode (hide debug) | **DONE** | 1 |
| SP-031 | Onboarding / empty states | **OPEN** | **4b** (after SP-035) |
| SP-032 | Cram presets (summary, flashcards) | **OPEN** | **4b** |
| SP-033 | Mobile responsive audit | **PARTIAL** | Outline collapsible @ 390px; full audit still open |
| SP-034 | Trust / branding surface | **DONE** | 1 |
| SP-035 | Visual design / polish pass | **OPEN** | **4a** — after Wave 3.5 (Git LFS), before upload (Option A) |

### MedX borrow list (actionable)

| Pattern | StudyPilot task | Wave | Status |
|---------|-----------------|------|--------|
| Hero + CTA | Example question chips + “Ask your notes” | 1 | DONE |
| Trust badges | Citations, local embed, OOC messaging | 1 | DONE |
| Unit landing cards | 5 PPL unit cards | 2 | DONE |
| Exam focus stats | Topic frequency heatmap | 1 | DONE |
| Citation cards | Section + page in SourcesList | 1 | DONE |
| 6-step journey | Upload → index → ask → cite → review → exam | 4 | OPEN |

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
| **3** | CI gate + streaming — **DONE** (local gate @ 100%; GitHub retrieval gate needs LFS) |
| **3.5** | Git LFS + cloud CI retrieval gate | **NEXT** |
| **4a** | Visual design pass (SP-035) — **after 3.5, before upload** (Option A) |
| **4b** | Upload (SP-017), onboarding (SP-031), cram modes (SP-032) |

See [CURRENT_STATE.md](CURRENT_STATE.md) and [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md).
