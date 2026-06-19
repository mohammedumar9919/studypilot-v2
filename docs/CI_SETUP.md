# CI setup — eval gate @ 100% (Wave 3, SP-003)

## Workflows

| Workflow | Job | When |
|----------|-----|------|
| `.github/workflows/eval-gate.yml` | `api-and-web` | Every push/PR — pytest (no PDFs) + `npm run build` |
| Same | `retrieval-gate` | When `eval/fixtures/ppl/PPL notes.pdf` exists in repo (via Git LFS) |

## One-time clone (Git LFS fixtures)

PPL PDFs are stored in **Git LFS**. After cloning:

```powershell
git lfs install
git clone https://github.com/mohammedumar9919/studypilot-v2.git studypilot-v2
cd studypilot-v2
git lfs pull
```

Verify fixtures:

```powershell
Test-Path "eval\fixtures\ppl\PPL notes.pdf"          # True
Test-Path "eval\fixtures\ppl\PPL previous papers.pdf" # True (optional for full ingest)
```

Linux / macOS:

```bash
git lfs install
git clone https://github.com/mohammedumar9919/studypilot-v2.git studypilot-v2
cd studypilot-v2
git lfs pull
test -f "eval/fixtures/ppl/PPL notes.pdf" && echo OK
```

**CI:** The `retrieval-gate` job uses `actions/checkout` with `lfs: true` so PDFs are materialized on the runner before the fixture check and ingest.

## Eval gate (default — full 50 questions, ~6–12 min)

One command from repo root (uses **studypilot** main DB, 100% precision + OOC):

```powershell
cd C:\Projects\studypilot-v2
git lfs pull
.\scripts\quick_gate.ps1
```

Prerequisites once: `docker compose up -d` and `.\scripts\ingest_ppl.ps1`

Optional smoke only (~2–3 min, 10 questions):

```powershell
.\scripts\quick_gate.ps1 -Smoke
```

## Local full gate (authoritative)

```powershell
cd C:\Projects\studypilot-v2
git lfs pull
docker compose up -d
.\scripts\ingest_ppl.ps1

$env:MIN_RERANK_SCORE = "0.35"
$env:EVAL_PRECISION_MIN = "1.0"
.\scripts\run_phase1b_eval_fast.ps1
.\scripts\phase_gate.ps1 -Phase 3
```

**Note:** `phase_gate` replay always uses the **studypilot** database (ingested), not `studypilot_test`.

Linux / GitHub Actions runner:

```bash
export MIN_RERANK_SCORE=0.35
export EVAL_PRECISION_MIN=1.0
./scripts/ci_eval_gate.sh
```

## PDF fixtures in CI

PPL PDFs are tracked with **Git LFS** (`.gitattributes`: `eval/fixtures/ppl/*.pdf`).

| File | Required for retrieval gate |
|------|-----------------------------|
| `PPL notes.pdf` | **Yes** — gate skips if missing |
| `PPL previous papers.pdf` | No — ingested when present (PYQ / past_paper path) |

If `retrieval-gate` shows **"Skip retrieval gate (fixtures not in repo)"**, run `git lfs pull` locally or confirm LFS objects were pushed (`git lfs ls-files`).

## Thresholds

| Variable | Default | Wave 3 target |
|----------|---------|---------------|
| `MIN_RERANK_SCORE` | `0.35` | Production tuning |
| `EVAL_PRECISION_MIN` | `1.0` | 100% (40/40 in-corpus) |
| `EVAL_OOC_MIN` | `1.0` | 10/10 OOC refusals |
| `GOLDEN_LIMIT` | (unset) | Set `10` for PR smoke |

## API pytest auth bypass (SP-012b)

Protected API routes require Clerk JWT in production. For local pytest and CI, set:

```powershell
$env:STUDYPILOT_AUTH_DISABLED = "1"
$env:ENVIRONMENT = "development"
cd apps\api
python -m pytest -q
```

`tests/conftest.py` sets `STUDYPILOT_AUTH_DISABLED=1` by default. CI `eval-gate` workflow should include the same env var on the pytest step.

## Never in CI

- `scripts/run_phase1b_eval.ps1` (4-threshold sweep, 1+ hour)

## Pytest auth bypass

API pytest sets `STUDYPILOT_AUTH_DISABLED=1` by default (`tests/conftest.py`) so course/query routes run without Clerk Bearer tokens. CI and local pytest do **not** need Clerk credentials. To test auth-enabled behavior, monkeypatch `settings.studypilot_auth_disabled = False` in the test module.
