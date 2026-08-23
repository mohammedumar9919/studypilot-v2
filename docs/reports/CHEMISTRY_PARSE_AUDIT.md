# Chemistry parse forensic audit (SP-062a)

Measure-only report. Parser / ingest code was not changed. Do not treat this as a 13/151/300 fix.

## Summary

- Course: `chemistry`
- Page source: `pdf+chunks`
- Golden: **13 papers / 151 mains / 300 sub-parts**
- Stored `exam_questions` rows: **302**
- Parser replay drafts: **302** (mains=17, subs=302)
- papers_found: **13** — E-5002/O/BL, E-5616/N/BL, E-5014/O/BL, E-5807/N/BL, E-5002/O, E-5870/N, E-5014/O, E-5616/N, D-2002/O, D-2014/O/BL, D-2337/N, D-2331/N, 15164
- papers_missing: **0** — (none)
- Stored paper codes: 15164, D-2002/O, D-2014/O/BL, D-2331/N, D-2337/N, E-5002/O, E-5002/O/BL, E-5014/O, E-5014/O/BL, E-5616/N, E-5616/N/BL, E-5807/N/BL, E-5870/N

## Why ~105 rows (evidence)

- Stored exam_questions rows=302; parser replay on the same ingest pages produced drafts=302 (mains=17 subs=302). Golden target is 13 papers / 151 mains / 300 sub-parts.
- Page probe: 17 pages (native=0, ocr=17, unknown=0). Readable threshold is 100 chars — 0 page(s) unreadably short and excluded from the OU bundle merge.
- OU splitter produced 17 paper section(s) vs golden 13. Golden codes found=13 missing=0.
- Format-skip pages=4 (detect_format=skip): p1/skip, p2/skip, p4/skip, p14/skip.
- Paper-start pages with no PART header and not compulsory=5: p1, p2, p4, p6, p14.
- Splitter section drops: no_code_no=0, format_skip=5, no_part_header=5.
- Drafts by splitter section: E-5002/O/BL→24 rows; E-5002/O/BL→5 rows; E-5616/N/BL→23 rows; E-5616/N/BL→10 rows; E-5014/O/BL→20 rows; E-5807/N/BL→28 rows; E-5002/O→22 rows; E-5870/N→19 rows; E-5014/O→24 rows; E-5616/N→19 rows; D-2002/O→24 rows; D-2014/O/BL→21 rows; D-2014/O/BL→4 rows.
- Drop-reason event counts (page-level): format_skip=4, unreadably_short=0, no_code_no=0, no_part_header=5.

## Drop reasons

| Reason | Page-level events | Meaning |
|---|---:|---|
| format_skip | 4 | `detect_format` returned skip |
| unreadably_short | 0 | char_count < 100; excluded from OU merge |
| no_code_no | 0 | paper-start page/section with no parseable Code No |
| no_part_header | 5 | paper-start without PART-A/B and not compulsory |

## Per page

| Doc | Page | chars | native_chars | native vs OCR | detect_format | Code No | PART | drops | codes |
|---|---:|---:|---:|---|---|---|---|---|---|
| OU QUESTION PAPERS.pdf | 1 | 2754 | 0 | ocr | skip | yes | no | format_skip, no_part_header | E-5002/O/BL |
| OU QUESTION PAPERS.pdf | 2 | 399 | 0 | ocr | skip | yes | no | format_skip, no_part_header | E-5002/O/BL |
| OU QUESTION PAPERS.pdf | 3 | 2480 | 0 | ocr | compulsory_q1 | yes | no | — | E-5616/N/BL |
| OU QUESTION PAPERS.pdf | 4 | 566 | 0 | ocr | skip | yes | no | format_skip, no_part_header | E-5616/N/BL |
| OU QUESTION PAPERS.pdf | 5 | 1831 | 0 | ocr | part_ab | yes | yes | — | E-5014/O/BL |
| OU QUESTION PAPERS.pdf | 6 | 427 | 0 | ocr | part_ab | yes | no | no_part_header | E-5014/O/BL |
| OU QUESTION PAPERS.pdf | 7 | 3056 | 0 | ocr | compulsory_q1 | yes | no | — | E-5807/N/BL, 28000 |
| OU QUESTION PAPERS.pdf | 8 | 1574 | 0 | ocr | part_ab | yes | yes | — | E-5002/O |
| OU QUESTION PAPERS.pdf | 9 | 1949 | 0 | ocr | compulsory_q1 | yes | no | — | E-5870/N |
| OU QUESTION PAPERS.pdf | 10 | 2037 | 0 | ocr | part_ab | yes | yes | — | E-5014/O |
| OU QUESTION PAPERS.pdf | 11 | 2313 | 0 | ocr | compulsory_q1 | yes | no | — | E-5616/N, 41000 |
| OU QUESTION PAPERS.pdf | 12 | 2208 | 0 | ocr | part_ab | yes | yes | — | D-2002/O |
| OU QUESTION PAPERS.pdf | 13 | 2242 | 0 | ocr | part_ab | yes | yes | — | D-2014/O/BL |
| OU QUESTION PAPERS.pdf | 14 | 395 | 0 | ocr | skip | yes | no | format_skip, no_part_header | D-2014/O, D-2014/O/BL |
| OU QUESTION PAPERS.pdf | 15 | 2093 | 0 | ocr | compulsory_q1 | yes | no | — | D-2337/N |
| OU QUESTION PAPERS.pdf | 16 | 1880 | 0 | ocr | compulsory_q1 | yes | no | — | D-2331/N |
| OU QUESTION PAPERS.pdf | 17 | 1915 | 0 | ocr | compulsory_q1 | yes | no | — | 15164 |

