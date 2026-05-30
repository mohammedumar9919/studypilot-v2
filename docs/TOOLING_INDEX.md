# StudyPilot v2 — Agent tooling index

Curated subset of external repos for Cursor orchestration and UI. Full plan: Grand Master Plan (`.cursor/plans/`).

---

## Installed (Wave 0)

| Tool | Repo | Location | Install command |
|------|------|----------|-----------------|
| **GSD Redux** | [open-gsd/get-shit-done-redux](https://github.com/open-gsd/get-shit-done-redux) | `.cursor/skills/gsd-*` | `npx @opengsd/get-shit-done-redux@latest --local --cursor --profile=standard` |
| **UI UX Pro Max** | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `apps/web/.cursor/skills/ui-ux-pro-max/` | `uipro init --ai cursor` (from `apps/web`) |
| **Council skills** | StudyPilot-native | `.cursor/skills/council-*`, `run-eval-gate` | See `docs/COUNCIL_SKILLS_COPYPASTE.md` |
| **Council board** | StudyPilot-native | `config/council/studypilot-board.yaml` | — |

### GSD next step (user, this chat or new)

After restart Cursor, run skill: **gsd-map-codebase** (or mention `gsd-map-codebase` skill) to index the repo.

---

## Manual install (user action)

| Tool | Repo | Command |
|------|------|---------|
| **Superpowers** | [obra/superpowers](https://github.com/obra/superpowers) | In Cursor Agent chat: `/add-plugin superpowers` |

---

## Reference only (not installed)

| Tool | Repo | When |
|------|------|------|
| **Karpathy LLM Council** | [karpathy/llm-council](https://github.com/karpathy/llm-council) | Process — `docs/COUNCIL_ORCHESTRATION.md` |
| **Awesome Claude Code** | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | Periodic discovery |
| **Obsidian Skills** | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Optional human planning vault |
| **Claude Mem** | [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem) | Defer — use `CURRENT_STATE.md` + GSD STATE |
| **n8n-MCP** | [czlonkowski/n8n-mcp](https://github.com/czlonkowski/n8n-mcp) | Wave 4–5 campus ops |

---

## Do not use

- `glittercowboy/get-shit-done` — superseded by **open-gsd/get-shit-done-redux**

---

## StudyPilot rules of precedence

1. `docs/failures-checklist.md` + eval gates win over GSD/Superpowers defaults
2. GSD owns `.planning/` phase artifacts; `docs/CURRENT_STATE.md` is runtime truth
3. UI UX Pro Max: **educational trust** aesthetic for Agent E — not spa/wellness templates
4. Council Stage 2 before merging retrieval/API/schema changes

---

## Worker task cards

- Wave 1 Agent E: [AGENT_E_TASK_CARD_3C-C.md](AGENT_E_TASK_CARD_3C-C.md)
- Queue: [WORKER_TASK_CARDS_QUEUE.md](WORKER_TASK_CARDS_QUEUE.md)
