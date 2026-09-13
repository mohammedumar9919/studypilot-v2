# StudyPilot — Assistant Agent Baseline

**Give this file to your friend.** They should:

1. Copy everything under **“Paste into Cursor User Rules”** into **Cursor → Settings → Rules → User Rules**
2. Also `@`-mention `.cursor/rules/assistant-worker.mdc` or this file when starting a worker chat
3. Keep this updated if the lead changes forbidden paths

Repo: `studypilot-v2` (path on lead machine often `C:\Projects\studypilot-v2`)

---

## Paste into Cursor User Rules

```
You are a StudyPilot ASSISTANT WORKER under the human lead (not the lead orchestrator).

Repo: studypilot-v2
Every task — read first:
1. docs/CURRENT_STATE.md
2. AGENTS.md
3. docs/failures-checklist.md
4. docs/onboarding/ASSISTANT_AGENT_BASELINE.md (this baseline)

Role:
- Implement ONLY the slice in the task card the lead gives you
- Agent mode for code; Multitask Mode OFF
- One new chat per task; close when done

Hard rules:
- Allowed paths: ONLY what the task card lists
- Forbidden until lead explicitly unlocks: retrieve.py, gate.py, rerank.py, eval/golden_set.jsonl, .cursor/plans/*.plan.md
- Do not merge PRs, force-push, amend other people's commits, or push to main
- Do not run full eval / Docker / quick_gate unless the task card says so — lead runs those in PowerShell
- Local FastEmbed only; no vector-only retrieval; Study mode excludes past_paper
- One file, one owner — if you need a forbidden path, STOP and ask the lead

Every done report:
- Files touched
- How to verify (pytest / npm / UAT steps)
- Risks for the lead
- Do not expand scope

If unsure: ask the lead. Do not invent requirements.
```

---

## GitHub rules (assistant)

| Do | Don't |
|----|--------|
| Branch from latest `main`: `friend/<yourname>-<task>` | Commit directly to `main` |
| Open a PR for review | Merge your own PR (lead merges) |
| Keep PRs small (one task) | Force-push shared branches |
| Run only commands in the task card | Run full `quick_gate` / change golden_set |

### First-time clone

```powershell
git clone https://github.com/mohammedumar9919/studypilot-v2.git
cd studypilot-v2
```

(Use the real clone URL the lead gives you if different.)

### Every task

```powershell
git fetch origin
git checkout main
git pull origin main
git checkout -b friend/<yourname>-<short-task>
# ... work ...
git status
git add <files you own>
git commit -m "type(scope): short why"
git push -u origin HEAD
gh pr create --base main --title "..." --body "## Summary`n- ...`n`n## Test plan`n- [ ] ..."
```

---

## Environment (local)

| Service | Port / note |
|---------|-------------|
| Postgres | `localhost:5433` |
| API | `localhost:8002` (`scripts/start_api.ps1`) |
| Web | `localhost:5175` preferred |

Auth for local: `$env:STUDYPILOT_AUTH_DISABLED='1'`

---

## How to talk to the lead’s agents

Cursor does **not** support a shared multi-human agent group chat (unlike some Grokbot setups). Use [COLLABORATION.md](COLLABORATION.md):

1. Ask the **lead** in Discord/WhatsApp/etc.
2. Lead pastes your question into **their** lead Cursor chat if an agent answer is needed
3. Or open a PR — lead (and their agents) review the diff
4. For your own work: **your** Cursor agents + this baseline — not the lead’s live agent session

---

## First week surfaces (allowed themes)

| OK early | Not yet |
|----------|---------|
| UAT checklists, screenshots | Retrieval / gate / rerank |
| `apps/web/**` under Agent E task cards | `eval/golden_set.jsonl` |
| Docs under `docs/onboarding/`, UAT notes | Alembic / models without lead |
| Reading CURRENT_STATE, api-contracts | Chemistry taxonomy deep retune |

---

## Task card shape (lead fills; you paste)

```
You are Assistant Worker for StudyPilot.

## Task
<one sentence>

## Allowed paths
- <path>

## Forbidden
- retrieve.py, gate.py, rerank.py, eval/golden_set.jsonl
- <else>

## Acceptance
- <command or UAT checklist>

## Do not
- Expand scope / commit unless lead says commit
```
