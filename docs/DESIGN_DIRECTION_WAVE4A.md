# Wave 4a — Design direction (SP-035)

**Locked:** 2026-05-31  
**Reference:** Mentor app *Nail the Round* (screen recording analyzed — inspiration only, **do not clone**).  
**StudyPilot blend:** Warm + teal + balanced density + **premium futuristic motion**.

---

## What to borrow from Nail the Round (patterns, not pixels)

| NTR pattern | StudyPilot adaptation |
|-------------|----------------------|
| Dark premium canvas + high-contrast type | **Warm dark-charcoal** base (`#0f1419` → `#1a222c`) with **cream/teal-tinted** surfaces — not pure black/cyan |
| Vertical **light streaks** / motion-blur hero bg | Subtle **teal ambient streaks** or soft gradient mesh behind header/hero; CSS `@keyframes` drift (slow, 20–40s loop) |
| Large hero headline + **gradient accent word** | App title or stage label (“Finding sources…”) with **teal→mint** gradient on key word |
| **Horizontal step cards** (01–05) with arrows | **Study journey** strip: Ask → Retrieve → Cite → Review → Exam (5 steps); slide/fade on scroll or stage change |
| **Feature/KPI cards** with colored icon + score | Trust/value cards + heatmap unit cards: icon tint (teal variants), **count-up or bar-grow** on enter |
| **Three-panel cards** with hover glow border | Course units / outline sections: card lift + **teal glow ring** on hover/focus |
| **Avatar rings + status pill** (“Panel ready”) | Query **stage pill** (idle / retrieving / writing) with pulsing teal dot — extends `ProgressIndicator` |
| **CTA cards** — rounded, centered, glow button + arrow | Primary “Ask” submit + example chips: pill buttons, teal border glow, arrow micro-motion on hover |
| **Leaderboard-style** contained table/card | Heatmap panel: contained dark card, clean rows, subtle row hover |
| Scroll **section reveals** | Sections (answer, sources, sidebar) **stagger fade + slide-up** (80–120ms offset between siblings) |

---

## StudyPilot constraints (non-negotiable)

- **Tone:** Warm, approachable, citation-first — still an educational trust product
- **Accent:** Teal / green family (not NTR cyan-blue, not AI purple)
- **Density:** Balanced — keep heatmap + outline + query on one view; motion enhances, does not add clutter
- **Anti-patterns:** No fake match %, no generic AI hype, trust badges remain
- **Behavior:** Streaming SSE, fallback, debug toggle, mobile @ 390px — unchanged

---

## Futuristic / premium motion spec

### Ambient (always-on, subtle)

- Background: slow-moving teal streaks or noise gradient (opacity ≤ 8%)
- Optional: very light **glass** on panels (`backdrop-filter: blur(12px)`, semi-transparent surface)

### Interaction (on user action)

| Moment | Motion |
|--------|--------|
| Page load | Header + main column fade/slide up (300–400ms, ease-out) |
| Submit query | Main answer area **slides left**; sources panel **slides in** from right on `retrieval_complete` |
| Token stream | Existing cursor; answer block soft **height ease** (no jank) |
| Heatmap load | Bars **grow** from 0 → value (400ms stagger 40ms) |
| Outline expand | Accordion height transition + chevron rotate |
| Hover cards | `translateY(-2px)` + teal box-shadow glow |
| Example chip click | Brief scale 0.98 → 1 |

### Implementation

- **Prefer CSS** for ambient + hovers + heatmap bars
- **Optional:** `framer-motion` only if needed for stage slides — keep bundle small; Agent E decides
- **`prefers-reduced-motion`:** disable streaks, slides → fades only

---

## Layout reference (adapt, don’t copy landing page)

NTR is a **marketing landing page**; StudyPilot is a **tool UI**. Apply the *vocabulary*:

```
┌─────────────────────────────────────────────────────────┐
│  Header (logo wordmark + gradient accent + trust pills) │
├──────────────────────────────┬──────────────────────────┤
│  Query + stage pill          │  Outline (card stack)    │
│  Answer panel (glass card)   │  Heatmap (contained card)│
│  Sources (slide-in on retrieve)                         │
└──────────────────────────────┴──────────────────────────┘
```

Optional: thin **horizontal step indicator** above query (5 study steps) — highlights active stage during stream.

---

## Token sketch (Agent E implements)

```css
/* Illustrative — Agent E finalizes values */
--sp-bg-deep: #0f1419;
--sp-surface: rgba(26, 34, 44, 0.85);
--sp-surface-warm: #f7f5f2;        /* alternate light panels if needed */
--sp-teal: #2dd4bf;
--sp-teal-glow: rgba(45, 212, 191, 0.35);
--sp-text: #e8edf2;
--sp-muted: #8b9aab;
--sp-radius-lg: 16px;
--sp-shadow-glow: 0 0 24px var(--sp-teal-glow);
--sp-ease-out: cubic-bezier(0.22, 1, 0.36, 1);
```

Typography: modern sans (system or **DM Sans** / **Plus Jakarta Sans** for headings only).

---

## Reference assets

- Video: `C:\Users\Owner\Videos\Screen Recordings\Screen Recording 2026-05-30 195332.mp4`
- Extracted frames: `.planning/ntr-frames/` (Lead analysis only — not shipped)

---

## Acceptance (design)

1. Feels **premium + futuristic** — motion visible within 2s of load/submit
2. Still reads **warm + teal** — not a NTR dark clone
3. NTR layout **inspired** (cards, steps, glow CTAs) — StudyPilot IA preserved
4. Reduced-motion respected
