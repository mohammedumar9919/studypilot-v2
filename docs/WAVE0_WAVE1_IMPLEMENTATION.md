# Wave 0 + Wave 1 — implementation pack

Use this when executing in **Agent mode**. Plan mode completed the markdown docs below.

## Done (markdown)

- [CURRENT_STATE.md](CURRENT_STATE.md) — 100% RAG, 3C done, next Agent E
- [GAP_BACKLOG.md](GAP_BACKLOG.md) — reconciled statuses
- [ACCURACY_ROADMAP.md](ACCURACY_ROADMAP.md) — 100% milestones
- [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md) — Karpathy 3-stage mapping

## Pending (requires Agent mode)

### Config

Create `config/council/studypilot-board.yaml` — see [COUNCIL_ORCHESTRATION.md](COUNCIL_ORCHESTRATION.md).

### Cursor skills

Create under `.cursor/skills/`:

1. **council-propose-slice/SKILL.md** — Lead writes task card; spawn B/C/D/E workers with allowed/forbidden paths
2. **council-review-slice/SKILL.md** — Check failures-checklist, ownership, eval/OOC risk; Approve/Concern/Block
3. **council-merge-slice/SKILL.md** — Lead synthesis, gate command, CURRENT_STATE update
4. **run-eval-gate/SKILL.md** — User terminal: smoke → fast eval → phase_gate

### Cursor rules

- `.cursor/rules/council-governance.mdc` — mandatory Stage 2 for retrieval/schema
- Update `.cursor/rules/lead-orchestrator.mdc` — target 100%, next Agent E heatmap

### Agent E (Wave 1)

| File | Change |
|------|--------|
| `apps/web/src/types.ts` | Add `TopicFrequencyResponse` types |
| `apps/web/src/api/topicFrequencyClient.ts` | `GET /api/v1/courses/{id}/exam/topic-frequency` |
| `apps/web/src/components/TopicFrequencyPanel.tsx` | Bar heatmap + coverage warning |
| `apps/web/src/components/TrustFooter.tsx` | Citations, local embed, OOC bullets |
| `apps/web/src/components/SourcesList.tsx` | Citation cards with optional section |
| `apps/web/src/App.tsx` | `debugEnabled` default **false**; show heatmap always; dev tools when debug |
| `apps/web/src/constants/goldenMisses.ts` | Empty array (100% eval) |
| `apps/web/src/App.css` | Heatmap + trust styles |

### Acceptance

- Student view: heatmap visible, no rerank/debug without checkbox
- `Invoke-RestMethod http://localhost:8001/api/v1/courses/PPL/exam/topic-frequency` matches UI
