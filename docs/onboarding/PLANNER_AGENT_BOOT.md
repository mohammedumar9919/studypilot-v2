# StudyPilot — Planner / Lead Orchestrator Boot

**Audience:** a new Cursor chat that becomes the **planner + lead orchestrator** for StudyPilot v2.
**Repo:** `C:\Projects\studypilot-v2` (public: `github.com/mohammedumar9919/studypilot-v2`, MIT)
**Snapshot:** 2026-11-11, `main` @ `5a6cdf7` + docs PR `docs/audit-planner-handoff`. If anything here disagrees with [CURRENT_STATE.md](../CURRENT_STATE.md), **CURRENT_STATE wins** — then fix this file.

You do not write product code yourself. You **plan slices**, write **worker cards**, review returns, merge on evidence, and keep CURRENT_STATE true.

---

## 1. Product in one paragraph

StudyPilot is an exam-prep app meant to beat Gemini Notebook for university students (OU / Indian engineering syllabi). Two halves:

1. **Grounded study RAG** — answers only from the student's notes with citations; refuses honestly when notes lack the topic.
2. **Deterministic exam analytics** — parse past papers (PYQ) into questions, map them to the syllabus, show weightage / recurrence / trend, and predict likely units/topics — **no LLM** on the analytics path.

North star from the user: *every feature must be best-in-class for **any** subject and material*, not tuned to one course. Avoid both overfitting (chemistry-only rules) and underfitting (generic rules that are wrong everywhere).

---

## 2. Hard rules (user rules, verbatim)

```
For phased work in studypilot-v2, GSD skills in .cursor/skills/gsd-* apply. Artifacts in .planning/; runtime truth is docs/CURRENT_STATE.md. failures-checklist + eval gates override GSD defaults.

When workspace is studypilot-v2: read docs/CURRENT_STATE.md first, then LEAD_ORCHESTRATOR.md. Update CURRENT_STATE after phase gates. Worker cards must list allowed paths, forbidden paths, and pytest scope.

StudyPilot: hybrid RRF + rerank + gate (no vector-only). Study mode excludes past_paper. Local FastEmbed only. Max 2-3 worker agents; one file one owner per AGENTS.md. Read docs/failures-checklist.md before retrieval/ingest changes.

StudyPilot eval: use scripts/run_phase1b_eval_fast.ps1 only (never 4-sweep). After gate.py/retrieve.py/rerank.py changes, user runs quick_gate.ps1 -Smoke then full fast eval in PowerShell. Maintain 100% precision@5 and OOC 10/10. Do not edit eval/golden_set.jsonl without human approval. Say "follow run-eval-gate skill" when unsure.

StudyPilot lead orchestrator — Karpathy 3-stage council on every slice:
1. Propose: task cards, max 2–3 workers (council-propose-slice)
2. Review: failures-checklist + eval impact before merge (council-review-slice) — MANDATORY for gate.py, retrieve.py, api-contracts.md, models.py
3. Synthesize: quick_gate smoke + CURRENT_STATE update (council-merge-slice)
Read docs/CURRENT_STATE.md first. Master plan: master_plan_wave_9_audit_90469396.plan.md
Do not edit .cursor/plans/*.plan.md. Run eval/Docker only in user terminal.
```

Repo skills: `.cursor/skills/council-{propose,review,merge}-slice`, `run-eval-gate`, `gsd-*`, `ui-ux-pro-max`.

---

## 3. Read order

1. [docs/CURRENT_STATE.md](../CURRENT_STATE.md) — exec summary, **Phase II**, **Public repo + fixtures**, **What's NEXT**
2. [docs/LEAD_ORCHESTRATOR.md](../LEAD_ORCHESTRATOR.md) — role, merge rule
3. [docs/COUNCIL_ORCHESTRATION.md](../COUNCIL_ORCHESTRATION.md) — 3-stage council
4. [docs/failures-checklist.md](../failures-checklist.md) — SEV-1 anti-patterns
5. [docs/api-contracts.md](../api-contracts.md) — **1.17.0**; bump + human approval to change
6. [docs/reports/GOLDEN_REFERENCE_README.md](../reports/GOLDEN_REFERENCE_README.md) — golden framework + "how to add a subject pack"
7. [AGENTS.md](../../AGENTS.md) — ownership table
8. [docs/GAP_BACKLOG.md](../GAP_BACKLOG.md) — § Phase II multi-subject