## Splitter sections

| # | code | format | chars | PART | drops | draft rows | mains | subs |
|---|---|---|---:|---|---|---:|---:|---:|
| 1 | E-5002/O/BL | skip | 2754 | no | format_skip, no_part_header | 24 | 16 | 24 |
| 2 | E-5002/O/BL | skip | 399 | no | format_skip, no_part_header | 5 | 2 | 5 |
| 3 | E-5616/N/BL | compulsory_q1 | 2480 | no | — | 23 | 5 | 23 |
| 4 | E-5616/N/BL | skip | 566 | no | format_skip, no_part_header | 10 | 3 | 10 |
| 5 | E-5014/O/BL | part_ab | 1840 | yes | — | 20 | 15 | 20 |
| 6 | E-5014/O/BL | skip | 418 | no | format_skip, no_part_header | 0 | 0 | 0 |
| 7 | E-5807/N/BL | compulsory_q1 | 3056 | no | — | 28 | 7 | 28 |
| 8 | E-5002/O | part_ab | 1574 | yes | — | 22 | 16 | 22 |
| 9 | E-5870/N | compulsory_q1 | 1949 | no | — | 19 | 7 | 19 |
| 10 | E-5014/O | part_ab | 2037 | yes | — | 24 | 17 | 24 |
| 11 | E-5616/N | compulsory_q1 | 2321 | no | — | 19 | 7 | 19 |
| 12 | D-2002/O | part_ab | 2200 | yes | — | 24 | 17 | 24 |
| 13 | D-2014/O/BL | part_ab | 2242 | yes | — | 21 | 15 | 21 |
| 14 | D-2014/O/BL | skip | 395 | no | format_skip, no_part_header | 4 | 2 | 4 |
| 15 | D-2337/N | compulsory_q1 | 2093 | no | — | 20 | 7 | 20 |
| 16 | D-2331/N | compulsory_q1 | 1880 | no | — | 19 | 7 | 19 |
| 17 | 15164 | compulsory_q1 | 1915 | no | — | 20 | 7 | 20 |

## Golden paper codes (13)

