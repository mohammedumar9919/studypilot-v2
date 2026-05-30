# Portable Agent Stack — copy to another project

**Source:** StudyPilot v2 orchestration stack (Waves 0–3, May 2026)  
**Use:** Paste this file into your new repo as `docs/PORTABLE_AGENT_STACK_SETUP.md` and follow the bootstrap checklist.

---

## 1. Architecture (5 layers)

| Layer | Purpose | StudyPilot example |
|-------|---------|-------------------|
| **Product waves** | What to ship in order | W1 UI → W2 API+UI → W3 CI → W4 pilot |
| **Orchestration** | Who owns what, task cards | Karpathy 3-stage council + Lead + workers B/C/D/E |
| **Agent quality** | TDD, review, verification | Superpowers plugin |
| **Planning / index** | Phases, codebase map | GSD Redux + `.planning/codebase/` |
| **Design (frontend)** | Trust UI, not generic AI chrome | UI UX Pro Max skill |

---

## 2. External repos (install order)

### P0 — Install first

| # | Tool | GitHub | Install |
|---|------|--------|---------|
| 1 | **GSD Redux** | https://github.com/open-gsd/get-shit-done-redux | `npx @opengsd/get-shit-done-redux@latest --local --cursor --profile=standard` |
| 2 | **Superpowers** | https://github.com/obra/superpowers | Cursor Agent chat: `/add-plugin superpowers` |
| 3 | **UI UX Pro Max** | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | From frontend app dir: `uipro init --ai cursor` (copies skill into `.cursor/skills/ui-ux-pro-max/`) |

### Process / reference (no install)

| Tool | GitHub | Use |
|------|--------|-----|
| **Karpathy LLM Council** | https://github.com/karpathy/llm-council | 3-stage governance pattern (docs only) |
| **Awesome Claude Code** | https://github.com/hesreallyhim/awesome-claude-code | Discovery |

### Defer until later

| Tool | GitHub | When |
|------|--------|------|
| Claude Mem | https://github.com/thedotmack/claude-mem | After you have `CURRENT_STATE.md` + GSD STATE |
| n8n-MCP | https://github.com/czlonkowski/n8n-mcp | Ops / webhooks (Wave 4+) |
| Obsidian Skills | https://github.com/kepano/obsidian-skills | Optional human planning vault |

### Do NOT use

- `glittercowboy/get-shit-done` — use **open-gsd/get-shit-done-redux** instead

---

## 3. Cursor plugin: Superpowers

**Install:** `/add-plugin superpowers` in a new Agent chat, then restart Cursor.

**Skills included (invoke before acting):**

| Skill | When |
|-------|------|
| `using-superpowers` | Start of any session |
| `brainstorming` | Before creative / feature work |
| `writing-plans` | Multi-step work before code |
| `executing-plans` | Run written plan in fresh session |
| `test-driven-development` | Features and bugfixes |
| `systematic-debugging` | Failures / unexpected behavior |
| `verification-before-completion` | Before claiming done |
| `requesting-code-review` / `receiving-code-review` | Merge readiness |
| `subagent-driven-development` | Parallel independent tasks |
| `dispatching-parallel-agents` | 2+ independent tasks |
| `using-git-worktrees` | Isolated feature work |
| `finishing-a-development-branch` | Merge / PR / cleanup |

**Subagent:** `code-reviewer` — after major steps complete.

---

## 4. GSD Redux (installed by npx)

### What it creates

```
.cursor/
  skills/gsd-*.md          # 19 skills (see list below)
  agents/gsd-*.md          # planner, executor, code-reviewer, etc.
  get-shit-done/           # workflows, bin/gsd-tools.cjs
  .gsd-profile
.planning/                 # created on first map / new-project
  codebase/                # STACK, ARCHITECTURE, etc. (7 files)
```

### GSD skills (after install)

- `gsd-new-project`, `gsd-plan-phase`, `gsd-execute-phase`, `gsd-discuss-phase`
- `gsd-code-review`, `gsd-verify-work`, `gsd-progress`, `gsd-help`
- `gsd-config`, `gsd-settings`, `gsd-update`, `gsd-import`, `gsd-quick`
- `gsd-phase`, `gsd-pause-work`, `gsd-resume-work`, `gsd-review`, `gsd-surface`, `gsd-workspace`

### GSD agents (partial install — extend as needed)

- `gsd-planner`, `gsd-plan-checker`, `gsd-phase-researcher`
- `gsd-executor`, `gsd-code-reviewer`, `gsd-code-fixer`

### First commands (new brownfield repo)

```text
# After install + Cursor restart:
Follow the gsd-map-codebase skill to index <your-repo-name>

# Then:
/gsd-new-project
```

**Map codebase output (7 files):**