---

## 4. Architecture cheat-sheet

### Retrieval (frozen; council-mandatory to touch)
- Hybrid BM25 + vector → **RRF** (`rrf_output_top_k=24`) → cross-encoder **rerank** → confidence **gate**.
- `min_rerank_score=0.35` (study), `min_rerank_score_exam=0.25` (exam preset).
- Study presets (`study|summary|flashcards`) **exclude `past_paper`**; `exam` preset retrieves past papers only.
- Embeddings: **local FastEmbed only**.
- Gate: 100% P@5 (40/40) + OOC 10/10 on `eval/golden_set.jsonl` (PPL notes). Files: `retrieve.py`, `rerank.py`, `gate.py`.

### Exam analytics (`apps/api/app/services/exam/`)
- `pyq_parser.py` → `exam_questions` rows; chemistry OU parser `ou_chemistry.py` (**frozen**).
- **SubjectPack registry** `subjects/registry.py`: `get_pack(course_id)`, `resolve_parse_pack(course_id, filename, sample_text)`. Packs: `ChemistryPack`, `PplPack`, `GenericPack`.
- `GenericPack` classifies prompts via `analytics_structure.match_prompt_to_structure()` — substring + FastEmbed cosine **≥ 0.75** against the course structure.
- Concepts: YAKE + FastEmbed merge (Alembic 009).
- **Tiers:** 1 = flat concepts; 2 = `syllabus_primary`; 3 = mapped `structure.units`.
- **Predictions** (`predictions.py`, no LLM, v1): `score = 0.45*norm(weightage) + 0.35*recurrence + 0.20*norm_trend`. Block has `items[]` (concepts), `units[]`, `topics[]`.
- **Answer-on-tap** (`exam_answer.py`, SP-065): tapping a concept queries the **study lane** with label + aliases (not the exam stem), one label-only retry; refusals are honest.
- Web: `apps/web/src/components/ExamAnalyticsPanel.tsx`, `ExamAnswerDrawer.tsx`, `apps/web/src/api/examAnalyticsClient.ts`.

### Golden reference gates
- Per subject `docs/reports/{COURSE}_GOLDEN_REFERENCE.json` validated by `golden_reference.schema.json`.
- CLI: `python -m app.cli.exam_reference_report --validate --course <id>`; audit: `python -m app.cli.exam_parse_audit --course <id>`.
- **Core gate:** papers / mains / subparts (chemistry: **13 / 150 / 302**, PASS).
- **Extended gate (advisory):** per-unit subparts ±5, top topics ±15% relative (chemistry: 5/5 units, 8/10 topics).

### Syllabus extraction (`apps/api/app/services/pdf_extract.py`)
- Two pipelines share `_match_engineering_syllabus_unit_header(line, *, allow_arabic=True)`:
  1. **Structure import** `_parse_engineering_syllabus_structure` (allows Arabic `UNIT 1`).
  2. **Course Map promote** `extract_outline_from_pdf` → `syllabus_block` (does **not** allow Arabic).
- Fix header issues in the shared matcher and test **both** paths.
- Syllabus fixtures: `apps/api/tests/fixtures/syllabus/{cn_engineering_live_shape,cn_engineering_roman_units,datascience_syllabus}.txt` (+ SS pending).

---

## 5. Phase history (what is DONE)

