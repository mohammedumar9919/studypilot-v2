"""PPL subject pack — fixture paths, seed-aware classify, generic parse wrapper (SP-064e)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from app.services.exam.subjects.generic import GenericPack

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import ExamQuestion
    from app.services.pdf_extract import DocumentOutline, PageText

logger = logging.getLogger(__name__)

_HERE = Path(__file__).resolve()


def _repo_root() -> Path:
    for parent in _HERE.parents:
        if (parent / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml").exists():
            return parent
    return _HERE.parents[5]


_REPO_ROOT = _repo_root()
PPL_OUTLINE_PATH = _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_outline.yaml"
PPL_PYQ_SEED_PATH = _REPO_ROOT / "eval" / "fixtures" / "ppl" / "ppl_pyq_seed.yaml"
PPL_GOLDEN_PATH = _REPO_ROOT / "docs" / "reports" / "PPL_GOLDEN_REFERENCE.json"

_PAST_PAPER_MARKERS = ("ppl previous", "previous papers", "programming languages")


class PplPack:
    """Second registered pack — PPL fixtures + seed taxonomy; parse wraps generic PYQ path."""

    pack_id = "ppl"

    def __init__(self) -> None:
        self._generic = GenericPack()

    @staticmethod
    def matches_course_id(course_id: str) -> bool:
        return course_id.strip().upper() == "PPL"

    def pyq_seed_path(self) -> Path | None:
        return PPL_PYQ_SEED_PATH if PPL_PYQ_SEED_PATH.is_file() else None

    def outline_fixture_path(self) -> Path | None:
        return PPL_OUTLINE_PATH if PPL_OUTLINE_PATH.is_file() else None

    def golden_path(self) -> Path | None:
        return PPL_GOLDEN_PATH if PPL_GOLDEN_PATH.is_file() else None

    def should_use_custom_parse(
        self,
        *,
        course_id: str,
        filename: str,
        sample_text: str = "",
    ) -> bool:
        del sample_text
        if self.matches_course_id(course_id):
            return True
        name = filename.lower()
        return any(marker in name for marker in _PAST_PAPER_MARKERS)

    def parse_pages(
        self,
        *,
        pages: list[PageText],
        document_id: Any,
        course_id: str,
        filename: str,
        outline: DocumentOutline | None,
    ) -> list[Any] | None:
        del document_id, course_id, filename
        from app.services.exam.pyq_parser import _group_pages, _parse_merged_text
        from app.services.exam.topic_frequency import _build_keyword_patterns
        from app.services.pdf_extract import load_outline

        resolved_outline = outline
        if resolved_outline is None:
            fixture = self.outline_fixture_path()
            if fixture is not None:
                resolved_outline = load_outline(fixture)

        patterns = _build_keyword_patterns(resolved_outline) if resolved_outline else None
        drafts: list[Any] = []

        for group in _group_pages(pages):
            merged_text = "\n\n".join(page.text for page in group)
            anchor_page = group[0].page
            page_drafts = _parse_merged_text(
                merged_text,
                anchor_page,
                outline=resolved_outline,
                patterns=patterns,
            )
            drafts.extend(page_drafts)

        if not drafts:
            return drafts

        enriched = self._apply_seed_hints(drafts)
        enriched = self._apply_paper_labels(enriched)
        logger.info(
            "Parsed %d PPL exam question(s) (%d seed-enriched)",
            len(enriched),
            sum(1 for draft in enriched if draft.unit or draft.section_title),
        )
        return enriched

    def classify_question(
        self,
        question: ExamQuestion,
        *,
        session: Session | None = None,
    ) -> tuple[str, str, str]:
        from_seed = self._classify_from_seed(question)
        if from_seed is not None:
            return from_seed

        unit, topic, subtopic = self._generic.classify_question(question, session=session)
        if unit != "Unmapped":
            return unit, topic, subtopic

        if question.unit or question.section_title:
            return self._generic._parser_fallback(question)

        return unit, topic, subtopic

    @staticmethod
    @lru_cache(maxsize=1)
    def _outline_units_by_id() -> dict[str, str]:
        path = PPL_OUTLINE_PATH
        if not path.is_file():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        mapping: dict[str, str] = {}
        for unit in raw.get("units") or []:
            unit_id = str(unit.get("id") or "").strip()
            title = str(unit.get("title") or "").strip()
            if unit_id and title:
                mapping[unit_id] = title
        return mapping

    @classmethod
    def _unit_label(cls, unit_id: str) -> str:
        title = cls._outline_units_by_id().get(unit_id.strip(), "")
        if not title:
            return f"Unit {unit_id.strip()}"
        roman = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5"}.get(unit_id.strip(), unit_id)
        return f"Unit {roman}"

    @staticmethod
    @lru_cache(maxsize=1)
    def _seed_rows() -> tuple[dict[str, str], ...]:
        path = PPL_PYQ_SEED_PATH
        if not path.is_file():
            return ()
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows: list[dict[str, str]] = []
        for entry in raw.get("questions") or []:
            rows.append(
                {
                    "prompt": str(entry.get("prompt") or ""),
                    "unit": str(entry.get("unit") or ""),
                    "section_title": str(entry.get("section_title") or ""),
                }
            )
        return tuple(rows)

    def _classify_from_seed(self, question: ExamQuestion) -> tuple[str, str, str] | None:
        prompt = question.prompt_text or ""
        if not prompt.strip():
            return None

        from app.services.exam.pyq_parser import prompts_match

        for row in self._seed_rows():
            if prompts_match(prompt, row["prompt"]):
                unit = self._unit_label(row["unit"])
                section = row["section_title"].strip()
                return unit, section, section
        return None

    def _apply_paper_labels(self, drafts: list[Any]) -> list[Any]:
        path = PPL_PYQ_SEED_PATH
        if not path.is_file():
            return drafts
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        labels = {
            int(row.get("page", 0)): str(row.get("label") or "").strip()
            for row in raw.get("exam_papers") or []
            if row.get("page") is not None
        }
        for draft in drafts:
            if draft.paper_label:
                continue
            label = labels.get(int(draft.page))
            if label:
                draft.paper_label = label
        return drafts

    def _apply_seed_hints(self, drafts: list[Any]) -> list[Any]:
        from app.services.exam.pyq_parser import prompts_match

        for draft in drafts:
            if draft.unit and draft.section_title:
                continue
            for row in self._seed_rows():
                if not prompts_match(draft.prompt_text, row["prompt"]):
                    continue
                if not draft.unit:
                    draft.unit = self._unit_label(row["unit"])
                if not draft.section_title:
                    draft.section_title = row["section_title"]
                break
        return drafts