- `STACK.md`, `INTEGRATIONS.md`, `ARCHITECTURE.md`, `STRUCTURE.md`
- `CONVENTIONS.md`, `TESTING.md`, `CONCERNS.md`

**Init CLI (if needed):**

```bash
node .cursor/get-shit-done/bin/gsd-tools.cjs init map-codebase
```

---

## 5. UI UX Pro Max

**Install:**

```bash
cd <your-frontend-app>   # e.g. apps/web
uipro init --ai cursor
# Optional: copy skill to repo root
cp -r .cursor/skills/ui-ux-pro-max ../../.cursor/skills/
```

**Invoke in Agent E / frontend chats:**

```text
Before implementing UI, invoke the ui-ux-pro-max skill.

Design target: <your product aesthetic> — NOT generic AI purple gradients.
Constraints: no fake metrics, accessible mobile, match existing CSS.
```

---

## 6. Council orchestration (StudyPilot-native — copy & adapt)

### Concept (Karpathy → engineering)

| Stage | Karpathy | Your project |
|-------|----------|--------------|
| 1 Propose | Parallel LLM answers | 2–3 worker Composer chats with scoped task cards |
| 2 Review | Peer ranking | Lead + checklist + eval impact |
| 3 Synthesize | Chairman answer | Lead merge + gate script + update CURRENT_STATE |

### Files to create

```
config/council/<project>-board.yaml
.cursor/skills/council-propose-slice/SKILL.md
.cursor/skills/council-review-slice/SKILL.md
.cursor/skills/council-merge-slice/SKILL.md
.cursor/skills/run-eval-gate/SKILL.md
.cursor/rules/council-governance.mdc
.cursor/rules/lead-orchestrator.mdc
docs/COUNCIL_ORCHESTRATION.md
docs/COUNCIL_SKILLS_COPYPASTE.md
docs/CURRENT_STATE.md
docs/GAP_BACKLOG.md
docs/WORKER_TASK_CARDS_QUEUE.md
AGENTS.md                    # ownership table: who owns which paths
docs/failures-checklist.md   # anti-patterns that override agent defaults
```

### Example board YAML (`config/council/<project>-board.yaml`)

```yaml
council:
  name: Your Project Engineering Board
  agents:
    - id: lead_chairman
      role: Lead orchestrator
      expertise: [phase_gates, merges, docs, task_cards]
    - id: agent_backend
      role: API / services
      expertise: [api, db, migrations]
    - id: agent_core
      role: Core logic / ML / retrieval
      expertise: [algorithms, eval]
    - id: agent_frontend
      role: Web / UX
      expertise: [react, accessibility]
  rules:
    council_required_for:
      - path/to/critical/module.py
      - eval/golden_set.jsonl
      - docs/api-contracts.md
```

### Council skill one-liners

**council-propose-slice:** Lead writes task card → user opens worker chat(s) → collect summary + files + risks.

**council-review-slice:** Mandatory for critical paths; vote Approve / Concern / Block; check failures-checklist + eval regression.

**council-merge-slice:** Lead picks winner → user runs tests/eval in terminal → update CURRENT_STATE → human merge approval.

**run-eval-gate:** Document exact PowerShell/bash commands; never long 4-sweep eval in agent shell.

---

## 7. Cursor rules (`.cursor/rules/`)

Create `.mdc` files with `alwaysApply` or globs as needed:

| File | Purpose |
|------|---------|
| `lead-orchestrator.mdc` | Lead does not implement worker-owned paths; delegates via task cards |
| `council-governance.mdc` | Stage 2 required before merging critical modules |
| `orchestrator.mdc` | Boot: read CURRENT_STATE first |

**Lead rule snippet:**

```markdown
---
description: Lead orchestrator — delegate, do not implement worker slices
alwaysApply: true
---
- Read docs/CURRENT_STATE.md before planning
- Do not edit apps/web/** when Agent Frontend is assigned
- Do not edit core retrieval/** when Agent Core is assigned
- Write task cards; user spawns worker chats
```

---

## 8. Docs template (runtime truth)

| File | Role |
|------|------|
| `docs/CURRENT_STATE.md` | Single source of truth: done / next / metrics |
| `docs/GAP_BACKLOG.md` | Product gaps with DONE/PARTIAL/OPEN |
| `docs/TOOLING_INDEX.md` | Installed repos + commands |
| `docs/WORKER_TASK_CARDS_QUEUE.md` | Copy-paste cards per wave |
| `docs/CI_SETUP.md` | GitHub Actions + local gate |
| `docs/api-contracts.md` | API version + routes |
| `AGENTS.md` | Path ownership matrix |

---

## 9. CI / eval gate (adapt to your project)

StudyPilot pattern:

