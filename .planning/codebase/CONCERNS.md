# Codebase Concerns

**Analysis Date:** 2026-05-30

## Tech Debt

**PPL-specific retrieval heuristics embedded in core RAG path:**
- Issue: `apps/api/app/services/rag/retrieve.py` (~918 lines) and `apps/api/app/services/rag/rerank.py` (~284 lines) contain hardcoded PPL unit phrases, section page hints, query-specific BM25 weight tweaks, and rerank bonuses/demotions tuned to the golden set (e.g. `ppl-002` evaluation-criteria cluster, short-circuit, ambiguous grammar). These are not configuration-driven and will not generalize to Chemistry or other courses without duplication.
- Files: `apps/api/app/services/rag/retrieve.py`, `apps/api/app/services/rag/rerank.py`, `eval/fixtures/ppl/ppl_outline.yaml`
- Impact: 100% precision@5 on PPL is fragile; adding a second course risks regressions or requires parallel heuristic blocks.
- Fix approach: Extract course-specific priors into per-course YAML/config loaded by `course_id`; add regression eval per course before removing inline constants.

**Context token budget is a char-based stub:**
- Issue: `apps/api/app/services/rag/context.py` uses `char_budget = budget * 4` with a comment that tiktoken replacement is deferred. `tiktoken` is already listed in `apps/api/pyproject.toml` but unused.
- Files: `apps/api/app/services/rag/context.py`, `apps/api/app/config.py` (`context_max_tokens`)
- Impact: LLM input may exceed intended token limits or truncate parent context unpredictably on long chunks.
- Fix approach: Replace char heuristic with tiktoken counting aligned to `settings.llm_budget_tier()` limits in `generate.py`.

**Stale developer UI artifacts at 100% retrieval:**
- Issue: `apps/web/src/constants/goldenMisses.ts` still lists five historical miss IDs (`ppl-002`, `ppl-013`, etc.) and drives `ChunkInspector` hints. Footer in `apps/web/src/App.tsx` advertises "golden misses loaded." Debug mode defaults to `true` (`useState(true)`).
- Files: `apps/web/src/constants/goldenMisses.ts`, `apps/web/src/App.tsx`, `apps/web/src/components/ChunkInspector.tsx`
- Impact: Student-facing UX (Wave 1) blocked; dev-only noise misleads new contributors about current accuracy state per `docs/CURRENT_STATE.md`.
- Fix approach: Gate inspector/misses behind dev flag; default `debugEnabled` to `false`; archive or empty `GOLDEN_MISSES` when golden set is clean.

**Course outline/seed paths hardcoded to PPL:**
- Issue: Outline and PYQ seed YAML paths are keyed only to `"PPL"` in `apps/api/app/services/exam/topic_frequency.py`, `apps/api/app/services/ingestion.py` (`OUTLINE_BY_FILENAME`), and `apps/api/app/services/rag/retrieve.py` (`_PPL_OUTLINE_PATH`).
- Files: `apps/api/app/services/exam/topic_frequency.py`, `apps/api/app/services/ingestion.py`, `apps/api/app/services/rag/retrieve.py`
- Impact: Second course (SP-018 Chemistry) requires code changes in multiple services, not data-only onboarding.
- Fix approach: Course registry table or `config/courses/{id}.yaml` mapping outline/seed paths; consumed by ingest and exam services.

**Phase gate threshold lags product target:**
- Issue: `scripts/phase_gate.ps1` Phase `1c` and `2` still pass at `precision_at_5 >= 0.70` and OOC `10/10`, not the documented 100% CI target (SP-003).
- Files: `scripts/phase_gate.ps1`, `docs/GAP_BACKLOG.md` (SP-003 OPEN)
- Impact: Gate can pass while product requirement (100% lock) is unmet; no automated PR blocker exists.
- Fix approach: Add Phase `3` gate at 1.0 precision + 10/10 OOC; wire GitHub Actions to `run_phase1b_eval_fast.ps1`.

**Incomplete docker-compose profile:**
- Issue: `docker-compose.yml` runs Postgres only. API, web, and ingest are manual local processes (SP-020 OPEN).
- Files: `docker-compose.yml`, `docs/GAP_BACKLOG.md`
- Impact: Onboarding friction; environment drift between developers and eval scripts.
- Fix approach: Add optional `api` and `web` services with documented env mounts (no secrets in compose).

