# StudyPilot — Assistant onboarding pack

Everything needed to bring a human assistant onto StudyPilot **before** the live teaching session.

| File | Who | Purpose |
|------|-----|---------|
| [FRIEND_ASSISTANT.md](FRIEND_ASSISTANT.md) | **Lead (Umar)** | Full mentorship roadmap, timeline, what to teach |
| [DAY1_SCRIPT.md](DAY1_SCRIPT.md) | **Lead** | Word-for-word Day 1 / Day 2 teaching script |
| [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md) | **Assistant** | Paste into Cursor User Rules / first agent chat |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | **Lead + assistant** | Collaborator invite, clone, branch, PR rules |
| [FIRST_TASKS.md](FIRST_TASKS.md) | **Lead assigns** | Ready task cards (UAT → SS repro → first UI) |
| [COLLABORATION.md](COLLABORATION.md) | Both | How humans + Cursor agents work together (no Grokbot-style group chat) |

**Cursor rule (repo):** [`.cursor/rules/assistant-worker.mdc`](../../.cursor/rules/assistant-worker.mdc) — `alwaysApply: false`; assistant @-mentions it or copies baseline into User Rules.

## Lead checklist (do before explanations)

- [ ] Add friend as GitHub collaborator ([GITHUB_SETUP.md](GITHUB_SETUP.md))
- [ ] Confirm they can clone `studypilot-v2` and open in Cursor
- [ ] Send them [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md) to upload as User Rules
- [ ] Agree ports: Postgres `5433`, API `8002`, web `5175`
- [ ] Prepare chemistry course for demo (or SS if syllabus fixed)
- [ ] Print / open [DAY1_SCRIPT.md](DAY1_SCRIPT.md)
- [ ] Assign Task 1 from [FIRST_TASKS.md](FIRST_TASKS.md) at end of Day 1

## Assistant checklist (before Day 1)

- [ ] GitHub account ready; accept collaborator invite
- [ ] Install: Git, Node 20+, Python 3.11+, Docker Desktop, Cursor
- [ ] Clone repo; open folder in Cursor
- [ ] Paste [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md) into **Cursor Settings → Rules → User Rules**
- [ ] Read [COLLABORATION.md](COLLABORATION.md) (how to ask the lead / agents)
- [ ] Do **not** push to `main`; do **not** merge PRs