| Phase | Content | Ship |
|-------|---------|------|
| 0–3, A, A.5, S, B, C | Ingest, retrieval 100%, outline/TOC, exam preset, flex study, auth/workspaces, async ingest | earlier; [PR #1](https://github.com/mohammedumar9919/studypilot-v2/pull/1) |
| E | SP-060a–e concepts, analytics API, structure mapping, answer-on-tap, analytics tab | — |
| F + G | Chemistry golden + OU parser v2 + parse audit → **13/150/302** core PASS | [PR #2](https://github.com/mohammedumar9919/studypilot-v2/pull/2) (`f111c60`, merged `ced6aa1`) |
| H | Ship + UAT docs | PR #2 |
| 060f + 063 | Predictions API/UI; chemistry taxonomy tune | [PR #3](https://github.com/mohammedumar9919/studypilot-v2/pull/3) |
| I (064a–c) | Subject pack registry, structure-first generic taxonomy, golden framework | [PR #4](https://github.com/mohammedumar9919/studypilot-v2/pull/4) |
| I (064e/f), SP-065 | PPL pack, unit/topic predictions + empty states, concept tap rewrite | [PR #5](https://github.com/mohammedumar9919/studypilot-v2/pull/5) (`020be45`) |
| — | Public repo: MIT, portfolio README, fixture PDFs removed | `99b30aa` |
| 064d.1 | Chemistry extended 5/5 units, 8/10 topics | [PR #6](https://github.com/mohammedumar9919/studypilot-v2/pull/6) (`2b55255`) |
| — | Human assistant onboarding pack (`docs/onboarding/`) | [PR #7](https://github.com/mohammedumar9919/studypilot-v2/pull/7) (`5a6cdf7`) |

---

## 6. What is LEFT (ordered)

1. **SP-071 finish — SS syllabus UNIT header OCR.**
   - Repro PDF: `C:\Users\Owner\Downloads\ss syllabus.pdf` (OU CSE ES305EC, 2 pages).
   - Page-2 headers: `UNIT \ufffd1`, `UNIT \ufffd II`, `UNIT III`, `UNIT -1IV`, `UNIT - V`. Only III and V match, and `UNIT -1IV` becomes a subtopic under Laplace.
   - **WIP exists (uncommitted, unverified):**
     - local branch `wip/sp-071-stash` has `_normalize_engineering_unit_header_line()` (NFKC, FFFD/control strip, dash fold, glued `-1IV` → `- IV`), `_warn_sparse_engineering_syllabus_units()`, tests in `test_toc_extraction.py`, and a failures-checklist line.
     - The fixture is on `wip/sp-071-fixture^3`.
   - Recovery commands:
     ```powershell
     git checkout -b sp-071-syllabus-unit-ocr main
     git checkout wip/sp-071-stash -- apps/api/app/services/pdf_extract.py apps/api/tests/test_toc_extraction.py docs/failures-checklist.md
     git checkout 'wip/sp-071-fixture^3' -- apps/api/tests/fixtures/syllabus/ss_signals_systems_ocr_units.txt
     ```
     Do **not** take CURRENT_STATE from the WIP; it is stale.
   - Done when:
     - `python -m pytest tests/test_toc_extraction.py -q` passes, with CN + DS + SS fixtures green.
     - The Course Map promote path is checked too.
     - The user re-imports the SS syllabus and sees Units I–V.
     - Optional: OCR retry when units are sparse or the FFFD rate is high.
2. **SS onboarding (SP-072).**
   - SS structure UAT.
   - SS papers through `exam_parse_audit`.
   - Human-tagged `SS_GOLDEN_REFERENCE.json` from `GOLDEN_REFERENCE_TEMPLATE.json`.
   - Run `--validate --course SS`.
   - Only add an `SsPack` if GenericPack provably fails.
3. **Phase II queue:**
   - SP-070b CN pack.
   - SP-070c onboard CLI.
   - SP-070d shared taxonomy helpers.
   - SP-070e fixture-only CI subject matrix.
   - SP-070a PPL is **parked**; WIP is on `wip/sp-070a-stash`.
4. **Deferred:**
   - SP-064d.2: chemistry Polymers 31 vs 23, Composites 15 vs 13, Solid Fuels 15 vs 12, or a Human Gate on positional-vs-content golden policy.
   - SP-073: Eval Gate CI reliability.
   - SP-014 observability / RAGAS.
   - Exam golden set (human approval).
   - SP-041 LLM outline.
5. **Human Gates pending:**
   - Purge the old PPL LFS objects from public history?
   - Chemistry golden positional policy.

---

## 7. Operating loop (how this user works)

1. **One slice per worker chat.** You write a copy-paste worker prompt; the user opens a new agent chat with it.
2. The worker returns a **DONE report**. The user pastes it back to you; you review it (council stage 2) and give the next prompt.
3. **Merges use manual green.**
   - GitHub Eval Gate often never posts or hangs.
   - Evidence needed: rebase on `main`, scoped `python -m pytest` PASS, and `npm run build` PASS (if web was touched).
   - Then `gh pr merge N --merge --admin` and a PR comment recording the evidence.
   - Retrieval files additionally need the user-run `quick_gate.ps1 -Smoke` plus the full fast eval.
4. **Eval, Docker and long gates run only in the user's PowerShell.** You give exact commands.
5. **Update CURRENT_STATE** after every slice merge. Never edit `.cursor/plans/*.plan.md`.
6. **Keep it universal.** Any exam/syllabus rule needs fixtures from **2+ subjects**. Prefer structure-first and pack overrides proven by fixtures over subject-specific regex.

### Worker card template

```
You are Agent <ID> for StudyPilot v2 (repo C:\Projects\studypilot-v2).
Read first: docs/CURRENT_STATE.md, AGENTS.md, docs/failures-checklist.md.

## Slice
<SP-xxx — one sentence goal>

## Context
<root cause / evidence / prior numbers>

## Allowed paths
- <exact files>

## Forbidden paths
- apps/api/app/services/retrieve.py, gate.py, rerank.py (unless council-unlocked)
- eval/golden_set.jsonl, .cursor/plans/*.plan.md
- <frozen files, e.g. ou_chemistry.py>

## Pytest scope
cd apps/api; python -m pytest <files> -q

## Done when
- <measurable criteria; regression fixtures that must stay green>

## Report back (exact format)
SP-xxx DONE|PARTIAL — files touched, pytest counts, before/after numbers, risks, UAT steps for user.
Do not commit unless told; do not expand scope.
```

---

## 8. Environment and gotchas

- Postgres `localhost:5433` (Docker, user-started); API `:8002` (`scripts/start_api.ps1`); web `:5175`.
- `STUDYPILOT_AUTH_DISABLED=1` for pytest/eval.
- Use `python -m pytest` (`pytest` is not on PATH). When Postgres is down, DB tests skip; say so in reports.
- Windows console: `$env:PYTHONIOENCODING='utf-8'` before printing OCR text (U+FFFD crashes cp1252).
- `gh` in PowerShell: quote `'stash@{1}'`; prefer `--template` over `--jq` with spaces; `gh pr list --state all` plain.
- Pushing branches whose names contain `/`: use an explicit refspec (`git push origin HEAD:refs/heads/<branch>`).
- **PPL fixture PDFs are local-only** (gitignored). Checking out a pre-`99b30aa` branch deletes them. Restore:
  ```powershell
  Copy-Item .git\lfs\objects\94\0a\940ab3095bdfc1dcec5cf4354984fd33b0cbc2d2e078248176c314d0dc7e37f8 "eval\fixtures\ppl\PPL notes.pdf"
  Copy-Item .git\lfs\objects\d2\f3\d2f3afd6df25f7dc05a9516c3e51125567b4447641742779527602f6c5acf1b0 "eval\fixtures\ppl\PPL previous papers.pdf"
  ```
  pytest prints a loud WARNING header and summary when they are missing.
- `extract_outline_from_pdf` returns **3** values (not 4).
