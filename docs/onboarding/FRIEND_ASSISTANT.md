# Friend assistant — mentorship roadmap (Lead)

**Status:** Ready for Day 1 teaching  
**Product:** StudyPilot v2 (`C:\Projects\studypilot-v2`)  
**Your role:** Lead — decide scope, merge PRs, run eval/Docker  
**Their role:** Assistant — UAT, docs, Agent E (web) slices under task cards  

## Recommendation

Start with a **product tour + small UAT task**, not architecture. Treat them as an **Agent E / UAT / docs worker**, not a co-architect.

| Role | Lead (you) | Assistant (friend) |
|------|------------|-------------------|
| Decide what ships | Yes | Propose only |
| Merge PRs / force-push | Yes | Never |
| Run Docker / full eval | Yes (until week 2–3) | Watch, then copy |
| Edit code | Review + assign | One owned path per task |
| Cursor | Lead chat + task cards | Separate worker chat, Agent mode |
| Forbidden early | — | `retrieve.py`, `gate.py`, `rerank.py`, `eval/golden_set.jsonl`, chemistry taxonomy deep edits |

## Phased onboarding

### Phase 0 — Familiarity (Day 1 morning, 60–90 min)

Goal: use the app and explain it in 3 sentences.

1. Product: notes + syllabus + past papers → grounded answers + exam analytics (not ChatGPT).
2. Live walkthrough (chemistry preferred): query → citations → Exam Analytics → Likely topics/units → answer-on-tap.
3. Honest gaps: syllabus OCR (SP-071), missing notes → “not in materials”, chemistry extended validate still advisory.

**Exit test:** Five bullets — what the app does, what to upload, what Exam Analytics shows, forbidden files, where `docs/CURRENT_STATE.md` lives.

### Phase 1 — Observer (Day 1 afternoon, 45 min)

Show lead vs worker vs PowerShell ([MULTI_AGENT_WORKFLOW.md](../MULTI_AGENT_WORKFLOW.md)).

### Phase 2 — First real task (Day 1 end / Day 2)

Use [FIRST_TASKS.md](FIRST_TASKS.md):

1. **Task 1** UAT chemistry (no code) — recommended first  
2. **Task 2** SS syllabus repro  
3. **Task 3** Tiny UI empty-state (after 1–2 pass)

### Phase 3 — Cadence (Week 1–2)

UAT runner → PR babysitter (`gh pr view`, no merge) → Agent E slices → docs updates under your approval.

## 4-week timeline

| Week | Focus | Deliverables | Still forbidden |
|------|--------|--------------|-----------------|
| 1 | Product + UAT + git + 1 docs/UI PR | UAT report; 1 PR | retrieve/gate/rerank; schema |
| 2 | Agent E | 2 small web PRs; PR status reports | pdf_extract deep; exam taxonomy |
| 3 | Scoped pytest / CLI under you | Commands you list; SS SP-071 UAT | golden_set edits |
| 4 | Junior assistant | Drafts task cards; owns UAT for one course | Merge without you |

**Promotion:** 2 clean PRs on a surface before expanding surface.

## Explain hard concepts

| Concept | One-liner |
|---------|-----------|
| Hybrid RAG | Two search methods + combine + gate refuses if unsure |
| Study vs Exam | Study = notes; analytics = past papers; answer-on-tap = notes |
| Subject pack | Per-course plugin (chemistry special); not every course needs heavy rules |
| Council | Review dangerous edits — not a student chatbot |
| CURRENT_STATE | Scoreboard — update after real gates |

## Related

- Teaching script: [DAY1_SCRIPT.md](DAY1_SCRIPT.md)  
- Agent baseline for them: [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md)  
- Collaboration / “group chat”: [COLLABORATION.md](COLLABORATION.md)  