```
.github/workflows/eval-gate.yml   # pytest + build every PR
eval/ci_gate.py                 # exit 1 if metrics below threshold
scripts/ci_eval_gate.sh         # Linux full pipeline
scripts/phase_gate.ps1          # -Phase 3 at 100%
scripts/run_*_eval_fast.ps1     # single threshold, NOT 4-sweep
```

**Env vars:**

```bash
MIN_RERANK_SCORE=0.35          # example tuning knob
EVAL_PRECISION_MIN=1.0         # 100% gate
EVAL_OOC_MIN=1.0               # if you have refusal tests
GOLDEN_LIMIT=10                # PR smoke only
```

---

## 10. Optional Cursor MCP plugins (user-level, not in repo)

These were enabled in the StudyPilot Cursor workspace — install per project need:

| MCP | Use |
|-----|-----|
| Notion | Tasks, docs, knowledge capture |
| Figma | Design ↔ code |
| Datadog | Production debug |

---

## 11. Bootstrap checklist (new project)

```markdown
## Wave 0 — Tooling
- [ ] `npx @opengsd/get-shit-done-redux@latest --local --cursor --profile=standard`
- [ ] `/add-plugin superpowers` → restart Cursor
- [ ] `uipro init --ai cursor` in frontend app
- [ ] Copy council skills from section 6
- [ ] Create config/council/<project>-board.yaml
- [ ] Create docs/CURRENT_STATE.md, GAP_BACKLOG.md, AGENTS.md, failures-checklist.md
- [ ] Add .cursor/rules/lead-orchestrator.mdc + council-governance.mdc

## Wave 0b — Index
- [ ] Run gsd-map-codebase (4 parallel mappers → .planning/codebase/)

## Wave 1+ — Product
- [ ] Write worker task cards (one agent, one path scope, acceptance commands)
- [ ] User runs long eval/ingest in terminal (not agent shell)
- [ ] Council Stage 2 before merging critical modules

## Wave 3 — Hardening
- [ ] GitHub Actions: pytest + build
- [ ] eval/ci_gate.py + phase_gate Phase 3
- [ ] Git LFS for large test fixtures (optional)
```

---

## 12. Worker task card template (copy-paste)

