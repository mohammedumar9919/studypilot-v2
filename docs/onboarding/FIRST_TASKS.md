# First task cards (Lead assigns one at a time)

Copy the block into the assistant’s **new Cursor chat** (or give as a markdown checklist for UAT-only tasks).

---

## Task 1 — Chemistry Exam Analytics UAT (Day 1) — START HERE

```
Manual UAT — chemistry Exam Analytics (NO code edits).

Prereq: API + web running (lead helps start). Open:
http://127.0.0.1:5175/courses/chemistry

Checklist (write Pass/Fail + screenshot notes):
1. Course opens without error
2. Exam Analytics tab loads (not hung / infinite spinner)
3. Likely topics shows ranked items
4. Tap 2 topics that should have notes coverage — drawer opens; answer or honest refuse
5. Tap 1 topic that may lack notes — expect "Not found in your study materials" OK if notes absent
6. Likely units visible if course is mapped; unit tap only when concept linked
7. Past-paper sources panel lists PDFs if present

Deliverable: create docs/onboarding/uat/chemistry-day1.md (or Notion) with table Pass/Fail + notes.
Forbidden: any code or parser changes.
Ask lead before commit.
```

---

## Task 2 — SS syllabus import repro (Day 2)

```
Reproduce Signals and Systems syllabus parse bug (read-only unless lead says otherwise).

PDF: C:\Users\Owner\Downloads\ss syllabus.pdf
(or path lead gives you)

Steps:
1. On course SS (or create course), import syllabus PDF via Course structure / import syllabus
2. Count how many units appear vs expected 5 (Unit I–V)
3. Screenshot wrong merges / missing units
4. Write docs/onboarding/uat/ss-syllabus-repro.md:
   - Expected: 5 units (operations on signals, Fourier, Laplace, discrete, Z-Transform)
   - Actual unit count + titles
   - Link to SP-071 (UNIT header OCR: UNIT �1, UNIT -1IV, etc.)

Forbidden: editing pdf_extract.py unless lead gives SP-071 worker prompt separately.
```

---

## Task 3 — First code (after Task 1–2 Pass)

```
You are Assistant Worker for StudyPilot (Agent E).

## Task
Improve clarity of ONE Exam Analytics empty-state message (no layout redesign).

## Allowed paths
- apps/web/src/components/ExamAnalyticsPanel.tsx
- apps/web/src/App.css (only if required for that message)

## Forbidden
- apps/api/**
- retrieve.py, gate.py, rerank.py, eval/golden_set.jsonl
- .cursor/plans/**

## Acceptance
cd apps/web
npm run build

## Do not
- Expand to new features
- Commit unless lead says "commit"
```

---

## Task card template (ongoing)

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
- <pytest / npm / UAT>

## Do not
- Expand scope
- Commit unless lead says commit
```
