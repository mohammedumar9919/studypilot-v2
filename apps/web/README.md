# StudyPilot v2 — Web UI (Phase 2)

Minimal study query UI with chunk inspector and rerank debug panel.

## Prerequisites

- API running with ingested PPL corpus (`scripts/ingest_ppl.ps1`)
- `apps/api/.env` with `OPENROUTER_API_KEY` and `DATABASE_URL`

## Dev setup

If the UI shows **502 Bad Gateway**, the API is not running on the port in `vite.config.ts` (default **8002**).

**Terminal 1 — API**

```powershell
cd C:\Projects\studypilot-v2
.\scripts\start_api.ps1
```

Or manually (default proxy is **8002** — orphan old uvicorn may block **8001**):

```powershell
cd C:\Projects\studypilot-v2\apps\api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

Verify: `(Invoke-RestMethod http://127.0.0.1:8002/health).exam_questions_ppl` → **377** after PYQ re-ingest.

**Terminal 2 — Web**

```powershell
cd C:\Projects\studypilot-v2\apps\web
npm install
npm run dev
```

Open http://127.0.0.1:5173/

## Build

```powershell
npm run build
```

## Notes

- Full `POST /api/v1/query` E2E latency is **~60s** (CPU rerank ~10–15s + OpenRouter LLM ~40–50s). Progress UI shows elapsed time.
- Upload: use `scripts/ingest_ppl.ps1` until upload API exists.
- Vite proxies `/api` to the API port — no CORS changes in `main.py` required.
