# GitHub setup — lead + assistant

## Lead (do before Day 1)

### 1. Add collaborator

1. Open https://github.com/mohammedumar9919/studypilot-v2/settings/access  
2. **Add people** → enter friend’s GitHub username  
3. Permission: **Write** (enough to push branches + open PRs; you keep merge control)  
4. Send invite; wait until they accept  

**You need their GitHub username** — ask them before Day 1.

### 2. Branch protection (recommended)

Settings → Branches → rules for `main`:

- Require pull request before merging (if available on your plan)
- Do not allow force-push to `main`

Even if CI is flaky (Eval Gate sometimes does not post), **you** still review every PR.

### 3. Share with them

- Repo URL  
- Link to [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md)  
- Link to [README.md](README.md) checklist  

### 4. Optional: secrets

Do **not** share `.env` / OpenRouter keys in chat. If they need local LLM later, lead configures on shared machine or issues a restricted key.

---

## Assistant (after invite)

1. Accept GitHub invitation (email or https://github.com/mohammedumar9919/studypilot-v2/invitations)  
2. Install [GitHub CLI](https://cli.github.com/) optional but useful: `gh auth login`  
3. Clone:

```powershell
git clone https://github.com/mohammedumar9919/studypilot-v2.git
cd studypilot-v2
```

4. Open folder in Cursor  
5. Paste User Rules from [ASSISTANT_AGENT_BASELINE.md](ASSISTANT_AGENT_BASELINE.md)  
6. Verify:

```powershell
git status
git branch -a
gh auth status
```

---

## PR rules (both)

| Rule | Detail |
|------|--------|
| Base branch | Always `main` |
| Branch name | `friend/<name>-<task>` |
| Size | One task per PR |
| Merge | **Lead only** |
| Commits | Clear message: `docs:`, `fix(web):`, `test:` — why, not noise |
| Secrets | Never commit `.env`, API keys, credentials |

---

## Lead cannot automate

Inviting a collaborator requires **their GitHub username** and usually interactive approval. This repo pack cannot accept the invite for them.
