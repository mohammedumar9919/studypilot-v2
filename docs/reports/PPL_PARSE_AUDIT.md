# PPL parse forensic audit

Measure-only report. Parser / ingest code was not changed in this run. Compare stored `exam_questions` and replay drafts to golden reference.

## Summary

- Course: `PPL`
- Page source: `pdf+chunks`
- Golden: **1 papers / 17 mains / 25 sub-parts**
- Stored `exam_questions` rows: **377**
- Parser replay drafts: **377** (mains=18, subs=117)
- papers_found: **1** — July 2021 Main & Backlog
- papers_missing: **0** — (none)
- Stored paper codes: (none)

## Evidence

- Stored exam_questions rows=377; parser replay on the same ingest pages produced drafts=377 (mains=18 subs=117). Golden target is 1 papers / 17 mains / 25 sub-parts.
- Page probe: 30 pages (native=2, ocr=28, unknown=0). Readable threshold is 100 chars — 1 page(s) unreadably short and excluded from the OU bundle merge.
- OU splitter produced 1 paper section(s) vs golden 13. Golden codes found=1 missing=0.
- Unreadably short pages (evidence): p2(0c).
- Format-skip pages=3 (detect_format=skip): p2/skip, p28/skip, p30/skip.
- Paper-start pages with no parseable Code No=22: p5, p6, p7, p8, p9, p10, p11, p12.
- Paper-start pages with no PART header and not compulsory=4: p26, p27, p28, p30.
- Drafts by splitter section: E-5772/N→61 rows.
- Drop-reason event counts (page-level): format_skip=3, unreadably_short=1, no_code_no=22, no_part_header=4.

## Drop reasons

| Reason | Page-level events | Meaning |
|---|---:|---|
| format_skip | 3 | `detect_format` returned skip |
| unreadably_short | 1 | char_count < 100; excluded from OU merge |
| no_code_no | 22 | paper-start page/section with no parseable Code No |
| no_part_header | 4 | paper-start without PART-A/B and not compulsory |

## Per page

| Doc | Page | chars | native_chars | native vs OCR | detect_format | Code No | PART | drops | codes |
|---|---:|---:|---:|---|---|---|---|---|---|
| PPL previous papers.pdf | 1 | 1599 | 0 | ocr | compulsory_q1 | yes | no | — | E-5772/N, 20273 |
| PPL previous papers.pdf | 2 | 0 | 0 | native | skip | no | no | unreadably_short, format_skip | — |
| PPL previous papers.pdf | 3 | 2980 | 2980 | native | part_ab | yes | yes | — | 15048 |
| PPL previous papers.pdf | 4 | 1461 | 0 | ocr | part_ab | yes | yes | — | 11461 |
| PPL previous papers.pdf | 5 | 1836 | 0 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 6 | 1805 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 7 | 1110 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 8 | 1785 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 9 | 1833 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 10 | 1903 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 11 | 1371 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 12 | 1661 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 13 | 1781 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 14 | 1222 | 7 | ocr | continuation | no | no | no_code_no | — |
| PPL previous papers.pdf | 15 | 1631 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 16 | 1272 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 17 | 1468 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 18 | 1586 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 19 | 1340 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 20 | 1537 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 21 | 1225 | 7 | ocr | part_ab | no | yes | no_code_no | — |
| PPL previous papers.pdf | 22 | 1235 | 7 | ocr | part_ab | yes | yes | — | 11461 |
| PPL previous papers.pdf | 23 | 1309 | 7 | ocr | part_ab | yes | yes | — | 11461 |
| PPL previous papers.pdf | 24 | 1441 | 7 | ocr | part_ab | yes | yes | — | 11075 |
| PPL previous papers.pdf | 25 | 1383 | 7 | ocr | part_ab | yes | yes | — | 11634 |
| PPL previous papers.pdf | 26 | 1762 | 7 | ocr | part_ab | no | no | no_code_no, no_part_header | — |
| PPL previous papers.pdf | 27 | 604 | 7 | ocr | part_ab | no | no | no_code_no, no_part_header | — |
| PPL previous papers.pdf | 28 | 1730 | 50 | ocr | skip | no | no | format_skip, no_code_no, no_part_header | — |
| PPL previous papers.pdf | 29 | 1296 | 50 | ocr | continuation | no | no | no_code_no | — |
| PPL previous papers.pdf | 30 | 643 | 50 | ocr | skip | no | no | format_skip, no_code_no, no_part_header | — |

## Splitter sections

| # | code | format | chars | PART | drops | draft rows | mains | subs |
|---|---|---|---:|---|---|---:|---:|---:|
| 1 | E-5772/N | compulsory_q1 | 43865 | yes | — | 61 | 7 | 61 |

## Golden paper codes (13)

| Code | Session | Fmt | Match | Extracted as | Golden main/sub | Draft main/sub/rows | Notes |
|---|---|---|---|---|---|---|---|
| `July 2021 Main & Backlog` | July 2021 Main & Backlog | part_ab | **exact** | July 2021 Main & Backlog | 17/25 | 17/11/22 | under-count vs golden main 17/17 sub 11/25 |

## papers_found / papers_missing

- papers_found (1): `July 2021 Main & Backlog`
- papers_missing (0): (none)

## Method

- Replayed `parse_exam_questions_from_pages` / `split_ou_bundle_text` / `detect_format` without modifying them.
- Page text comes from ingested chunks when present; native PDF text is probed without re-OCR.
- A page is `ocr` when stored/chunk text is longer than native text at or below the readable threshold.
- Code match: exact after normalize (`O`/`0`, whitespace); fuzzy via ratio ≥ 0.86. `E-5002/O` and `E-5002/O/BL` stay distinct.