| Code | Session | Fmt | Match | Extracted as | Golden main/sub | Draft main/sub/rows | Notes |
|---|---|---|---|---|---|---|---|
| `E-5002/O/BL` | Sep/Oct 2023 | Old | **exact** | E-5002/O/BL | 17/24 | 17/26/26 | present on stored exam_questions.paper_label |
| `E-5616/N/BL` | Sep/Oct 2023 | New | **exact** | E-5616/N/BL | 7/31 | 7/31/31 | present on stored exam_questions.paper_label |
| `E-5014/O/BL` | Sep/Oct 2023 | Old | **exact** | E-5014/O/BL | 17/24 | 17/25/25 | present on stored exam_questions.paper_label |
| `E-5807/N/BL` | Sep/Oct 2023 | New | **exact** | E-5807/N/BL | 7/31 | 7/28/28 | present on stored exam_questions.paper_label; under-count vs golden main 7/7 sub 28/31 |
| `E-5002/O` | Feb/Mar 2023 | Old | **exact** | E-5002/O | 17/23 | 16/22/22 | present on stored exam_questions.paper_label; under-count vs golden main 16/17 sub 22/23 |
| `E-5870/N` | Feb/Mar 2023 | New | **exact** | E-5870/N | 7/19 | 7/19/19 | present on stored exam_questions.paper_label |
| `E-5014/O` | Feb/Mar 2023 | Old | **exact** | E-5014/O | 17/24 | 17/24/24 | present on stored exam_questions.paper_label |
| `E-5616/N` | Feb/Mar 2023 | New | **exact** | E-5616/N | 7/19 | 7/19/19 | present on stored exam_questions.paper_label |
| `D-2002/O` | Mar/Apr 2022 | Old | **exact** | D-2002/O | 17/24 | 17/24/24 | present on stored exam_questions.paper_label |
| `D-2014/O/BL` | Sep/Oct 2022 | Old | **exact** | D-2014/O/BL | 17/24 | 17/25/25 | present on stored exam_questions.paper_label |
| `D-2337/N` | Sep/Oct 2022 | New | **exact** | D-2337/N | 7/19 | 7/39/39 | present on stored exam_questions.paper_label |
| `D-2331/N` | Mar/Apr 2022 | New | **exact** | D-2331/N | 7/19 | 7/39/39 | present on stored exam_questions.paper_label |
| `15164` | July 2021 | New | **exact** | 15164 | 7/19 | 7/20/20 | present on stored exam_questions.paper_label |

## papers_found / papers_missing

- papers_found (13): `E-5002/O/BL`, `E-5616/N/BL`, `E-5014/O/BL`, `E-5807/N/BL`, `E-5002/O`, `E-5870/N`, `E-5014/O`, `E-5616/N`, `D-2002/O`, `D-2014/O/BL`, `D-2337/N`, `D-2331/N`, `15164`
- papers_missing (0): (none)

## Method

- Replayed `parse_exam_questions_from_pages` / `split_ou_bundle_text` / `detect_format` without modifying them.
- Page text comes from ingested chunks when present; native PDF text is probed without re-OCR.
- A page is `ocr` when stored/chunk text is longer than native text at or below the readable threshold.
- Code match: exact after normalize (`O`/`0`, whitespace); fuzzy via ratio ≥ 0.86. `E-5002/O` and `E-5002/O/BL` stay distinct.

---

## SP-062d stored vs replay (2026-08-23)

Post re-ingest of `OU QUESTION PAPERS.pdf` (`past_paper`, doc `fb2fcfea-e326-48b8-be84-e3ac81d50184`). Parser frozen (062c). No parser changes in this slice.

| Metric | Stored DB | Parser replay | Golden / band |
|---|---:|---:|---|
| question rows | **302** | **302** | 290–310 subs |
| paper codes | **13** | **13** | 13 exact |
| mains (unique base) | **150** | 17* | 145–155 |
| sub-parts | **302** | **302** | 290–310 |

\*Replay `draft_mains=17` is an audit counter artifact (unique bases across bundle); per-code mains match stored.

| Code | Stored rows | Replay rows | Stored main/sub | Golden main/sub | Match |
|---|---:|---:|---|---|---|
| E-5002/O/BL | 26 | 26 | 17/26 | 17/24 | stored=replay |
| E-5616/N/BL | 31 | 31 | 7/31 | 7/31 | stored=replay |
| E-5014/O/BL | 25 | 25 | 17/25 | 17/24 | stored=replay |
| E-5807/N/BL | 28 | 28 | 7/28 | 7/31 | stored=replay |
| E-5002/O | 22 | 22 | 16/22 | 17/23 | stored=replay |
| E-5870/N | 19 | 19 | 7/19 | 7/19 | stored=replay |
| E-5014/O | 24 | 24 | 17/24 | 17/24 | stored=replay |
| E-5616/N | 19 | 19 | 7/19 | 7/19 | stored=replay |
| D-2002/O | 24 | 24 | 17/24 | 17/24 | stored=replay |
| D-2014/O/BL | 25 | 25 | 17/25 | 17/24 | stored=replay |
| D-2337/N | 20 | 20 | 7/20 | 7/19 | stored=replay |
| D-2331/N | 19 | 19 | 7/19 | 7/19 | stored=replay |
| 15164 | 20 | 20 | 7/20 | 7/19 | stored=replay |

`exam_reference_report --validate --course chemistry`: **core PASS** (13 papers, 150 mains, 302 subs); **extended FAIL** (unit/topic rubric vs manual golden — advisory only). CLI exit **0** on core gate. Fixed `DEFAULT_GOLDEN_PATH` (was `apps/docs/...`).