```markdown
You are **Agent <NAME>** for <PROJECT> — **<SCOPE> only**.

## Read first
1. docs/CURRENT_STATE.md
2. docs/GAP_BACKLOG.md
3. docs/api-contracts.md (if API)
4. AGENTS.md

## You own ONLY
- `path/to/your/**`

## FORBIDDEN
- `path/other-agent/**`

## Deliverables
1. ...
2. ...

## Acceptance
1. `npm run build` / `pytest ...`
2. ...

## Return to lead
- Files changed
- Screenshot / description
- API gaps (if any)

**Do NOT** edit `.cursor/plans/*.plan.md`
```

---

## 13. Rules of precedence (copy as project policy)

1. **Your failures-checklist + eval gates** beat GSD/Superpowers defaults
2. **GSD** owns `.planning/` phase artifacts; **`CURRENT_STATE.md`** is runtime truth for agents
3. **UI UX Pro Max:** pick a real product aesthetic (e.g. educational trust), not spa/wellness templates
4. **Council Stage 2** before merging critical core/API/schema paths
5. **Never** run 1+ hour eval sweeps in agent shell — user terminal only

---

## 14. StudyPilot file manifest (reference paths)

If cloning patterns from StudyPilot v2:

| Path | Notes |
|------|-------|
| `.cursor/skills/council-*` | 4 custom skills |
| `.cursor/skills/gsd-*` | 19 from GSD install |
| `.cursor/skills/ui-ux-pro-max/` | From uipro |
| `.cursor/get-shit-done/workflows/map-codebase.md` | Index workflow |
| `.planning/codebase/*.md` | Generated index |
| `config/council/studypilot-board.yaml` | Board template |
| `.github/workflows/eval-gate.yml` | CI |
| `eval/ci_gate.py` | Metric gate script |
| `docs/AGENT_E_TASK_CARD_*.md` | Example worker card |

---

## 15. One-line pitch for your new repo README

```text
Orchestration: Karpathy 3-stage council + GSD phases + Superpowers TDD +
UI UX Pro Max for frontend. Lead writes task cards; workers own paths;
CURRENT_STATE.md is truth; eval gate blocks regressions.
```

---

## 16. Skill slice phrases — paste into every prompt

**Policy:** Every Lead task card and worker prompt must include an **Invocation block** with exact skill names below. Agents read the skill file before acting.

### Universal (start of any important chat)

```text
Invoke the using-superpowers skill first — find and follow relevant skills before responding.
Read docs/CURRENT_STATE.md (runtime truth) before planning or coding.
```

### Lead orchestrator — planning a slice

```text
Follow council-propose-slice — write scoped task card; one owner per path from AGENTS.md.
Use brainstorming (Superpowers) before locking scope — explore intent and design first.
Use writing-plans (Superpowers) if the slice is multi-step.
Read .planning/codebase/ if present; run gsd-map-codebase if index is stale.
Do NOT implement worker-owned paths — delegate via task card only.
```

### Lead — after worker returns (merge)

```text
Follow council-review-slice — check failures-checklist, ownership, eval impact; vote Approve/Concern/Block.
Follow council-merge-slice — synthesize, update CURRENT_STATE.md, user runs gate in terminal.
Use verification-before-completion (Superpowers) before marking slice DONE.
Use receiving-code-review (Superpowers) if applying review feedback — verify, don't perform agreement.
```

### Worker — backend / API (Agent D pattern)

```text
Use test-driven-development (Superpowers) — tests before implementation.
Use systematic-debugging (Superpowers) only if tests fail unexpectedly.
Follow run-eval-gate skill discipline if retrieval touched — user runs eval in terminal, not agent shell.
Use verification-before-completion (Superpowers) — run pytest and paste output before claiming done.
Council Stage 2 was required before you started if paths include retrieve.py, gate.py, api-contracts.md.
```

### Worker — frontend (Agent E pattern)

```text
Invoke the ui-ux-pro-max skill before implementing UI.
Use brainstorming (Superpowers) if layout or trust patterns are unclear.
Use test-driven-development (Superpowers) where tests exist; otherwise npm run build as gate.
Use verification-before-completion (Superpowers) — build must pass with evidence.
Design: educational trust UI — no fake match %, no generic AI purple gradients.
```

### Worker — retrieval / ingest (Agent B/C pattern)

```text
Use systematic-debugging (Superpowers) for eval misses — reproduce with replay, then hypothesize.
Use test-driven-development (Superpowers) for helper changes; run test_retrieval_golden.py.
Follow run-eval-gate — user runs: MIN_RERANK_SCORE=0.35, run_phase1b_eval_fast.ps1, phase_gate -Phase 3.
NEVER run scripts/run_phase1b_eval.ps1 (4-sweep, 1+ hour).
Council mandatory — council-review-slice before merge.
```

### Debug / incident chat

```text
Use systematic-debugging (Superpowers) — root cause before fixes; evidence at each step.
Use verification-before-completion (Superpowers) before closing — rerun failing command and show output.
```

### GSD phase work (greenfield or large phase)

```text
Follow gsd-discuss-phase — gather context before PLAN.md.
Follow gsd-plan-phase — create PLAN.md with verification loop.
Follow gsd-execute-phase — execute plans with wave parallelization.
Follow gsd-code-review — review changed files after phase.
Follow gsd-verify-work — conversational UAT before phase sign-off.
```

### Pre-ship / PR

```text
Use requesting-code-review (Superpowers) — verify requirements before merge.
Use finishing-a-development-branch (Superpowers) — merge/PR/cleanup options.
Subagent: code-reviewer (Superpowers) after major implementation steps.
```

### Parallel independent tasks (Lead)

```text
Use dispatching-parallel-agents (Superpowers) or subagent-driven-development when 2+ workers have no shared state.
```

---

## 17. Example task card with slice phrases (Agent E — copy pattern)

```markdown
You are **Agent E** for <PROJECT> — **web UI only**.

## Skill invocation (mandatory — read each skill file first)
- Invoke **using-superpowers** — then **ui-ux-pro-max** before any UI code.
- Use **test-driven-development** for logic; **verification-before-completion** before handoff (run `npm run build`, paste result).
- Do NOT use **systematic-debugging** unless build/tests fail.

## Read first
1. docs/CURRENT_STATE.md
2. docs/GAP_BACKLOG.md
3. docs/api-contracts.md
4. AGENTS.md

## You own ONLY
- apps/web/**

## FORBIDDEN
- apps/api/**

## Deliverables
[...]

## Acceptance
1. npm run build — PASS with output pasted
2. ...

## Return to lead (for council-review-slice)
- Files changed, screenshot description, risks, API gaps

**Do NOT** edit .cursor/plans/*.plan.md
```

---

## 18. Example Lead opener (new slice)

```text
You are Lead for <PROJECT>.

Invoke using-superpowers. Read docs/CURRENT_STATE.md and .planning/codebase/ARCHITECTURE.md.

Follow council-propose-slice — I need a task card for [slice description].
Use brainstorming before you finalize the card.
Include the full Skill invocation block for the assigned worker (frontend/backend/retrieval template from section 16).
```

---

*Generated from StudyPilot v2 — adjust agent IDs, paths, and eval metrics for your stack.*
*Prompt policy: always include section 16 slice phrases in task cards and handoff prompts.*
