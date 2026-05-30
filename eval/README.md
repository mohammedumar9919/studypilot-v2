# Eval harness



Golden-set retrieval evaluation for Phase 1c. **No LLM** — replay runs hybrid retrieve → rerank → gate only.



## Golden set



`golden_set.jsonl` — 50 PPL questions with expected source doc + page(s).



| Category | Count | Scoring |

|----------|-------|---------|

| notes | 32 | Hit if top-5 chunk page in `expected_pages` (±1 tolerance) |

| lexical | 5 | Same + keyword optional check |

| pyq_style | 3 | Exam phrasing; answer still in notes |

| out_of_corpus | 10 | Gate must return `not_in_materials` |



Fixtures: `fixtures/ppl/PPL notes.pdf`, `fixtures/ppl/PPL previous papers.pdf`



**Gate target:** `precision@5 ≥ 70%` (40 in-corpus) **and** OOC refusal **10/10**.



## Preferred: fast eval (user terminal)



Run from repo root in **PowerShell** (not Cursor agent shell — often broken):



```powershell

cd C:\Projects\studypilot-v2



# Smoke — first 10 golden questions (~1-2 min)

$env:GOLDEN_LIMIT = "10"

$env:MIN_RERANK_SCORE = "0.40"

.\scripts\run_phase1b_eval_fast.ps1

Remove-Item Env:GOLDEN_LIMIT -ErrorAction SilentlyContinue



# Full — all 50 questions (~5-10 min CPU rerank)

$env:MIN_RERANK_SCORE = "0.35"   # tune: 0.30, 0.35, 0.40
$env:EVAL_PRECISION_MIN = "1.0"  # Wave 3: 100% gate

.\scripts\run_phase1b_eval_fast.ps1

# Phase 3 gate (100% precision + 10/10 OOC)

.\scripts\phase_gate.ps1 -Phase 3

```



**Outputs:**



| File | Contents |

|------|----------|

| `eval/reports/latest.jsonl` | Per-question replay results |

| `eval/reports/phase1b_metrics.json` | precision, OOC, gate pass flag |

| `eval/reports/PHASE1B_SUMMARY_FOR_AGENT.txt` | Paste into orchestrator chat |

| `eval/reports/phase1b_run.log` | Timestamped steps |



Default threshold in script: `MIN_RERANK_SCORE=0.40`. Override via `$env:MIN_RERANK_SCORE`.



## Do NOT use: 4-sweep eval



`scripts/run_phase1b_eval.ps1` sweeps 0.30 / 0.35 / 0.40 / 0.45 — **~1+ hour** on CPU. It was interrupted mid-run and blocked progress. Use **`run_phase1b_eval_fast.ps1`** only.



## Manual replay (advanced)



```powershell

cd C:\Projects\studypilot-v2\apps\api

.\.venv\Scripts\Activate.ps1

$env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"

cd ..\..

python eval/replay_retrieval.py

python eval/score_precision.py eval/golden_set.jsonl eval/reports/latest.jsonl

```



Optional: `$env:GOLDEN_LIMIT = "10"` limits replay to first N golden rows (smoke).



## Prerequisites



```powershell

docker compose up -d

.\scripts\ingest_ppl.ps1   # if DB empty

```



## Adding questions



1. Open the source PDF and note the **PDF page index** (0-based; matches ingest).

2. Add one JSON object per line to `golden_set.jsonl` (**human approval only**).

3. Re-run fast eval.



See `pdf_audit.md` for ingest quality flags per fixture PDF.



## Status



See [docs/CURRENT_STATE.md](../docs/CURRENT_STATE.md) for latest metrics and miss IDs.


