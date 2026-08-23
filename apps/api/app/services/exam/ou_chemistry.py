"""OU Engineering Chemistry (BS 204 CH) PYQ parsing helpers — SP-061b."""

from __future__ import annotations

import re
from dataclasses import dataclass

# OCR-tolerant: "E - 5616", "E- 5616", "/0" for "/O", optional /BL, ignore /AICTE.
_OU_CODE = re.compile(
    r"Code\s*No\.?\s*[:.]?\s*"
    r"(?:([ED])\s*-\s*(\d{4})\s*/\s*([ON0])0?(?:\s*/\s*(BL))?|(15164))",
    re.IGNORECASE,
)
_JUNK_FIVE_DIGIT = frozenset({"28000", "41000"})
GOLDEN_CHEMISTRY_CODES: tuple[str, ...] = (
    "E-5002/O/BL",
    "E-5616/N/BL",
    "E-5014/O/BL",
    "E-5807/N/BL",
    "E-5002/O",
    "E-5870/N",
    "E-5014/O",
    "E-5616/N",
    "D-2002/O",
    "D-2014/O/BL",
    "D-2337/N",
    "D-2331/N",
    "15164",
)
GOLDEN_CHEMISTRY_FORMAT: dict[str, str] = {
    code: ("Old" if "/O" in code else "New") for code in GOLDEN_CHEMISTRY_CODES
}

_Q_MARK = re.compile(
    r"(?:^|[\s\n])(\d{1,2})\s*[.)]\s*(?:\(([a-g@])\)|([a-g])\))?",
    re.IGNORECASE | re.MULTILINE,
)
_ORPHAN_SUB = re.compile(r"\(([a-g])\)\s+", re.IGNORECASE)
_PART_ANYWHERE = re.compile(r"PART\s*[-–—=\s]*([AB])\b", re.IGNORECASE)
_HEADER_SPLIT = re.compile(
    r"(?=Code\s*No\.?\s*[:.]?\s*(?:[ED]\s*-\s*\d{4}|15164)|"
    r"FACULTY OF ENGINEERING[\s\S]{0,120}?BS\s*204)",
    re.IGNORECASE,
)
_OU_SESSION = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s*,?\s*(?:/|\s)?\s*(January|February|March|April|May|June|July|August|September|October|November|December)?"
    r"\s*,?\s*(\d{4})",
    re.IGNORECASE,
)
_BS204_SUBJECT = re.compile(r"BS\s*204|Engineering\s+Chemistry", re.IGNORECASE)
_NEW_FORMAT = re.compile(r"first question is compulsory", re.IGNORECASE)

_UNIT_KEYWORDS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Unit I", "Electrochemistry", (
        "nernst", "electrode", "calomel", "quinhydrone", "emf", "electrochem",
        "fuel cell", "electrochemical",         "electrochemical series", "glass electrode",
        "reference electrode", "electrode potential", "galvanic", "electrolytic",
    )),
    ("Unit I", "Battery Chemistry", (
        "battery", "lead-acid", "lead acid", "lithium", "zinc-carbon", "alkaline",
        "primary battery", "secondary battery", "primary and secondary",
    )),
    ("Unit II", "Water Chemistry", (
        "hardness", "edta", "alkalinity", "chlorination", "ion exchange",
        "reverse osmosis", "softening", "water treatment", " ro ", "demineral",
    )),
    ("Unit II", "Corrosion", (
        "corrosion", "pitting", "galvanizing", "cathodic", "rust", "waterline",
        "electrochemical corrosion", "hot dipping",
    )),
    ("Unit III", "Specific Polymers", (
        "polymer", "pvc", "nylon", "kevlar", "bakelite", "rubber", "thermoplastic",
        "thermoset", "buna", "plastics", "addition polymer", "condensation polymer",
    )),
    ("Unit III", "Conducting Polymers", (
        "conducting polymer", "polyacetylene", "biodegradable", "pla", "conducting polymers",
    )),
    ("Unit IV", "Fuels — General", (
        "calorific", "dulong", "hcv", "lcv", "combustion", "fuel classification",
        "gaseous fuel", "lpg", "cng",
    )),
    ("Unit IV", "Liquid Fuels", (
        "petroleum", "octane", "cetane", "cracking", "liquid fuel", "moving bed",
        "catalytic cracking",
    )),
    ("Unit IV", "Solid Fuels (Coal)", (
        "coal", "proximate", "ultimate analysis", "solid fuel", "ranking of coal",
    )),
    ("Unit V", "Green Chemistry", (
        "green chemistry", "atom economy", "clean technology", "principles of green",
    )),
    ("Unit V", "Biodiesel", (
        "biodiesel", "transesterification", "biofuel", "carbon neutral", "bio diesel",
    )),
    ("Unit V", "Composites", (
        "composite", "matrix", "reinforcement", "fibre", "fiber", "composite material",
    )),
]

