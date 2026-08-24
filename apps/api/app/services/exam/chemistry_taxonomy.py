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

_POLYMER_NAMED_KEYWORDS: tuple[str, ...] = (
    "nylon",
    "kevlar",
    "bakelite",
    "buna",
    "rubber",
    "silicone",
    "pvc",
    "plastics",
    "polyethylene",
    "polypropylene",
    "teflon",
    "neoprene",
    "polystyrene",
)

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
            "surface coating",
            "sacrificial anode",
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
        _POLYMER_NAMED_KEYWORDS,
    ),
    (
        "Unit IV",
        "Solid Fuels (Coal)",
        (
            "coal",
            "proximate",
            "ultimate analysis",
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
_FUEL_TOPICS = frozenset({"Solid Fuels (Coal)", "Liquid Fuels", "Fuels — General"})
_POLYMER_GENERIC_KEYWORDS: tuple[str, ...] = (
    "thermoplastic",
    "thermoset",
    "thermosetting",
    "addition polymer",
    "condensation polymer",
    "polymerization",
    "polymerisation",
    "degree of polymerization",
    "degree of polymerisation",
    "monomer",
)
_SOLID_FUEL_KEYWORDS: tuple[str, ...] = (
    "coal",
    "proximate",
    "ultimate analysis",
    "ranking of coal",
)
_GENERAL_FUEL_KEYWORDS: tuple[str, ...] = (
    "calorific",
    "dulong",
    "hcv",
    "lcv",
    "combustion",
    "lpg",
    "cng",
    "gaseous fuel",
    "classification of fuel",
)
_LIQUID_FUEL_KEYWORDS: tuple[str, ...] = (
    "petroleum",
    "octane",
    "cetane",
    "cracking",
    "liquid fuel",
    "knocking",
)
_WATER_KEYWORDS: tuple[str, ...] = (
    "edta",
    "hardness",
    "alkalinity",
    "chlorination",
    "chlorine",
    "ion exchange",
    "reverse osmosis",
    "softening",
    "demineral",
    "de ionized",
    "de-ionized",
    "deionized",
    "potable water",
    "sterilize water",
    "ppm",
)
_CORROSION_KEYWORDS: tuple[str, ...] = (
    "corrosion",
    "pitting",
    "galvanizing",
    "cathodic protection",
    "sacrificial anode",
    "sacrificial anodic",
    "rust",
    "hot dipping",
)
_BATTERY_KEYWORDS: tuple[str, ...] = (
    "primary battery",
    "secondary battery",
    "primary and secondary",
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
    "storage battery",
    "button cell",
    "battery",
)
_UNIT_I_CROSS_TOPICS = frozenset({"Electrochemistry", "Battery Chemistry"})
_BIODIESEL_KEYWORDS: tuple[str, ...] = (
    "biodiesel",
    "transesterification",
    "transesterify",
    "bio diesel",
    "biofuel",
    "carbon neutral",
    "methyl ester",
    "jatropha",
    "fatty acid",
    "vegetable oil",
    "esterification",
)
_GREEN_KEYWORDS: tuple[str, ...] = (
    "green chemistry",
    "atom economy",
    "clean technology",
    "principles of green",
)


def _apply_topic_overrides(prompt: str, topic: str) -> str:
    lowered = _normalize_prompt(prompt)
    if topic == "Corrosion" and (
        "electrochemical corrosion" in lowered
        or ("electrochemical" in lowered and "corrosion" in lowered)
        or ("galvanic" in lowered and "corrosion" in lowered)
    ):
        return "Electrochemistry"
    if topic == "Specific Polymers" and any(
        marker in lowered
        for marker in (
            "conducting polymer",
            "polyacetylene",
            "biodegradable polymer",
            "poly lactic",
            "polylactic",
        )
    ):
        return "Conducting Polymers"
    if topic == "Specific Polymers" and any(
        marker in lowered for marker in ("surface coating", "corrosion control", "galvanizing")
    ):
        return "Corrosion"
    if topic == "Water Chemistry" and any(
        marker in lowered for marker in ("emf", "electrode potential", "nernst", "cell emf")
    ):
        return "Electrochemistry"
    if topic == "Fuels — General" and any(
        marker in lowered for marker in ("petroleum", "octane", "cetane", "cracking", "liquid fuel", "knocking")
    ):
        return "Liquid Fuels"
    if topic == "Fuels — General" and any(
        marker in lowered for marker in ("coal", "proximate", "ultimate analysis", "ranking of coal")
    ):
        return "Solid Fuels (Coal)"
    if topic == "Solid Fuels (Coal)" and "petroleum" in lowered:
        return "Liquid Fuels"
    return topic


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


def _specific_polymer_hits(
    prompt: str,
    keywords: tuple[str, ...],
    *,
    allow_generic: bool,
) -> int:
    hits = _keyword_hits(prompt, keywords)
    if allow_generic:
        hits += _keyword_hits(prompt, _POLYMER_GENERIC_KEYWORDS)
    return hits


def _map_unit_i_cross_content(prompt: str) -> str | None:
    """Part C cross-unit prompts that golden rolls to Unit I electrochemistry/battery."""
    in_unit = map_chemistry_topic_in_unit(prompt, "Unit I")
    if in_unit in _UNIT_I_CROSS_TOPICS:
        return in_unit
    return None


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
    allow_generic_polymers = positional_topic == "Specific Polymers"
    best: tuple[str, int] | None = None
    for row_unit, topic, keywords in _TOPIC_KEYWORDS:
        if row_unit != unit or (exclude_topics and topic in exclude_topics):
            continue
        if topic == "Specific Polymers":
            hits = _specific_polymer_hits(
                prompt,
                keywords,
                allow_generic=allow_generic_polymers,
            )
        else:
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
    """Composite-coded mains: content-first; weak composite alone does not win."""
    if _keyword_hits(prompt, _BIODIESEL_KEYWORDS) >= 1:
        return "Biodiesel"
    if _keyword_hits(prompt, _GREEN_KEYWORDS) >= 1:
        return "Green Chemistry"
    if _composite_hits(prompt, allow_weak=False):
        return "Composites"
    if _composite_hits(prompt, allow_weak=True):
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic and global_topic not in {"Composites"}:
            if global_topic == "Specific Polymers" and not _specific_polymer_hits(
                prompt, _POLYMER_NAMED_KEYWORDS, allow_generic=False
            ):
                pass
            else:
                return global_topic
        sibling = map_chemistry_topic_in_unit(
            prompt,
            unit,
            positional_topic="Composites",
            exclude_topics=frozenset({"Composites", "Green Chemistry"}),
        )
        if sibling == "Specific Polymers" and not _specific_polymer_hits(
            prompt, _POLYMER_NAMED_KEYWORDS, allow_generic=False
        ):
            sibling = None
        if sibling:
            return sibling
        return "Composites"
    sibling = map_chemistry_topic_in_unit(
        prompt,
        unit,
        exclude_topics=frozenset({"Composites"}),
    )
    if sibling and sibling != "Green Chemistry":
        return sibling
    if allow_global:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic and global_topic not in {"Composites"}:
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
    if _keyword_hits(prompt, _BIODIESEL_KEYWORDS) >= 1:
        return "Biodiesel"
    if _keyword_hits(prompt, _GREEN_KEYWORDS) >= 1:
        return "Green Chemistry"
    if _composite_hits(prompt, allow_weak=False):
        return "Composites"
    if allow_global:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic in _FUEL_TOPICS:
            return global_topic
        if global_topic and global_topic not in {"Green Chemistry", "Composites"}:
            return global_topic
    in_unit = map_chemistry_topic_in_unit(
        prompt,
        unit,
        exclude_topics=frozenset({"Composites"}),
    )
    if in_unit and in_unit not in {"Green Chemistry", "Composites"}:
        return in_unit
    stored = (section_title or "").strip()
    if stored and stored not in {"Unclassified", "Green Chemistry", "Composites"}:
        return stored
    return "Green Chemistry"


def _resolve_solid_fuels_main_topic(
    prompt: str,
    unit: str,
    *,
    section_title: str | None = None,
    allow_global: bool = True,
) -> str:
    """Coal-coded Part C mains: coal analysis stays; cross-content uses named-polymer gate."""
    if _keyword_hits(prompt, _SOLID_FUEL_KEYWORDS) >= 1:
        return "Solid Fuels (Coal)"
    if _keyword_hits(prompt, _CORROSION_KEYWORDS) >= 1:
        return "Corrosion"
    if _keyword_hits(prompt, _BIODIESEL_KEYWORDS) >= 1:
        return "Biodiesel"
    if _keyword_hits(prompt, _GREEN_KEYWORDS) >= 1:
        return "Green Chemistry"
    unit_i = _map_unit_i_cross_content(prompt)
    if unit_i:
        return unit_i
    named_polymer = _specific_polymer_hits(prompt, _POLYMER_NAMED_KEYWORDS, allow_generic=False)
    if named_polymer:
        return "Specific Polymers"
    generic_polymer = _keyword_hits(prompt, _POLYMER_GENERIC_KEYWORDS)
    if generic_polymer:
        conducting = map_chemistry_topic_in_unit(
            prompt,
            unit,
            positional_topic="Conducting Polymers",
        )
        if conducting == "Conducting Polymers":
            return "Conducting Polymers"
    if allow_global:
        _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
        if global_topic and global_topic not in {"Solid Fuels (Coal)"}:
            return global_topic
        stored = (section_title or "").strip()
        if stored and stored not in {"Unclassified", "Solid Fuels (Coal)"}:
            return stored
    return "Solid Fuels (Coal)"


def _resolve_fuels_general_main_topic(
    prompt: str,
    unit: str,
    *,
    section_title: str | None = None,
) -> str:
    """Fuels — General positional mains (Part A Q7, Part B Q14): content-first fuel/corrosion/polymer."""
    if _keyword_hits(prompt, _SOLID_FUEL_KEYWORDS) >= 1:
        return "Solid Fuels (Coal)"
    if _keyword_hits(prompt, _GENERAL_FUEL_KEYWORDS) >= 1:
        return "Fuels — General"
    if _keyword_hits(prompt, _LIQUID_FUEL_KEYWORDS) >= 1:
        return "Liquid Fuels"
    if _keyword_hits(prompt, _CORROSION_KEYWORDS) >= 1:
        return "Corrosion"
    if _keyword_hits(prompt, _BATTERY_KEYWORDS) >= 1:
        return "Battery Chemistry"
    unit_i = _map_unit_i_cross_content(prompt)
    if unit_i:
        return unit_i
    if _specific_polymer_hits(prompt, _POLYMER_NAMED_KEYWORDS, allow_generic=False):
        return "Specific Polymers"
    if _keyword_hits(prompt, _BIODIESEL_KEYWORDS) >= 1:
        return "Biodiesel"
    _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
    if global_topic:
        return global_topic
    stored = (section_title or "").strip()
    if stored and stored not in {"Unclassified", "Fuels — General"}:
        return stored
    return "Fuels — General"


_STRICT_PART_C_MAINS = frozenset({"7"})


def _resolve_part_c_main_topic(
    prompt: str,
    unit: str,
    default_topic: str,
    *,
    section_title: str | None = None,
    main: str | None = None,
) -> str:
    if default_topic == "Composites":
        return _resolve_composite_main_topic(prompt, unit, section_title=section_title, allow_global=True)
    if default_topic == "Green Chemistry":
        return _resolve_green_main_topic(prompt, unit, section_title=section_title, allow_global=True)
    if default_topic == "Solid Fuels (Coal)":
        return _resolve_solid_fuels_main_topic(prompt, unit, section_title=section_title, allow_global=True)

    in_unit = map_chemistry_topic_in_unit(
        prompt,
        unit,
        positional_topic=default_topic,
    )
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
        elif default_topic == "Fuels — General":
            topic = _resolve_fuels_general_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
            )
        elif default_topic == "Battery Chemistry":
            topic = map_chemistry_topic_in_unit(
                prompt,
                unit_hint,
                positional_topic=default_topic,
            ) or default_topic
        elif default_topic == "Conducting Polymers":
            if _keyword_hits(prompt, _BATTERY_KEYWORDS) >= 1:
                topic = "Battery Chemistry"
            else:
                in_unit = map_chemistry_topic_in_unit(
                    prompt,
                    unit_hint,
                    positional_topic=default_topic,
                )
                if in_unit:
                    topic = in_unit
                else:
                    _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
                    topic = global_topic or default_topic
        else:
            in_unit = map_chemistry_topic_in_unit(
                prompt,
                unit_hint,
                positional_topic=default_topic,
            )
            if in_unit:
                topic = in_unit
            elif default_topic in {"Specific Polymers", "Conducting Polymers", "Water Chemistry"}:
                _global_unit, global_topic = map_chemistry_topic_keywords(prompt)
                topic = global_topic or default_topic
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
        elif default_topic == "Fuels — General":
            topic = _resolve_fuels_general_main_topic(
                prompt,
                unit_hint,
                section_title=question.section_title,
            )
        else:
            if default_topic == "Electrochemistry" and main in {"11", "17"}:
                if _keyword_hits(prompt, _BATTERY_KEYWORDS) >= 1:
                    topic = "Battery Chemistry"
                else:
                    in_unit = map_chemistry_topic_in_unit(
                        prompt,
                        unit_hint,
                        positional_topic=default_topic,
                    )
                    topic = in_unit or default_topic
            else:
                topic = (
                    map_chemistry_topic_in_unit(
                        prompt,
                        unit_hint,
                        positional_topic=default_topic,
                    )
                    or default_topic
                )
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

    topic = _apply_topic_overrides(prompt, topic)

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
