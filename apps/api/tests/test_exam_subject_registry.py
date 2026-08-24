"""Tests for pluggable exam subject pack registry (SP-064a)."""

from __future__ import annotations

from app.services.exam.ou_chemistry import is_ou_chemistry_source
from app.services.exam.subjects.chemistry import ChemistryPack
from app.services.exam.subjects.generic import GenericPack
from app.services.exam.subjects.registry import get_pack


def test_chemistry_course_resolves_to_chemistry_pack() -> None:
    pack = get_pack("chemistry")
    assert isinstance(pack, ChemistryPack)
    assert pack.pack_id == "chemistry"


def test_chem_alias_resolves_to_chemistry_pack() -> None:
    pack = get_pack("CHEM")
    assert isinstance(pack, ChemistryPack)


def test_unknown_course_resolves_to_generic_pack() -> None:
    pack = get_pack("cn")
    assert isinstance(pack, GenericPack)
    assert pack.pack_id == "generic"


def test_cn_course_id_does_not_trigger_ou_chemistry_parser() -> None:
    assert not is_ou_chemistry_source(course_id="cn", filename="paper.pdf")
    assert not is_ou_chemistry_source(course_id="CN", filename="syllabus.pdf")


def test_chemistry_course_still_triggers_ou_parser() -> None:
    assert is_ou_chemistry_source(course_id="chemistry", filename="paper.pdf")
    assert is_ou_chemistry_source(course_id="chem", filename="paper.pdf")


def test_ou_filename_resolves_to_chemistry_parse_pack() -> None:
    from app.services.exam.subjects.registry import resolve_parse_pack

    pack = resolve_parse_pack(
        course_id="PPL",
        filename="OU QUESTION PAPERS (1).pdf",
    )
    assert isinstance(pack, ChemistryPack)


def test_cn_filename_does_not_resolve_to_chemistry_parse_pack() -> None:
    from app.services.exam.subjects.registry import resolve_parse_pack

    pack = resolve_parse_pack(course_id="cn", filename="cn_syllabus.pdf")
    assert isinstance(pack, GenericPack)


def test_chemistry_pack_exposes_golden_path() -> None:
    pack = get_pack("chemistry")
    path = pack.golden_path()
    assert path is not None
    assert path.name == "CHEMISTRY_GOLDEN_REFERENCE.json"


def test_generic_pack_has_no_golden_path() -> None:
    pack = get_pack("ds101")
    assert pack.golden_path() is None