_NEW_FORMAT_MAIN_UNITS: dict[str, tuple[str, str]] = {
    "2": ("Unit II", "Water Chemistry"),
    "3": ("Unit III", "Specific Polymers"),
    "4": ("Unit IV", "Solid Fuels (Coal)"),
    "5": ("Unit V", "Green Chemistry"),
    "6": ("Unit V", "Composites"),
    "7": ("Unit I", "Battery Chemistry"),
}

_OLD_PART_B_MAIN_UNITS: dict[str, tuple[str, str]] = {
    "11": ("Unit I", "Electrochemistry"),
    "12": ("Unit II", "Water Chemistry"),
    "13": ("Unit III", "Specific Polymers"),
    "14": ("Unit IV", "Fuels — General"),
    "15": ("Unit V", "Green Chemistry"),
    "16": ("Unit V", "Composites"),
    "17": ("Unit I", "Electrochemistry"),
}

_OLD_PART_A_MAIN_UNITS: dict[str, tuple[str, str]] = {
    "1": ("Unit I", "Electrochemistry"),
    "2": ("Unit I", "Battery Chemistry"),
    "3": ("Unit II", "Water Chemistry"),
    "4": ("Unit II", "Corrosion"),
    "5": ("Unit III", "Specific Polymers"),
    "6": ("Unit III", "Conducting Polymers"),
    "7": ("Unit IV", "Fuels — General"),
    "8": ("Unit IV", "Liquid Fuels"),
    "9": ("Unit V", "Green Chemistry"),
    "10": ("Unit V", "Composites"),
}


@dataclass(frozen=True, slots=True)
class OuPaperHeader:
    session: str | None
    code: str | None
    year: str | None
    paper_format: str | None  # Old | New

    @property
    def paper_label(self) -> str | None:
        parts = [part for part in (self.session, self.code, self.year) if part]
        return " | ".join(parts) if parts else None


def is_ou_chemistry_source(*, course_id: str, filename: str, sample_text: str = "") -> bool:
    course = course_id.strip().lower()
    name = filename.lower()
    if course in {"chemistry", "cn", "chem"}:
        return True
    if "ou question" in name or "engineering chemistry" in name:
        return True
    if sample_text and _BS204_SUBJECT.search(sample_text[:800]):
        return True
    return False


def normalize_ou_code(raw: str | None) -> str | None:
    """Normalize OCR codes; drop junk 5-digit hits like 28000 / 41000."""
    if not raw:
        return None
    cleaned = re.sub(r"\s+", "", raw.upper())
    cleaned = re.sub(r"/AICTE.*$", "", cleaned)
    cleaned = cleaned.replace("/O0", "/O").replace("/0", "/O")
    if cleaned in _JUNK_FIVE_DIGIT:
        return None
    if cleaned == "15164":
        return cleaned
    match = re.fullmatch(r"([ED])-(\d{4})/([ON])(?:/(BL))?", cleaned)
    if not match:
        return None
    code = f"{match.group(1)}-{match.group(2)}/{match.group(3)}"
    if match.group(4):
        code += "/BL"
    return code


def _code_from_match(match: re.Match[str]) -> str | None:
    if match.group(5):
        return normalize_ou_code(match.group(5))
    letter = match.group(1)
    digits = match.group(2)
    on = match.group(3)
    bl = match.group(4)
    if not letter or not digits or not on:
        return None
    raw = f"{letter}-{digits}/{on}"
    if bl:
        raw += f"/{bl}"
    return normalize_ou_code(raw)


