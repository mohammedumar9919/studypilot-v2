# Day 1–2 teaching script (Lead reads aloud)

## Before they arrive (15 min)

1. GitHub collaborator invite sent ([GITHUB_SETUP.md](GITHUB_SETUP.md)).
2. Repo opens on your machine; chemistry course demo-ready.
3. This script + [FIRST_TASKS.md](FIRST_TASKS.md) open.
4. Ports free: `5433` / `8002` / `5175` (see `docs/CURRENT_STATE.md`).

---

## Day 1

### 1. Opening (5 min)

> StudyPilot is a study app for our courses. It reads your PDFs and answers from them with page citations. It also analyzes past papers. You’re my assistant: you run UAT, small UI/docs tasks, and later code slices I assign. **I decide merges.** You never push to `main` or force-push.

### 2. Show the app (20 min)

You drive once; they repeat once.

```powershell
cd C:\Projects\studypilot-v2
docker compose up -d postgres
$env:STUDYPILOT_AUTH_DISABLED='1'
.\scripts\start_api.ps1
```

Other terminal:

```powershell
cd C:\Projects\studypilot-v2\apps\web
npm run dev -- --port 5175
```

Browser: `http://127.0.0.1:5175/courses/chemistry`

Show:

1. Study question → **sources / page citations**
2. Exam Analytics → Likely topics / Likely units
3. Tap a topic that answers; tap one that may say “not in materials” (honest)
4. Course structure / syllabus idea (SS failed UNIT OCR — SP-071)

### 3. Source-of-truth docs (15 min)

They open read-only:

| Doc | Say |
|-----|-----|
| `docs/CURRENT_STATE.md` | What’s done / next |
| `AGENTS.md` | Ownership + forbidden files |
| `docs/failures-checklist.md` | Never break these |
| `docs/MULTI_AGENT_WORKFLOW.md` | How we use Cursor |
| `docs/onboarding/ASSISTANT_AGENT_BASELINE.md` | Their agent rules |

> If the agent and these files disagree, CURRENT_STATE + failures-checklist win.

### 4. Cursor ritual (20 min)

Demonstrate:

1. New chat → **Agent mode** (not Plan for implementation)
2. Multitask **OFF**
3. Paste a task card (allowed / forbidden / done when)
4. Never edit `.cursor/plans/*.plan.md`
5. End with: files changed + how to verify

They install baseline: Cursor **Settings → Rules → User Rules** ← paste `ASSISTANT_AGENT_BASELINE.md` body.

### 5. Homework (30–45 min)

Assign **Task 1** from [FIRST_TASKS.md](FIRST_TASKS.md) (chemistry UAT). They fill Pass/Fail + screenshots.

### 6. Close (5 min)

> Tomorrow we do one tiny PR together. Tonight: write five bullets — product summary from Phase 0 exit test.

---

## Day 2

### 1. Review notes (10 min)

Correct study vs exam lane; past papers not used for study answers.

### 2. Git basics (20 min)

```powershell
cd C:\Projects\studypilot-v2
git fetch origin
git checkout main
git pull
git checkout -b friend/<their-name>-task
# after work:
git status
git add <only their files>
git commit -m "docs: onboarding UAT notes"
git push -u origin HEAD
gh pr create --base main --fill
```

They open PR; **you** merge or request changes.

### 3. First worker task (45–60 min)

**Task 2** (SS syllabus repro) or **Task 3** (UI copy) from [FIRST_TASKS.md](FIRST_TASKS.md). Sit with them for the first agent prompt.

### 4. Close

Week-1 cadence: 3× UAT **or** 2× small PRs; daily 15-min sync with you.
