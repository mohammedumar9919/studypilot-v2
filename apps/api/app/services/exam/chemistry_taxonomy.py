"""Golden-aligned OU chemistry taxonomy for syllabus-primary analytics."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.exam.ou_chemistry import (
    _NEW_FORMAT_MAIN_UNITS,
    _OLD_PART_A_MAIN_UNITS,
    _OLD_PART_B_MAIN_UNITS,
    map_chemistry_by_position,
)

if TYPE_CHECKING:
    from app.models import ExamQuestion

# Ordered specific-before-generic; mirrors golden topic labels in CHEMISTRY_GOLDEN_REFERENCE.json.
_TOPIC_KEYWORDS: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "Unit I",
        "Battery Chemistry",
        (
            "primary battery",
            "secondary battery",
            "primary cell",
            "secondary cell",
            "lead-acid",
            "lead acid",
            "pb-acid",
            "pb acid",
            "lithium ion",
            "lithium-ion",
            "li-ion",
            "li ion",
            "zinc-carbon",
            "zinc carbon",
            "alkaline battery",
            "dry cell",
            "lead acid battery",
            "nickel cadmium",
            "ni-cd",
            "ni cd",
            "button cell",
            "leclanche",
            "storage battery",
            "battery",
        ),
    ),
    (
        "Unit I",
        "Electrochemistry",
        (
            "fuel cell",
            "hydrogen oxygen fuel",
            "oxygen fuel cell",
            "nernst",
            "calomel",
            "quinhydrone",
            "glass electrode",
            "reference electrode",
            "emf",
            "electrode potential",
            "electrochemical",
            "galvanic",
            "electrolytic",
            "cell notation",
            "electrode",
            "electrolyte",
            "conductivity",
            "conductance",
            "molar conductivity",
        ),
    ),
    (
        "Unit II",
        "Water Chemistry",
        (
            "edta",
            "hardness",
            "alkalinity",
            "chlorination",
            "chlorine",
            "ion exchange",
            "reverse osmosis",
            " ro ",
            "softening",
            "demineral",
            "potable water",
            "break point",
            "sterilize water",
        ),
    ),
    (
        "Unit II",
        "Corrosion",
        (
            "corrosion",
            "pitting",
            "galvanizing",
            "cathodic protection",
            "rust",
            "waterline",
            "hot dipping",
        ),
    ),
    (
        "Unit III",
        "Conducting Polymers",
        (
            "conducting polymer",
            "polyacetylene",
            "poly acetylene",
            "biodegradable polymer",
            " polylactic",
            " pla ",
        ),
    ),
    (
        "Unit III",
        "Specific Polymers",
        (
            "pvc",
            "nylon",
            "kevlar",
            "bakelite",
            "rubber",
            "thermoplastic",
            "thermoset",
            "buna",
            "addition polymer",
            "condensation polymer",
            "monomer",
            "plastics",
        ),
    ),
    (
        "Unit IV",
        "Solid Fuels (Coal)",
        (
            "coal",
            "proximate",
            "ultimate analysis",
            "solid fuel",
            "ranking of coal",
        ),
    ),
    (
        "Unit IV",
        "Liquid Fuels",
        (
            "petroleum",
            "octane",
            "cetane",
            "cracking",
            "liquid fuel",
            "moving bed",
            "knocking",
        ),
    ),
    (
        "Unit IV",
        "Fuels — General",
        (
            "calorific",
            "dulong",
            "hcv",
            "lcv",
            "combustion",
            "lpg",
            "cng",
            "gaseous fuel",
            "classification of fuel",
        ),
    ),
    (
        "Unit V",
        "Biodiesel",
        (
            "biodiesel",
            "transesterification",
            "bio diesel",
            "biofuel",
            "carbon neutral",
        ),
    ),
    (
        "Unit V",
        "Green Chemistry",
        (
            "green chemistry",
            "atom economy",
            "clean technology",
            "principles of green",
        ),
    ),
    (
        "Unit V",
        "Composites",
        (
            "composite",
            "matrix",
            "reinforcement",
            "fibre",
            "fiber",
            "composite material",
        ),
    ),
]

_COMPOSITE_STRONG_KEYWORDS: tuple[str, ...] = (
    "classification of composite",
    "composite classification",
    "matrix",
    "reinforcement",
    "frp",
    "fibre reinforced",
    "fiber reinforced",
    "composite material",
)
_COMPOSITE_WEAK_KEYWORDS: tuple[str, ...] = ("composite", "composites")

_SUBTOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Green Chemistry Principles", ("green chemistry", "atom economy", "principles of green", "clean technology")),
    ("Calorific Value (HCV/LCV/Dulong's)", ("calorific", "hcv", "lcv", "dulong")),
    ("Fuel Cells", ("fuel cell", "fuel cells", "oxygen fuel")),
    (
        "Reference Electrodes (Calomel/Quinhydrone/Glass)",
        ("calomel", "quinhydrone", "glass electrode", "reference electrode"),
    ),
    ("EDTA Hardness Method", ("edta", "hardness", "hardness of water")),
    (
        "Primary vs Secondary Batteries",
        (
            "primary battery",
            "secondary battery",
            "primary and secondary",
            "lead-acid",
            "lead acid",
            "pb-acid",
            "pb acid",
            "li-ion",
            "li ion",
            "lithium",
            "zinc-carbon",
            "alkaline battery",
            "dry cell",
        ),
    ),
    ("Conducting Polymers (Polyacetylene)", ("conducting polymer", "polyacetylene", "poly acetylene")),
    ("Transesterification / Biodiesel", ("transesterification", "biodiesel", "bio diesel")),
    (
        "Composite Classification",
        ("classification of composite", "composite classification", "matrix", "reinforcement", "frp"),
    ),
    ("Octane / Cetane Rating", ("octane", "cetane", "knocking")),
    ("Nernst Equation / EMF", ("nernst", "emf", "electrode potential")),
]

_TOPIC_TO_UNIT: dict[str, str] = {topic: unit for unit, topic, _ in _TOPIC_KEYWORDS}
_POLYMER_MISLABELS = frozenset({"Conducting Polymers", "Specific Polymers"})


def _base_main_number(question_number: str | None) -> str | None:
    if not question_number:
        return None
    match = re.match(r"^(\d+)", question_number.strip())
    return match.group(1) if match else None


def _normalize_prompt(prompt: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (prompt or "").lower())


def _keyword_hits(prompt: str, keywords: tuple[str, ...]) -> int:
    lowered = _normalize_prompt(prompt)
    tokens = set(lowered.split())
    return sum(
        1
        for keyword in keywords
        if keyword in lowered or keyword.replace("-", " ") in lowered or keyword in tokens
    )


def _composite_hits(prompt: str, *, allow_weak: bool) -> int:
    lowered = _normalize_prompt(prompt)
    strong = sum(1 for keyword in _COMPOSITE_STRONG_KEYWORDS if keyword in lowered)
    if strong:
        return strong
    if allow_weak:
        return sum(1 for keyword in _COMPOSITE_WEAK_KEYWORDS if keyword in lowered)
    return 0


def _topic_keyword_hits(
    prompt: str,
    topic: str,
    keywords: tuple[str, ...],
    *,
    allow_weak_composite: bool = False,
) -> int:
    if topic == "Composites":
        return _composite_hits(prompt, allow_weak=allow_weak_composite)
    return _keyword_hits(prompt, keywords)


def map_chemistry_topic_keywords(prompt: str) -> tuple[str | None, str | None]:
    best: tuple[str, str, int] | None = None
    for unit, topic, keywords in _TOPIC_KEYWORDS:
        hits = _topic_keyword_hits(prompt, topic, keywords, allow_weak_composite=False)
        if hits and (best is None or hits > best[2]):
            best = (unit, topic, hits)
    if best is None:
        return None, None
    return best[0], best[1]


def map_chemistry_topic_in_unit(
    prompt: str,
    unit: str,
    *,
    positional_topic: str | None = None,
    exclude_topics: frozenset[str] | None = None,
) -> str | None:
    allow_weak_composite = unit == "Unit V" and positional_topic == "Composites"
    best: tuple[str, int] | None = None
    for row_unit, topic, keywords in _TOPIC_KEYWORDS:
        if row_unit != unit or (exclude_topics and topic in exclude_topics):
            continue
        hits = _topic_keyword_hits(
            prompt,
            topic,
            keywords,
            allow_weak_composite=allow_weak_composite and topic == "Composites",
        )
        if hits and (best is None or hits > best[1]):
            best = (topic, hits)
    return best[0] if best else None


def _resolve_composite_main_topic(
    prompt: str,
    unit: str,
    *,
    section_title: str | None = None,
    allow_global: bool = False,
) -> str:
    """Composite-coded mains: tag Composites only with composite signal; else sibling/global."""
    if _composite_hits(prompt, allow_weak=False):
        return "Composites"
    if _composite_hits(prompt, allow_weak=True):
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic and global_topic != "Composites":
            return global_topic
        sibling = map_chemistry_topic_in_unit(
            prompt,
            unit,
            positional_topic="Composites",
            exclude_topics=frozenset({"Composites"}),
        )
        if sibling:
            return sibling
        return "Composites"
    sibling = map_chemistry_topic_in_unit(
        prompt,
        unit,
        exclude_topics=frozenset({"Composites"}),
    )
    if sibling:
        return sibling
    if allow_global:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic:
            return global_topic
        stored = (section_title or "").strip()
        if stored and stored not in {"Unclassified", "Composites"}:
            return stored
    return "Composites"


def _resolve_green_main_topic(
    prompt: str,
    unit: str,
    *,
    section_title: str | None = None,
    allow_global: bool = True,
) -> str:
    in_unit = map_chemistry_topic_in_unit(prompt, unit)
    if in_unit and in_unit != "Green Chemistry":
        return in_unit
    if allow_global:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic and global_topic != "Green Chemistry":
            return global_topic
    stored = (section_title or "").strip()
    if stored and stored not in {"Unclassified", "Green Chemistry"}:
        return stored
    return "Green Chemistry"


_STRICT_PART_C_MAINS = frozenset({"7"})


def _resolve_part_c_main_topic(
    prompt: str,
    unit: str,
    default_topic: str,
    *,
    section_title: str | None = None,
    main: str | None = None,
) -> str:
    del section_title
    if default_topic == "Composites":
        return _resolve_composite_main_topic(prompt, unit, allow_global=True)

    in_unit = map_chemistry_topic_in_unit(prompt, unit)
    if in_unit:
        return in_unit

    if main not in _STRICT_PART_C_MAINS:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic:
            return global_topic

    return default_topic


def _resolve_topic(prompt: str, *, unit_hint: str | None, default_topic: str) -> str:
    if unit_hint:
        if default_topic == "Composites":
            return _resolve_composite_main_topic(prompt, unit_hint, allow_global=True)
        refined = map_chemistry_topic_in_unit(prompt, unit_hint)
        if refined:
            return refined
        return default_topic
    _, global_topic = map_chemistry_topic_keywords(prompt)
    if global_topic:
        return global_topic
    return default_topic


def _match_subtopic_rule(prompt: str, *, skip_composite_weak: bool = False) -> str | None:
    lowered = _normalize_prompt(prompt)
    for name, keywords in _SUBTOPIC_RULES:
        if skip_composite_weak and name == "Composite Classification":
            if not any(keyword in lowered for keyword in keywords):
                continue
        elif not any(keyword in lowered for keyword in keywords):
            continue
        return name
    return None


def classify_chemistry_subtopic(
    prompt: str,
    *,
    part: str,
    main: str | None,
    topic: str,
    section_title: str | None = None,
) -> str:
    stored = (section_title or "").strip()
    if part == "C" and main == "1":
        if stored and stored not in {"Unclassified", "Mixed Part-A (New format Q1)"}:
            return stored
        rule_match = _match_subtopic_rule(prompt)
        if rule_match:
            return rule_match
        if topic and topic not in {"Unclassified", "Mixed Part-A (New format Q1)"}:
            return topic
        return "Mixed Part-A (New format Q1)"

    rule_match = _match_subtopic_rule(prompt)
    if rule_match:
        return rule_match
    return topic


def classify_chemistry_question(question: ExamQuestion) -> tuple[str, str, str]:
    """Return (unit, topic, subtopic) aligned to golden chemistry taxonomy."""
    part = (question.part or "").strip().upper()
    prompt = question.prompt_text or ""
    main = _base_main_number(question.question_number)
    stored_topic = (question.section_title or "").strip()

    if part == "A" and main and main in _OLD_PART_A_MAIN_UNITS:
        unit_hint, default_topic = _OLD_PART_A_MAIN_UNITS[main]
        if default_topic == "Composites":
            topic = _resolve_composite_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
                allow_global=True,
            )
        elif default_topic == "Green Chemistry":
            topic = _resolve_green_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
                allow_global=True,
            )
        else:
            topic = default_topic
    elif part == "C" and main == "1":
        _, topic = map_chemistry_topic_keywords(prompt)
        if not topic:
            topic = stored_topic or "Unclassified"
    elif part == "B" and main and main in _OLD_PART_B_MAIN_UNITS:
        unit_hint, default_topic = _OLD_PART_B_MAIN_UNITS[main]
        if default_topic == "Composites":
            topic = _resolve_composite_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
                allow_global=True,
            )
        elif default_topic == "Green Chemistry":
            topic = _resolve_green_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
                allow_global=True,
            )
        else:
            if default_topic == "Electrochemistry" and main in {"11", "17"}:
                in_unit = map_chemistry_topic_in_unit(prompt, unit_hint)
                topic = in_unit if in_unit == "Electrochemistry" else default_topic
            else:
                topic = map_chemistry_topic_in_unit(prompt, unit_hint) or default_topic
    elif part == "C" and main and main in _NEW_FORMAT_MAIN_UNITS:
        unit_hint, default_topic = _NEW_FORMAT_MAIN_UNITS[main]
        topic = _resolve_part_c_main_topic(
            prompt,
            unit_hint,
            default_topic,
            section_title=question.section_title,
            main=main,
        )
    else:
        positional = map_chemistry_by_position(part, question.question_number)
        if positional[0]:
            unit_hint, default_topic = positional
            topic = _resolve_topic(prompt, unit_hint=unit_hint, default_topic=default_topic)
        else:
            _, topic = map_chemistry_topic_keywords(prompt)
            if not topic:
                topic = stored_topic or "Unclassified"

    if stored_topic in _POLYMER_MISLABELS and part == "B":
        positional = map_chemistry_by_position(part, question.question_number)
        if positional[0]:
            unit_hint, default_topic = positional
            if default_topic == "Composites":
                topic = _resolve_composite_main_topic(
                    prompt,
                    unit_hint,
                    section_title=question.section_title,
                    allow_global=part != "C",
                )
            else:
                topic = map_chemistry_topic_in_unit(prompt, unit_hint) or default_topic
        else:
            _, keyword_topic = map_chemistry_topic_keywords(prompt)
            if keyword_topic and keyword_topic not in _POLYMER_MISLABELS:
                topic = keyword_topic

    unit = (
        _TOPIC_TO_UNIT.get(topic)
        or map_chemistry_by_position(part, question.question_number)[0]
        or question.unit
        or "Unmapped"
    )
    subtopic = classify_chemistry_subtopic(
        prompt,
        part=part,
        main=main,
        topic=topic,
        section_title=question.section_title,
    )
    return unit, topic or "Unclassified", subtopic