def extract_ou_codes(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _OU_CODE.finditer(text):
        code = _code_from_match(match)
        if code and code not in seen:
            seen.add(code)
            found.append(code)
    return found


def _format_for_code(code: str | None, text: str, current: str | None) -> str | None:
    if current:
        return current
    if code and code in GOLDEN_CHEMISTRY_FORMAT:
        return GOLDEN_CHEMISTRY_FORMAT[code]
    if code:
        if "/N" in code or code.isdigit():
            return "New"
        if "/O" in code:
            return "Old"
    if _NEW_FORMAT.search(text[:2000]):
        return "New"
    if _PART_ANYWHERE.search(text):
        return "Old"
    return None


def header_with_code(header: OuPaperHeader, code: str | None, text: str = "") -> OuPaperHeader:
    resolved = normalize_ou_code(code) or code
    paper_format = _format_for_code(resolved, text or "", header.paper_format)
    return OuPaperHeader(
        session=header.session,
        code=resolved,
        year=header.year,
        paper_format=paper_format,
    )


def detect_ou_paper_header(text: str) -> OuPaperHeader:
    sample = text[:2500]
    codes = extract_ou_codes(sample) or extract_ou_codes(text)
    code = codes[0] if codes else None

    session: str | None = None
    year: str | None = None
    session_match = _OU_SESSION.search(sample)
    if session_match:
        month_a = session_match.group(1).title()
        month_b = session_match.group(2)
        year = session_match.group(3)
        if month_b:
            session = f"{month_a}/{month_b.title()} {year}"
        else:
            session = f"{month_a} {year}"

    paper_format = _format_for_code(code, text, None)
    return OuPaperHeader(session=session, code=code, year=year, paper_format=paper_format)


def assign_golden_codes_to_sections(
    sections: list[tuple[OuPaperHeader, str]],
) -> list[tuple[OuPaperHeader, str]]:
    """Fill missing codes from golden order (E-5616/N/BL between E-5002/O/BL and E-5014/O/BL)."""
    labeled: list[tuple[OuPaperHeader, str, str | None]] = []
    used: set[str] = set()
    for header, chunk in sections:
        code = normalize_ou_code(header.code) or (extract_ou_codes(chunk)[:1] or [None])[0]
        if code:
            used.add(code)
        labeled.append((header, chunk, code))

    last_idx = -1
    filled: list[tuple[OuPaperHeader, str, str | None]] = []
    for index, (header, chunk, code) in enumerate(labeled):
        if code and code in GOLDEN_CHEMISTRY_CODES:
            last_idx = GOLDEN_CHEMISTRY_CODES.index(code)
            filled.append((header, chunk, code))
            continue
        if code:
            filled.append((header, chunk, code))
            continue
        next_idx = len(GOLDEN_CHEMISTRY_CODES)
        for later_header, _later_chunk, later_code in labeled[index + 1 :]:
            del later_header
            if later_code and later_code in GOLDEN_CHEMISTRY_CODES:
                next_idx = GOLDEN_CHEMISTRY_CODES.index(later_code)
                break
        gap = [
            candidate
            for candidate in GOLDEN_CHEMISTRY_CODES[last_idx + 1 : next_idx]
            if candidate not in used
        ]
        assigned = gap[0] if gap else None
        if assigned:
            used.add(assigned)
            last_idx = GOLDEN_CHEMISTRY_CODES.index(assigned)
        filled.append((header, chunk, assigned))

    return [
        (header_with_code(header, code, chunk), chunk) for header, chunk, code in filled
    ]


def split_ou_bundle_text(text: str) -> list[tuple[OuPaperHeader, str]]:
    """Split a multi-paper OU bundle on Code No / BS 204 headers, then assign golden codes."""
    starts = [match.start() for match in _HEADER_SPLIT.finditer(text)]
    if not starts:
        sections = [(detect_ou_paper_header(text), text)]
        return assign_golden_codes_to_sections(sections)
    if starts[0] != 0:
        starts = [0, *starts]

    sections: list[tuple[OuPaperHeader, str]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) < 80:
            continue
        sections.append((detect_ou_paper_header(chunk), chunk))
    return assign_golden_codes_to_sections(sections)


def split_parts_loose(text: str) -> tuple[str, str]:
    """Find PART-A / PART-B even mid-line or as PART=B (OCR)."""
    part_a = _PART_ANYWHERE.search(text)
    part_b = None
    if part_a and part_a.group(1).upper() == "A":
        part_b = _PART_ANYWHERE.search(text, part_a.end())
        while part_b and part_b.group(1).upper() != "B":
            part_b = _PART_ANYWHERE.search(text, part_b.end())
    elif part_a and part_a.group(1).upper() == "B":
        part_b = part_a
        part_a = None
    if part_a and part_b:
        return text[part_a.end() : part_b.start()], text[part_b.end() :]
    if part_a:
        return text[part_a.end() :], ""
    if part_b:
        return "", text[part_b.end() :]
    return "", ""


def harvest_numbered_questions(text: str, *, paper_format: str | None) -> list[tuple[str, str, str]]:
    """OCR-tolerant numbered harvest. Returns (part, qnum, prompt)."""
    prior = (paper_format or "").strip()
    if prior == "New":
        return expand_new_format_questions(text)
    if prior == "Old":
        return expand_old_format_questions(text)
    expanded = expand_new_format_questions(text)
    if len(expanded) >= 4:
        return expanded
    return expand_old_format_questions(text)


_MAIN_MARK = re.compile(
    r"(?:^|[\s\n])(?P<raw>14[67]|4[0-7]|0|[1-9]\d?)"
    r"(?:\s*[.)]\s*|\s*,\s*(?=\(?[a-gA-G])|\s+)(?=\(?[a-gA-G]|Write|What|Define|Explain|Describe|"
    r"Differentiate|Calculate|Outline|Give|List|How|Discuss|Classify|Mention|"
    r"Distinguish|Derive|Compare|State|Answer)",
    re.MULTILINE | re.IGNORECASE,
)
_GHOST_MAIN = re.compile(
    r"(?:^|[\s\n])[.\-*]\s*a\)",
    re.IGNORECASE | re.MULTILINE,
)
_LETTER_MARK = re.compile(
    r"(?:^|[\s\n])(?:\(([a-g@])\)|([a-g])\))",
    re.IGNORECASE | re.MULTILINE,
)
_ROMAN_MARK = re.compile(
    r"(?:^|[\s\n])(?:\(([ivx]{1,3})\)|([ivx]{1,3})\))",
    re.IGNORECASE | re.MULTILINE,
)
_QUESTIONISH = re.compile(
    r"\b(?:Write|What|Define|Explain|Describe|Differentiate|Calculate|Outline|"
    r"Give|List|How|Discuss|Classify|Mention|Distinguish|Derive|Compare|State|Why)\b",
    re.IGNORECASE,
)
_PART_A_NUM = re.compile(
    r"(?:^|[\s\n])(?P<raw>40|0|10|[1-9])\s*[.)]",
    re.MULTILINE,
)
_PART_B_NUM = re.compile(
    r"(?:^|[\s\n])(?P<raw>14[67]|4[1-7]|1[1-7])\s*[.)]",
    re.MULTILINE,
)
_GHOST_Q = re.compile(
    r"(?:^|[\s\n])(?:[.\-*]|>|[a-eA-E]\.)\s+"
    r"(?=(?:Write|What|Define|Explain|Describe|Differentiate|Calculate|"
    r"Outline|How|Discuss|Classify|Mention|Distinguish|Derive|Compare|State|Why)\b)",
    re.IGNORECASE | re.MULTILINE,
)
_SPLIT_Q = re.compile(
    r"(?:^|(?<=[.?!]))\s*"
    r"(?=(?:Write|What|Define|Explain|Describe|Differentiate|Calculate|"
    r"Outline|How|Discuss|Classify|Mention|Distinguish|Why)\b)",
    re.IGNORECASE | re.MULTILINE,
)


def _ocr_main_number(raw: str, *, old_part: str | None) -> int | None:
    try:
        value = int(raw)
    except ValueError:
        return None
    if old_part == "A":
        if value == 0:
            return 10
        if value == 40:
            return 10
        if 1 <= value <= 10:
            return value
        return None
    if old_part == "B":
        mapping = {41: 11, 42: 12, 43: 13, 44: 14, 45: 15, 46: 16, 47: 17, 147: 17}
        if value in mapping:
            return mapping[value]
        if 11 <= value <= 17:
            return value
        return None
    if 1 <= value <= 17:
        return value
    return None


_CLEAN = None


def _prompt_at(text: str, start: int, end: int) -> str:
    global _CLEAN
    if _CLEAN is None:
        from app.services.exam.pyq_parser import _clean_prompt

        _CLEAN = _clean_prompt
    return _CLEAN(text[start:end])


def _letter_slices(block: str) -> list[tuple[str, str]]:
    marks = list(_LETTER_MARK.finditer(block))
    if not marks:
        return []
    slices: list[tuple[str, str]] = []
    for index, match in enumerate(marks):
        letter = (match.group(1) or match.group(2) or "a").lower()
        letter = "a" if letter == "@" else letter
        end = marks[index + 1].start() if index + 1 < len(marks) else len(block)
        prompt = _prompt_at(block, match.end(), end)
        if len(prompt) >= 10:
            slices.append((letter, prompt))
    return slices


def _roman_slices(block: str) -> list[str]:
    marks = list(_ROMAN_MARK.finditer(block))
    if len(marks) < 2:
        return []
    prompts: list[str] = []
    for index, match in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(block)
        prompt = _prompt_at(block, match.end(), end)
        if len(prompt) >= 10:
            prompts.append(prompt)
    return prompts


def _emit_lettered(
    part: str,
    main: int,
    block: str,
    *,
    max_letter: str = "g",
) -> list[tuple[str, str, str]]:
    letters = _letter_slices(block)
    items: list[tuple[str, str, str]] = []
    next_ord = ord("a")
    limit = ord(max_letter)
    if not letters:
        romans = _roman_slices(block)
        if romans:
            for prompt in romans:
                if next_ord > limit:
                    break
                items.append((part, f"{main}{chr(next_ord)}", prompt))
                next_ord += 1
            return items
        prompt = _prompt_at(block, 0, len(block))
        if len(prompt) >= 10:
            items.append((part, str(main) if part == "A" else f"{main}a", prompt))
        return items

    for _letter, letter_prompt in letters:
        romans = _roman_slices(letter_prompt)
        if len(romans) >= 2:
            for prompt in romans:
                if next_ord > limit:
                    break
                items.append((part, f"{main}{chr(next_ord)}", prompt))
                next_ord += 1
        else:
            if next_ord > limit:
                break
            items.append((part, f"{main}{chr(next_ord)}", letter_prompt))
            next_ord += 1
    return items


def expand_new_format_questions(text: str) -> list[tuple[str, str, str]]:
    """Q1 a–g and Q2–7 a/b/c plus roman (i)/(ii) from mid-line OCR."""
    two = re.search(r"(?:(?<=^)|(?<=[\s\n]))2\s*[.)]\s*", text)
    mains = list(_MAIN_MARK.finditer(text))
    starts: list[tuple[int, int, int]] = []  # value, start, end_of_mark
    for match in mains:
        value = _ocr_main_number(match.group("raw"), old_part=None)
        if value is None or value < 1 or value > 7:
            continue
        starts.append((value, match.start(), match.end()))
    starts = [(v, s, e) for v, s, e in starts if v <= 7]
    # Keep first occurrence of each main.
    seen: set[int] = set()
    unique: list[tuple[int, int, int]] = []
    for value, start, end in starts:
        if value in seen:
            continue
        seen.add(value)
        unique.append((value, start, end))
    unique.sort(key=lambda row: row[1])

    items: list[tuple[str, str, str]] = []
    if 1 not in seen:
        q1_block = text[: two.start()] if two else text[: min(len(text), 1800)]
        q1_items = _emit_lettered("C", 1, q1_block, max_letter="g")
        # Prefer a–g orphans if the block is the preamble + Q1.
        orphans = _letter_slices(q1_block)
        if len(orphans) >= 3:
            q1_items = [("C", f"1{letter}", prompt) for letter, prompt in orphans[:7]]
        items.extend(q1_items)
    for index, (value, start, mark_end) in enumerate(unique):
        end = unique[index + 1][1] if index + 1 < len(unique) else len(text)
        block = text[mark_end:end]
        if value == 1:
            q1 = _emit_lettered("C", 1, block, max_letter="g")
            if len(q1) < 3:
                q1 = [("C", f"1{letter}", prompt) for letter, prompt in _letter_slices(block)[:7]]
            items.extend(q1)
            continue
        items.extend(_emit_lettered("C", value, block, max_letter="d"))

    deduped: list[tuple[str, str, str]] = []
    seen_q: set[str] = set()
    for item in items:
        if item[1] in seen_q or len(item[2]) < 10:
            continue
        seen_q.add(item[1])
        deduped.append(item)
    return _recover_ghost_new_mains(text, deduped)


def _recover_ghost_new_mains(
    text: str,
    items: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """D-2337-style OCR: '. a)' / '- a)' blocks with the main number dropped."""
    present = set()
    for _part, qnum, _prompt in items:
        match = re.match(r"^(\d+)", qnum)
        if match:
            present.add(int(match.group(1)))
    missing = [n for n in range(2, 8) if n not in present]
    if not missing:
        return items
    ghosts = list(_GHOST_MAIN.finditer(text))
    if not ghosts:
        return items
    two = re.search(r"(?:^|[\s\n])2\s*[.)]\s*", text)
    q1_end = two.start() if two else 0
    recovered = list(items)
    used_q = {qnum for _p, qnum, _t in recovered}
    for index, match in enumerate(ghosts):
        if not missing:
            break
        if q1_end and match.start() < q1_end:
            continue
        end = ghosts[index + 1].start() if index + 1 < len(ghosts) else len(text)
        block = text[match.start() : end]
        main = missing.pop(0)
        for part, qnum, prompt in _emit_lettered("C", main, block, max_letter="d"):
            if qnum not in used_q and len(prompt) >= 10:
                recovered.append((part, qnum, prompt))
                used_q.add(qnum)
    return recovered


def expand_old_format_questions(text: str) -> list[tuple[str, str, str]]:
    """Part A Q1–10 and Part B Q11–17 a)/b) from mid-line PART-A / PART=B OCR."""
    part_a, part_b = split_parts_loose(text)
    if not part_a and not part_b:
        eleven = re.search(r"(?:(?<=^)|(?<=[\s\n]))1[1-7]\s*[.)]\s*", text)
        if eleven:
            part_a, part_b = text[: eleven.start()], text[eleven.start() :]
        else:
            part_a, part_b = text, ""

    items: list[tuple[str, str, str]] = []
    items.extend(_expand_old_part_a(part_a))
    items.extend(_expand_old_part_b(part_b or text if not part_b else part_b))
    if not any(item[0] == "B" for item in items) and part_b:
        items.extend(_expand_old_part_b(part_b))
    deduped: list[tuple[str, str, str]] = []
    seen_q: set[str] = set()
    for item in items:
        if item[1] in seen_q or len(item[2]) < 10:
            continue
        seen_q.add(item[1])
        deduped.append(item)
    return deduped


def _should_split_part_a(prev: str, verb: str) -> bool:
    trimmed = prev.strip()
    core = re.sub(r"[\s\d.,;:]+$", "", trimmed)
    if len(core) < 18:
        return False
    verb_l = verb.lower()
    if verb_l in {"write", "give", "explain", "discuss", "mention"}:
        return trimmed.endswith("?") or bool(re.search(r"\n\s*$", prev))
    return bool(re.search(r"[.?]\s*$", trimmed)) or bool(re.search(r"\n\s*$", prev))


def _part_a_prompt_end(section: str, start: int, hard_end: int) -> int:
    window = section[start:hard_end]
    cut = hard_end
    ghost = _GHOST_Q.search(window)
    if ghost:
        cut = min(cut, start + ghost.start())
    for match in _SPLIT_Q.finditer(window):
        abs_pos = start + match.start()
        if abs_pos <= start + 1:
            continue
        verb_match = _QUESTIONISH.search(window[match.start() :])
        verb = verb_match.group(0) if verb_match else ""
        if _should_split_part_a(section[start:abs_pos], verb):
            cut = min(cut, abs_pos)
            break
    return cut


def _expand_old_part_a(section: str) -> list[tuple[str, str, str]]:
    raw_marks: list[tuple[int | None, int, int, str]] = []
    for match in _PART_A_NUM.finditer(section):
        value = _ocr_main_number(match.group("raw"), old_part="A")
        if value is None:
            continue
        raw_marks.append((value, match.start(), match.end(), "num"))
    for match in _GHOST_Q.finditer(section):
        raw_marks.append((None, match.start(), match.end(), "ghost"))
    raw_marks.sort(key=lambda row: row[1])

    marks: list[tuple[int | None, int, int, str]] = []
    seen_nums: set[int] = set()
    for value, start, end, kind in raw_marks:
        if marks and abs(start - marks[-1][1]) < 3:
            if kind == "num" and marks[-1][3] != "num":
                marks[-1] = (value, start, end, kind)
            continue
        if kind == "num":
            if value in seen_nums:
                continue
            seen_nums.add(value)
        marks.append((value, start, end, kind))

    if (
        marks
        and marks[0][3] == "num"
        and marks[0][0] == 4
        and 1 not in seen_nums
    ):
        marks[0] = (1, marks[0][1], marks[0][2], "num")
        seen_nums.discard(4)
        seen_nums.add(1)

    candidates: list[tuple[int, int | None, str]] = []
    claimed_spans: list[tuple[int, int]] = []

    def _add_candidate(suggested: int | None, start: int, mark_end: int, hard_end: int) -> None:
        end = _part_a_prompt_end(section, mark_end, hard_end)
        prompt = _prompt_at(section, mark_end, end)
        if len(prompt) < 10:
            return
        if any(prompt[:24] in existing[2] for existing in candidates):
            return
        candidates.append((start, suggested, prompt))
        claimed_spans.append((start, end))

    for index, (value, start, mark_end, kind) in enumerate(marks):
        hard_end = marks[index + 1][1] if index + 1 < len(marks) else len(section)
        suggested = value if kind == "num" else None
        _add_candidate(suggested, start, mark_end, hard_end)

    verb_hits = list(_QUESTIONISH.finditer(section))
    for pos, match in enumerate(verb_hits):
        if any(span_start <= match.start() < span_end for span_start, span_end in claimed_spans):
            continue
        at_break = match.start() == 0 or bool(
            re.search(r"[\n.?!|]", section[max(0, match.start() - 2) : match.start()])
        )
        if match.start() > 0 and not at_break and not _should_split_part_a(
            section[: match.start()], match.group(0)
        ):
            continue
        nxt_verb = verb_hits[pos + 1].start() if pos + 1 < len(verb_hits) else len(section)
        nxt_mark = next((s for _v, s, _e, _k in marks if s > match.start()), len(section))
        _add_candidate(None, match.start(), match.start(), min(nxt_verb, nxt_mark))

    candidates.sort(key=lambda row: row[0])
    used: set[int] = set()
    items: list[tuple[str, str, str]] = []
    for _start, suggested, prompt in candidates:
        if suggested is not None and 1 <= suggested <= 10 and suggested not in used:
            value = suggested
        else:
            value = next((n for n in range(1, 11) if n not in used), None)
            if value is None:
                continue
        used.add(value)
        items.append(("A", f"{value}a", prompt))
    items.sort(key=lambda row: int(re.match(r"\d+", row[1]).group(0) or 0))
    return items


def _expand_old_part_b(section: str) -> list[tuple[str, str, str]]:
    marks = list(_PART_B_NUM.finditer(section)) + list(_MAIN_MARK.finditer(section))
    numbered: list[tuple[int, int, int]] = []
    for match in marks:
        raw = match.groupdict().get("raw") or match.group(1)
        value = _ocr_main_number(raw, old_part="B")
        if value is None:
            continue
        numbered.append((value, match.start(), match.end()))
    numbered.sort(key=lambda row: (row[1], row[0]))
    deduped: list[tuple[int, int, int]] = []
    seen_vals: set[int] = set()
    for value, start, mark_end in numbered:
        if value in seen_vals:
            continue
        seen_vals.add(value)
        deduped.append((value, start, mark_end))
    numbered = deduped
    items: list[tuple[str, str, str]] = []
    used: set[int] = set()
    for index, (value, _start, mark_end) in enumerate(numbered):
        if value in used:
            continue
        end = numbered[index + 1][1] if index + 1 < len(numbered) else len(section)
        block = section[mark_end:end]
        used.add(value)
        items.extend(_emit_lettered("B", value, block, max_letter="c"))
    if 17 not in used and numbered:
        last_value, last_start, last_end = numbered[-1]
        tail = section[last_end:]
        extra_letters = _letter_slices(tail)
        # 16a/16b already consumed from last block; a leftover second a)/b) pair is Q17.
        if last_value == 16 and len(extra_letters) >= 4:
            for letter, prompt in extra_letters[2:4]:
                items.append(("B", f"17{letter}", prompt))
        elif last_value < 17:
            later = list(_LETTER_MARK.finditer(section[last_start:]))
            if len(later) >= 4:
                block = section[later[2].start() :]
                items.extend(_emit_lettered("B", 17, block, max_letter="c"))
    return items


def map_chemistry_unit_section(prompt: str) -> tuple[str | None, str | None]:
    lowered = re.sub(r"[^a-z0-9\s]", " ", prompt.lower())
    tokens = set(lowered.split())
    best: tuple[str, str, int] | None = None
    for unit, section, keywords in _UNIT_KEYWORDS:
        hits = sum(
            1
            for keyword in keywords
            if keyword.replace("-", " ") in lowered or keyword in tokens
        )
        if hits == 0:
            continue
        if best is None or hits > best[2]:
            best = (unit, section, hits)
    if best is None:
        return None, None
    return best[0], best[1]


def _base_main_number(question_number: str | None) -> str | None:
    if not question_number:
        return None
    match = re.match(r"^(\d+)", question_number.strip())
    return match.group(1) if match else None


def map_chemistry_by_position(
    part: str | None,
    question_number: str | None,
) -> tuple[str | None, str | None]:
    """OU BS 204 positional syllabus mapping when keyword match fails."""
    base = _base_main_number(question_number)
    if not base:
        return None, None

    part_key = (part or "").strip().upper()
    if part_key == "B" and base in _OLD_PART_B_MAIN_UNITS:
        return _OLD_PART_B_MAIN_UNITS[base]
    if part_key == "A" and base in _OLD_PART_A_MAIN_UNITS:
        return _OLD_PART_A_MAIN_UNITS[base]
    if base in _NEW_FORMAT_MAIN_UNITS:
        return _NEW_FORMAT_MAIN_UNITS[base]
    if base in _OLD_PART_B_MAIN_UNITS:
        return _OLD_PART_B_MAIN_UNITS[base]
    if base in _OLD_PART_A_MAIN_UNITS:
        return _OLD_PART_A_MAIN_UNITS[base]
    return None, None


def map_chemistry_unit_for_question(
    prompt: str,
    *,
    part: str | None = None,
    question_number: str | None = None,
) -> tuple[str | None, str | None]:
    unit, section = map_chemistry_unit_section(prompt)
    if unit:
        return unit, section
    return map_chemistry_by_position(part, question_number)


def parse_part_a_subparts(section: str) -> list[tuple[str, str]]:
    """Parse Part A numbered questions, expanding 1a)/1b) sub-parts when present."""
    from app.services.exam.pyq_parser import _clean_prompt, _is_junk_line, _PART_A_DOT, _QUESTION_VERB

    items: list[tuple[str, str]] = []
    current_main: str | None = None
    current_sub: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_main, current_sub, current_lines
        if not current_main or not current_lines:
            current_lines = []
            return
        prompt = _clean_prompt(" ".join(current_lines))
        if len(prompt) < 12:
            current_lines = []
            return
        qnum = f"{current_main}{current_sub}" if current_sub else current_main
        items.append((qnum, prompt))
        current_lines = []

    subpart_line = re.compile(r"^\s*(\d{1,2})\s*([a-g])\)\s*(.+)$", re.IGNORECASE)
    main_line = re.compile(r"^\s*(\d{1,2})[\.\)]\s*(.+)$")

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if _is_junk_line(line):
            continue

        sub_match = subpart_line.match(line)
        if sub_match:
            flush()
            current_main = sub_match.group(1).lstrip("0") or sub_match.group(1)
            current_sub = sub_match.group(2).lower()
            current_lines = [sub_match.group(3).strip()]
            continue

        inline_sub = re.match(r"^\s*(\d{1,2})\s+([a-g])\)\s*(.+)$", line, re.I)
        if inline_sub:
            flush()
            current_main = inline_sub.group(1)
            current_sub = inline_sub.group(2).lower()
            current_lines = [inline_sub.group(3).strip()]
            continue

        main_match = main_line.match(line) or _PART_A_DOT.match(line)
        if main_match and _QUESTION_VERB.search(main_match.group(2)):
            flush()
            current_main = main_match.group(1).lstrip("0") or main_match.group(1)
            current_sub = None
            current_lines = [main_match.group(2).strip()]
            continue

        orphan_sub = re.match(r"^\s*([a-g])\)\s*(.+)$", line, re.I)
        if orphan_sub and current_main:
            flush()
            current_sub = orphan_sub.group(1).lower()
            current_lines = [orphan_sub.group(2).strip()]
            continue

        if current_main:
            current_lines.append(line)

    flush()
    return items
