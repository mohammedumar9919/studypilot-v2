---
name: run-eval-gate
description: User-terminal eval discipline for StudyPilot. Never use the 4-sweep eval script.
---

# Run eval gate

## Commands (user PowerShell, repo root)

**Simple (recommended):**

```powershell
cd C:\Projects\studypilot-v2
.\scripts\quick_gate.ps1            # full 50 questions, ~6-12 min (default)
.\scripts\quick_gate.ps1 -Smoke      # optional 10-question smoke, ~2-3 min
```

**Manual (advanced):**

```powershell
cd C:\Projects\studypilot-v2
docker compose up -d
$env:MIN_RERANK_SCORE = "0.35"
$env:EVAL_PRECISION_MIN = "1.0"
.\scripts\run_phase1b_eval_fast.ps1
.\scripts\phase_gate.ps1 -Phase 3
```

## Never

- `scripts/run_phase1b_eval.ps1` (4-sweep, 1+ hour)
- Agent shell for 30+ min jobs — user runs these
