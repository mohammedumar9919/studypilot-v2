"""Non-PPL courses must not inherit PPL hardcoded retrieval hints."""

from __future__ import annotations

from app.services.rag.retrieve import _UNIT_PHRASES, _hints_for_course


def test_non_ppl_course_gets_empty_hints_when_no_outline() -> None:
    phrases, terms, section_hints = _hints_for_course("TEST101")
    assert phrases == {}
    assert terms == {}
    assert section_hints == ()


def test_non_ppl_does_not_include_ppl_unit_phrases() -> None:
    phrases, _, _ = _hints_for_course("CHEM101")
    ppl_only = _UNIT_PHRASES.get("1", ())
    for phrase in ppl_only:
        assert phrase not in str(phrases).lower()


def test_ppl_still_gets_ppl_hints() -> None:
    phrases, terms, section_hints = _hints_for_course("PPL")
    assert phrases == _UNIT_PHRASES
    assert terms
    assert section_hints