**Windows-centric script and OCR paths:**
- Issue: Eval and ingest scripts use absolute `C:\Projects\studypilot-v2` paths and Tesseract default `C:\Program Files\Tesseract-OCR\` in `apps/api/app/services/pdf_extract.py`.
- Files: `scripts/run_phase1b_eval_fast.ps1`, `scripts/ingest_ppl_pyq.ps1`, `apps/api/app/services/pdf_extract.py`
- Impact: Linux/macOS contributors need manual path edits; OCR silently skipped when Tesseract missing (`logger.warning` only).
- Fix approach: Resolve repo root relative to script location; fail ingest loudly when OCR required pages remain low-text.

**TocBrowser is post-query only:**
- Issue: `apps/web/src/components/TocBrowser.tsx` renders chunks from `result?.retrieval_debug?.chunks` — requires a submitted query with debug enabled. No `GET /courses/{id}/outline` API exists (SP-010 PARTIAL).
- Files: `apps/web/src/components/TocBrowser.tsx`, `apps/web/src/App.tsx`, `docs/GAP_BACKLOG.md`
- Impact: Students cannot browse course structure before asking; MedX "unit landing cards" blocked.
- Fix approach: Add outline endpoint using `load_outline()` / `outline_summary()` from `apps/api/app/services/pdf_extract.py`; feed sidebar from API not retrieval debug.

## Known Bugs

**E2E query latency ~60 seconds:**
- Symptoms: Full `/api/v1/query` round-trip is LLM-bound (~60s); CPU rerank alone ~10–15s per `docs/CURRENT_STATE.md`. UI progress uses a 25s heuristic (`RETRIEVAL_ESTIMATE_MS`) then switches to "generating" — understates total wait.
- Files: `apps/api/app/services/rag/generate.py` (`httpx.Client(timeout=60.0)`), `apps/web/src/hooks/useStudyQuery.ts`, `apps/web/src/constants/goldenMisses.ts`
- Trigger: Any successful study query with OpenRouter generation enabled.
- Workaround: Use retrieval-only replay (`eval/replay_retrieval.py`) for tuning; set paid/faster model via `OPENROUTER_DEV_CHAT_MODEL` in `apps/api/.env`.

**4/30 PYQ pages still low-text after OCR:**
- Symptoms: Topic frequency reports partial coverage; ~26/30 pages readable per `docs/CURRENT_STATE.md` and `eval/fixtures/ppl/ppl_pyq_seed.yaml`. Remaining pages contribute only via keyword estimates, not verified question mapping.
- Files: `apps/api/app/services/exam/topic_frequency.py` (`_READABLE_CHAR_THRESHOLD = 100`, `_build_coverage_note()`), `eval/fixtures/ppl/ppl_pyq_seed.yaml`, `scripts/ingest_ppl_pyq.ps1`
- Trigger: `GET /api/v1/courses/PPL/exam/topic-frequency` or CLI `apps/api/app/cli/topic_frequency.py`
- Workaround: Re-run `scripts/ingest_ppl_pyq.ps1` with Tesseract installed; manually extend seed YAML for newly readable pages.

**Phase 3C-C exam heatmap UI not shipped:**
- Symptoms: No heatmap component under `apps/web/src/`; topic frequency API exists but has no consumer UI. Status IN PROGRESS per `docs/CURRENT_STATE.md`.
- Files: `apps/api/app/main.py` (`exam_topic_frequency` route), `apps/web/src/` (no `TopicFrequency*` or `Heatmap*` component)
- Trigger: Product Wave 1 deliverable incomplete.
- Workaround: Call API directly or use `apps/api/app/cli/topic_frequency.py` for JSON output.

**OpenRouter free-tier rate limits (429):**
- Symptoms: Dev model `meta-llama/llama-3.3-70b-instruct:free` hits ~20 req/min; API returns 502/429 with message in `OpenRouterGenerationError`.
- Files: `apps/api/app/services/rag/generate.py`, `apps/api/app/config.py` (`openrouter_dev_chat_model`), `apps/api/app/main.py`
- Trigger: Rapid query testing or eval runs that include generation.
- Workaround: Add credits, wait, or set `OPENROUTER_DEV_CHAT_MODEL=deepseek/deepseek-chat` in `apps/api/.env`.

## Security Considerations

**No authentication or workspace scoping on API routes:**
- Risk: Any client can query any `course_id`, read topic-frequency data, and trigger expensive LLM/rerank work. Documented as Phase 4 defer (`docs/failures-checklist.md`, SP-012).
- Files: `apps/api/app/main.py`, `docs/failures-checklist.md`
- Current mitigation: Localhost-only dev deployment; no public hosting documented.
- Recommendations: Add workspace ownership middleware before any pilot deploy; reject unknown `course_id` without auth.

**Debug flag exposes full retrieval internals:**
- Risk: `POST /api/v1/query` with `"debug": true` returns chunk IDs, filenames, pages, rerank scores, and 300-char excerpts in `retrieval_debug` (`apps/api/app/services/rag/pipeline.py` `_build_retrieval_debug`). Default UI enables debug.
- Files: `apps/api/app/main.py`, `apps/api/app/services/rag/pipeline.py`, `apps/web/src/App.tsx`
- Current mitigation: None in API; debug is client-controlled.
- Recommendations: Strip debug from production builds; server-side ignore `debug` when `environment=production`.

**No rate limiting on `/api/v1/query`:**
- Risk: Unauthenticated abuse can exhaust OpenRouter quota and CPU rerank capacity.
- Files: `apps/api/app/main.py`
- Current mitigation: None.
- Recommendations: Per-IP or per-session rate limits before campus pilot (SP-040+ defer until CI stable).

**Development database credentials in compose:**
- Risk: `docker-compose.yml` uses fixed `studypilot/studypilot` credentials exposed in repo.
- Files: `docker-compose.yml`, `apps/api/app/config.py` (matching default URLs)
- Current mitigation: Localhost binding on port 5433 only.
- Recommendations: Document that these are dev-only; use secrets manager for any shared environment.

## Performance Bottlenecks

**CPU cross-encoder rerank on every query:**
- Problem: `apps/api/app/services/rag/rerank.py` loads `BAAI/bge-reranker-base` (~400MB) once per process via `@lru_cache`, then scores up to 24 RRF candidates synchronously.
- Files: `apps/api/app/services/rag/rerank.py`, `apps/api/app/config.py` (`rrf_output_top_k=24`, `rerank_output_top_k=6`)
- Cause: No GPU path; blocking call in request thread.
- Improvement path: Phase 4 GPU rerank; reduce candidate pool after stable CI; cache rerank scores for identical queries.

**Synchronous full pipeline in request handler:**
- Problem: `run_study_query()` in `apps/api/app/services/rag/pipeline.py` runs retrieve → rerank → gate → embed context → OpenRouter HTTP POST sequentially before returning.
- Files: `apps/api/app/services/rag/pipeline.py`, `apps/api/app/main.py`
- Cause: No streaming or background job queue (SP-013 DEFER).
- Improvement path: SSE streaming for generation (Wave 3); return retrieval sources before LLM completes.

**Golden-set replay cost:**
- Problem: Full eval replays 50 questions with live DB + rerank; `scripts/run_phase1b_eval_fast.ps1` expects ~5–10 min CPU. Four-threshold sweep script takes 1+ hour (`eval/README.md` warns against `run_phase1b_eval.ps1`).
- Files: `eval/replay_retrieval.py`, `scripts/run_phase1b_eval_fast.ps1`, `scripts/run_phase1b_eval.ps1`
- Cause: No parallel workers; model cold start per pytest/eval invocation.
- Improvement path: Parallelize replay; cache embeddings; CI smoke with `GOLDEN_LIMIT=10` only on PR, full gate on main.

**OCR ingest duration:**
- Problem: `scripts/ingest_ppl_pyq.ps1` notes OCR may take 30–60 minutes for scanned PYQ PDF.
- Files: `scripts/ingest_ppl_pyq.ps1`, `apps/api/app/services/pdf_extract.py`
- Cause: Per-page Tesseract at 2x pixmap scale, single-threaded loop.
- Improvement path: Batch OCR worker; pre-process PDFs in CI fixture pipeline.

## Fragile Areas

**Retrieval accuracy tied to golden-set tuning:**
- Files: `apps/api/app/services/rag/retrieve.py`, `apps/api/app/services/rag/rerank.py`, `apps/api/app/services/rag/gate.py`, `eval/golden_set.jsonl`
- Why fragile: A single constant change (`min_rerank_score`, BM25 weight multiplier, phrase boost) can drop precision@5 from 100% to failure; anti-pattern doc forbids golden_set edits without human approval.
- Safe modification: Always run `scripts/run_phase1b_eval_fast.ps1` with `MIN_RERANK_SCORE=0.35` after changes; council review required for `retrieve.py`/`rerank.py`/`gate.py` per `config/council/studypilot-board.yaml`.
- Test coverage: `apps/api/tests/test_retrieval_golden.py`, `eval/replay_retrieval.py`; no CI enforcement yet.

**Page refinement for multi-page parents:**
- Files: `apps/api/app/services/rag/retrieve.py` (`_refine_page_from_parent`, `_SECTION_PAGE_HINTS`, `_PAGE_PHRASE_ANCHORS`)
- Why fragile: Eval scoring uses ±1 page tolerance (`apps/web/src/utils/pageMatch.ts`, `eval/score_precision.py`); incorrect ratio mapping on wide parents causes false misses.
- Safe modification: Extend unit tests in `test_retrieval_golden.py` for each new hint cluster before tuning weights.
- Test coverage: Partial — helper tests exist; not all golden IDs have dedicated regression tests.

**PYQ topic frequency hybrid seed + keyword model:**
- Files: `apps/api/app/services/exam/topic_frequency.py`, `eval/fixtures/ppl/ppl_pyq_seed.yaml`
- Why fragile: Counts are estimates (~50 questions); keyword matcher can double-count or mis-assign sections on OCR-noisy text; seed covers only page 3 in detail.
- Safe modification: Update seed YAML when new pages become readable; add tests in `apps/api/tests/test_topic_frequency.py` for each new page mapping.
- Test coverage: Good for seed load and keyword add-on; no test for live 26/30 OCR state.

**Ingest idempotency and doc_kind separation:**
- Files: `apps/api/app/services/ingestion.py`, `apps/api/app/services/rag/retrieve.py` (`STUDY_DOC_KINDS`)
- Why fragile: Re-ingest deletes all chunks for a document; accidental `past_paper` mis-tag would pollute study index. Anti-pattern: past_paper in study mode.
- Safe modification: Run `apps/api/tests/test_retrieval_golden.py::test_study_retrieval_excludes_past_paper_*` after ingest changes.
- Test coverage: Two exclusion tests present.

## Scaling Limits

**Single-course golden eval set:**
- Current capacity: 50 questions, one course (PPL), one notes PDF + one past-paper PDF in `eval/fixtures/ppl/`.
- Limit: Cannot measure cross-course accuracy or pilot readiness for Chemistry (deferred SP-018).
- Scaling path: Add Chemistry fixtures + golden rows after OCR path validated (`eval/pdf_audit.md`).

**Postgres + pgvector on single node:**
- Current capacity: HNSW index on 384-dim embeddings (`apps/api/alembic/versions/001_core.py`); full table scan fallback not used — vector search required.
- Limit: No read replicas, connection pooling config, or horizontal API scaling documented.
- Scaling path: Connection pool tuning; optional dedicated embed/rerank worker service.

**OpenRouter generation dependency:**
- Current capacity: External HTTP; dev free model with strict quotas.
- Limit: Production chat model (`deepseek/deepseek-chat`) adds cost and latency; no fallback if OpenRouter unavailable (`503` when key missing only).
- Scaling path: License proxy, response caching for FAQ-style queries, optional local LLM (Phase 4+).

## Dependencies at Risk

**OpenRouter free dev model:**
- Risk: `meta-llama/llama-3.3-70b-instruct:free` subject to rate and daily caps; documented 429 handling in `generate.py`.
- Impact: Dev/demo queries fail intermittently during intensive testing.
- Migration plan: Default to paid `deepseek/deepseek-chat` for stable dev; keep free model opt-in.

**Tesseract OCR optional install:**
- Risk: `pytesseract` and `Pillow` are optional (`apps/api/pyproject.toml` `[ocr]` extra); OCR failures log warning and leave pages empty.
- Impact: PYQ ingest incomplete without manual verification; 4/30 pages remain low-text.
- Migration plan: Make `[ocr]` required for ingest CI job; preflight check in `scripts/ingest_ppl_pyq.ps1` already exists — extend to fail on partial OCR.

**fastembed CPU models loaded in-process:**
- Risk: Both embedder (`apps/api/app/services/embedder.py`) and reranker share process memory; no model version pinning beyond config strings.
- Impact: Memory pressure under concurrent requests; model download on first request.
- Migration plan: Pin model versions in config; lazy-load with health check endpoint reporting model readiness.

## Missing Critical Features

**CI regression gate @ 100% precision (SP-003):**
- Problem: No `.github/workflows/` CI pipeline detected; eval gate is manual PowerShell only.
- Blocks: Safe merge of retrieval changes; campus pilot (SP-040+ defer until CI @ 100%).

**Student mode and trust UI (SP-030, SP-034 IN PROGRESS):**
- Problem: Debug panels, golden miss inspector, and dev footer visible by default; no student/prod mode toggle.
- Blocks: Student pilot UX; MedX-informed trust badges and citation polish incomplete.

**In-app PDF upload (SP-017 OPEN):**
- Problem: Ingest only via CLI (`apps/api/app/cli/ingest.py`) and PowerShell scripts (`scripts/ingest_ppl.ps1`); no upload API or UI.
- Blocks: 6-step user journey (Wave 4); non-developer onboarding.

**Exam preset / streaming / observability (Phase 4):**
- Problem: Only `preset: "study"` accepted (`apps/api/app/main.py`); no SSE; no RAGAS or structured logging beyond OpenRouter token info in `generate.py`.
- Blocks: Cram modes (SP-032), production monitoring (SP-014).

## Test Coverage Gaps

**No automated CI eval on pull requests:**
- What's not tested: 100% precision@5 and 10/10 OOC on every PR.
- Files: `scripts/phase_gate.ps1`, `docs/GAP_BACKLOG.md` (SP-003)
- Risk: Retrieval regressions merge undetected until manual eval.
- Priority: High

**No frontend tests:**
- What's not tested: Any `apps/web/src/` component; no Vitest/Jest config in web app.
- Files: `apps/web/src/**/*.tsx`
- Risk: Heatmap, student mode, and TOC UI break silently.
- Priority: Medium ( rises to High when Wave 1 UI ships)

**End-to-end query latency not asserted:**
- What's not tested: Full retrieve + generate path timing; only retrieval replay in eval harness.
- Files: `apps/api/tests/test_query_api.py` (mocks `run_study_query`), `eval/replay_retrieval.py`
- Risk: Latency regressions from model or prompt changes go unnoticed.
- Priority: Medium

**Production debug flag behavior:**
- What's not tested: Server ignoring `debug=true` in production environment.
- Files: `apps/api/app/main.py`, `apps/api/app/config.py` (`environment`)
- Risk: Accidental chunk text leak if deployed without hardening.
- Priority: Medium

**OCR quality integration:**
- What's not tested: Automated assertion that PYQ ingest achieves ≥29/30 readable pages after OCR.
- Files: `apps/api/tests/test_ingest_e2e.py`, `scripts/ingest_ppl_pyq.ps1`
- Risk: Exam intelligence remains partial without manual page audits.
- Priority: Medium

**Database-unavailable pytest skip:**
- What's not tested: Full test suite when Postgres is down — `apps/api/tests/conftest.py` skips DB tests; `phase_gate.ps1` Phase 0 may pass smoke-only.
- Files: `apps/api/tests/conftest.py`, `scripts/phase_gate.ps1`
- Risk: False green gates in environments without Docker.
- Priority: Low (documented dev expectation)

---

*Concerns audit: 2026-05-30*
