# Exam golden reference — adding a new subject

StudyPilot validates parsed `exam_questions` against per-course JSON golden files (SP-064c).

## Files

| File | Purpose |
|------|---------|
| [golden_reference.schema.json](./golden_reference.schema.json) | JSON Schema (required shape) |
| [GOLDEN_REFERENCE_TEMPLATE.json](./GOLDEN_REFERENCE_TEMPLATE.json) | Copy-paste starter |
| `{COURSE_ID}_GOLDEN_REFERENCE.json` | Live golden (e.g. `PPL_GOLDEN_REFERENCE.json`) |
| `{COURSE_ID}_GOLDEN_REFERENCE.md` | Derivation notes + Human Gate estimates |

## Resolution order

1. Subject pack `golden_path()` (e.g. `ChemistryPack` → `CHEMISTRY_GOLDEN_REFERENCE.json`)
2. Convention: `docs/reports/{COURSE_UPPER}_GOLDEN_REFERENCE.json`
3. CLI `--golden /path/to/file.json` override

## Validate

```powershell
cd apps\api
python -m app.cli.exam_reference_report --validate --course chemistry
python -m app.cli.exam_reference_report --validate --course PPL
python -m app.cli.exam_reference_report --course PPL --json   # metrics only
```

## Core vs extended gate

| Gate | Checks |
|------|--------|
| **Core** | `papers`, `main_questions`, `subparts` (within tolerances) |
| **Extended** | Per-unit subpart deltas, top-10 topic relative % |

## Meta fields

- **`paper_count_source`**: `codes` (OU paper codes, default) or `labels` (distinct `paper_label` values — use for PPL).
- **`confidence`**: `seed_confirmed` | `parse_confirmed` | `estimated` | `mixed`
- Put unverified full-corpus numbers in **`estimates`** — not in `meta` core counts.

## Checklist

1. Copy `GOLDEN_REFERENCE_TEMPLATE.json` → `{COURSE}_GOLDEN_REFERENCE.json`
2. Fill counts from defensible source (seed YAML, parse replay, UAT export)
3. Document assumptions in `{COURSE}_GOLDEN_REFERENCE.md`
4. Run `pytest tests/test_golden_reference_schema.py`
5. Optional: register pack `golden_path()` in `subjects/`

**Do not** edit `eval/golden_set.jsonl` (retrieval eval — separate Human Gate).

## Adding a new subject pack (SP-064)

1. Create `apps/api/app/services/exam/subjects/<subject>.py` implementing `SubjectPack`:
   - `pack_id`, `should_use_custom_parse`, `parse_pages` (or delegate to generic), `classify_question`, optional `golden_path` / fixture paths
2. Register in `subjects/registry.py` (`get_pack` + `resolve_parse_pack` order — chemistry heuristics stay before generic)
3. Optional: `eval/fixtures/<course>/` seed + outline YAML; golden JSON under `docs/reports/`
4. Wire fixture paths via pack helpers (do not hardcode course paths in `topic_frequency` / `course_outline`)
5. Add registry pytest coverage; run `exam_reference_report --validate --course <id>` if golden exists

Reference packs: `ChemistryPack` (custom OU parse), `PplPack` (generic parse + seed classify), `GenericPack` (structure-first).
