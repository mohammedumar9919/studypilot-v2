# OU Engineering Chemistry — Golden Reference (SP-061a)

**Source:** `chemistry-past-papers-analytics.canvas.tsx` (Weathero — OCR + manual tagging)  
**Machine-readable:** [`CHEMISTRY_GOLDEN_REFERENCE.json`](./CHEMISTRY_GOLDEN_REFERENCE.json)

## Target metrics

| Metric | Value |
|--------|------:|
| Past papers | **13** |
| Main questions | **151** |
| Sub-parts | **300** |
| Years | 2021 (7 mains), 2022 (48), 2023 (96) |
| Formats | 6 Old / 7 New |

## Unit distribution (sub-parts)

| Unit | Sub-parts | % subparts | % mains |
|------|----------:|-----------:|--------:|
| Unit I — Electrochemistry & Batteries | 103 | 34.3% | 25.2% |
| Unit II — Water & Corrosion | 48 | 16.0% | 17.9% |
| Unit III — Engineering Materials | 50 | 16.7% | 18.5% |
| Unit IV — Chemical Fuels | 56 | 18.7% | 21.2% |
| Unit V — Green Chemistry & Composites | 43 | 14.3% | 17.2% |

## Validation CLI

```powershell
cd C:\Projects\studypilot-v2\apps\api
$env:STUDYPILOT_AUTH_DISABLED='1'
python -m app.cli.exam_reference_report --validate --course chemistry
python -m pytest tests/test_exam_reference_report.py -q
```

## Tolerances (until parser v2 lands)

- Papers: exact **13**
- Mains: **145–155** (target 151)
- Sub-parts: **290–310** (target 300)
- Per-unit subpart count: ±**5** vs golden
- Top-10 topic counts: ±**15%** relative
