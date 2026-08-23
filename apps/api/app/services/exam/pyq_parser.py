"""Regex-first exam question parser for past_paper PDFs (ingest-time only)."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.services.exam.pyq_formats import detect_format, strip_watermarks
from app.services.exam.ou_chemistry import (
    expand_new_format_questions,
    expand_old_format_questions,
    harvest_numbered_questions,
    is_ou_chemistry_source,
    map_chemistry_unit_for_question,
    map_chemistry_unit_section,
    parse_part_a_subparts,
    split_ou_bundle_text,
    split_parts_loose,
)
from app.services.exam.topic_frequency import _READABLE_CHAR_THRESHOLD, _best_keyword_match, _build_keyword_patterns
from app.services.pdf_extract import DocumentOutline, PageText

logger = logging.getLogger(__name__)

# OCR-tolerant PART headers (standalone lines; Note lines excluded in _split_parts).
_PART_A_LINE = re.compile(
    r"^\s*PART\s*[-\s—–ΓÇö]*\s*(?:A|8)\b",
    re.IGNORECASE,
)
_PART_B_LINE = re.compile(
    r"^\s*_?\s*PART\s*[-\s—–ΓÇö]*\s*(?:B|8|1)\b",
    re.IGNORECASE,
)
_PAPER_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s*,?\s*(\d{4})",
    re.IGNORECASE,
)
_MARKS_INLINE = re.compile(
    r"\(\s*\d+\s*[xX×]\s*\d+\s*=\s*\d+\s*(?:Marks?)?\s*\)|"
    r"\(\s*\d+\s*\+\s*\d+\s*M\s*\)|"
    r"\b\d+\s*M\b|\b\d+\+\d+\s*M\b",
    re.IGNORECASE,
)
_PART_A_NUMBER = re.compile(r"^\s*(\d{1,2})\s+(.+)$")
_PART_A_NUMBER_ALT = re.compile(r"^\s*(\d{1,2})\s*[_\.]\s*(.+)$")
_PART_A_DOT = re.compile(r"^\s*(\d{1,2})[\.\)]\s*(.+)$")
_PART_B_MAIN = re.compile(r"^\s*(?:~)?(\d{1,2})\s+(.+)$")
_PART_B_SUB = re.compile(r"^\s*([a-c])\)\s*(.+)$", re.IGNORECASE)
_PART_B_SUB_ROMAN = re.compile(r"^\s*([ivx]+)\)\s*(.+)$", re.IGNORECASE)
_ANSWER_ANY = re.compile(r"Answer any (?:five|four|three|two) questions", re.IGNORECASE)
_JUNK_LINE = re.compile(
    r"^(?:Code No\.|FACULTY OF|B\.E\.|Subject:|Time:|Max\.|\*{3,}|Note:|Missing data|"
    r"ODDASIF|Download|Bown a|ese w Re|seeeee|Nw$|Ny &|Nye OR|10$|\d{1,2}$)",
    re.IGNORECASE,
)
_QUESTION_VERB = re.compile(
    r"^(?:\d{1,2}[\.\)]\s*)?"
    r"(?:Write|What|Define|Explain|Describe|Which|Draw|List|Compare|Discuss|Compute|Prove|Give|"
    r"Distinguish|Brief|Demonstrate|Consider|Show|Assume|Differentiate|Derive|Expiain|in what|"
    r"What are|What is|What Is|What isthe|What advantages|What you mean)",
    re.IGNORECASE,
)


@dataclass
class ExamQuestionDraft:
    page: int
    paper_label: str | None
    part: str
    question_number: str
    prompt_text: str
    marks: int | None = None
    unit: str | None = None
    section_title: str | None = None
    extraction_method: str = "regex"
    confidence: float = 1.0


def normalize_prompt(text: str) -> str:
    lowered = text.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _token_variants(token: str) -> set[str]:
    variants = {token}
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    if not token.endswith("s"):
        variants.add(f"{token}s")
    if token == "ai":
        variants.update({"artificial", "intelligence"})
    if token in {"oop", "oriented"}:
        variants.update({"object", "oriented", "programming"})
    return variants


def prompt_overlap_score(parsed: str, seed: str) -> float:
    """Substring, fuzzy ratio, or seed-token recall (>=60% threshold target)."""
    p_norm = normalize_prompt(parsed)
    s_norm = normalize_prompt(seed)
    if not p_norm or not s_norm:
        return 0.0
    if p_norm in s_norm or s_norm in p_norm:
        shorter = min(len(p_norm), len(s_norm))
        longer = max(len(p_norm), len(s_norm))
        return shorter / longer if longer else 0.0

    fuzzy = SequenceMatcher(None, p_norm, s_norm).ratio()

    s_tokens = [t for t in s_norm.split() if len(t) >= 2 or t.isdigit()]
    if s_tokens:
        hits = 0
        for token in s_tokens:
            if any(v in p_norm for v in _token_variants(token)):
                hits += 1
        recall = hits / len(s_tokens)
    else:
        recall = 0.0

    p_tokens = set(p_norm.split())
    s_token_set = set(s_tokens)
    jaccard = len(p_tokens & s_token_set) / len(p_tokens | s_token_set) if p_tokens and s_token_set else 0.0
    return max(fuzzy, recall, jaccard)


def prompts_match(parsed: str, seed: str, *, threshold: float = 0.6) -> bool:
    return prompt_overlap_score(parsed, seed) >= threshold


def _clean_prompt(text: str) -> str:
    cleaned = _MARKS_INLINE.sub(" ", text)
    cleaned = re.sub(r"^[_\W]+", "", cleaned)
    cleaned = re.sub(r"\bst condition\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[,~]{2,}", " ", cleaned)
    # Strip trailing mark annotations: (2), @), «2), etc.
    cleaned = re.sub(r"[\s\.\(«»]*(?:\d+\s*Marks?|\d+\s*\)|@[^\)]*\)|\\N|\d+\s*$).*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-;~'\"«»@")
    return cleaned


def _is_bnf_fragment(text: str) -> bool:
    stripped = text.strip()
    if "<" in stripped and ">" in stripped and len(stripped.split()) <= 12:
        return True
    return bool(re.match(r"^[\s<>\-\|\.Ia-z0-9]+$", stripped, re.I)) and "<" in stripped


def _detect_paper_label(text: str) -> str | None:
    match = _PAPER_DATE.search(text)
    if match:
        return f"{match.group(1).title()} {match.group(2)}"
    return None


def _split_parts(text: str) -> tuple[str, str]:
    """Split text into Part-A and Part-B bodies using OCR-tolerant headers."""
    part_a = ""
    part_b = ""
    part_a_end: int | None = None
    part_b_start: int | None = None

    for match in re.finditer(r"^.*$", text, re.MULTILINE):
        line = match.group(0)
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\s*Note\b", stripped, re.IGNORECASE):
            continue
        if _PART_A_LINE.match(stripped) and part_a_end is None:
            part_a_end = match.end()
            continue
        if part_b_start is None and part_a_end is not None:
            if _PART_B_LINE.match(stripped) or re.match(r"^\s*_?\s*PART\s*[-\s—–ΓÇö]*\s*B", stripped, re.I):
                part_b_start = match.end()
                break

    if part_a_end is not None and part_b_start is not None:
        part_a = text[part_a_end:part_b_start]
        part_b = text[part_b_start:]
    elif part_a_end is not None:
        part_a = text[part_a_end:]

    return part_a, part_b


def _is_junk_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if _JUNK_LINE.match(stripped):
        return True
    if _ANSWER_ANY.match(stripped):
        return True
    if re.match(r"^\(\s*\d+\s*[xX×]", stripped):
        return True
    if re.match(r"^[\W_\-~«»]+$", stripped):
        return True
    if len(stripped) <= 2 and stripped.isdigit():
        return True
    return False


def _flush_part_a(
    items: list[tuple[str, str]],
    current_num: str | None,
    current_lines: list[str],
) -> None:
    if not current_num or not current_lines:
        return
    prompt = _clean_prompt(" ".join(current_lines))
    if len(prompt) >= 12:
        items.append((current_num, prompt))


def _parse_part_a(section: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    current_num: str | None = None
    current_lines: list[str] = []
    expected_next = 1

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if _is_junk_line(line):
            continue

        match = (
            _PART_A_DOT.match(line)
            or _PART_A_NUMBER.match(line)
            or _PART_A_NUMBER_ALT.match(line)
        )
        if match:
            _flush_part_a(items, current_num, current_lines)
            current_num = match.group(1).lstrip("0") or match.group(1)
            current_lines = [match.group(2).strip()]
            try:
                expected_next = int(current_num) + 1
            except ValueError:
                expected_next = 1
            continue

        if _PART_B_SUB.match(line):
            if current_num:
                current_lines.append(line)
            continue

        if _QUESTION_VERB.match(line):
            if current_num is None or (
                expected_next <= 10 and not re.match(r"^\d{1,2}[\.\)]", line)
            ):
                _flush_part_a(items, current_num, current_lines)
                current_num = str(expected_next)
                current_lines = [line]
                expected_next += 1
                continue

        if current_num:
            if re.search(r"\bst condition\b", line, re.I):
                break
            if _PART_B_SUB.match(line) or _PART_B_SUB_ROMAN.match(line):
                current_lines.append(line)
            elif not re.match(r"^[\W~]+$", line):
                current_lines.append(line)

    _flush_part_a(items, current_num, current_lines)

    if len(items) < 3:
        items = _parse_part_a_sequential(section)
    return items


def _parse_part_a_sequential(section: str) -> list[tuple[str, str]]:
    """Fallback: assign 1..N to question-like lines when numbers are missing (OCR)."""
    items: list[tuple[str, str]] = []
    current_lines: list[str] = []
    num = 0

    def flush() -> None:
        nonlocal num, current_lines
        if not current_lines:
            return
        prompt = _clean_prompt(" ".join(current_lines))
        if len(prompt) >= 12 and _QUESTION_VERB.match(prompt):
            num += 1
            items.append((str(num), prompt))
        current_lines = []

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if _is_junk_line(line):
            continue
        if _QUESTION_VERB.match(line) and current_lines:
            flush()
        if _QUESTION_VERB.match(line) or current_lines:
            current_lines.append(line)
    flush()
    return items


def _normalize_part_b_text(section: str) -> str:
    text = section.replace("~", " ")
    text = _expand_orphan_subparts(text)
    # OCR: "2 a)" in Part B usually means Q12.
    text = re.sub(r"(?<!\d)([2-9])\s+([a-c]\))", lambda m: f"1{m.group(1)} {m.group(2)}", text, flags=re.I)
    # OCR: 13.2) / 17.4) -> 13 a) / 17 a)
    text = re.sub(r"(1[0-7])\.\s*([2-9])\)\s", r"\1 a) ", text)
    # OCR: 41.8) garble for 11. a)
    text = re.sub(r"\b41\.8\)\s", "11 a) ", text)
    # OCR: 15a) / 16.(a)
    text = re.sub(r"(1[1-7])\s*\.\s*\(([a-c])\)\s", r"\1 \2) ", text, flags=re.I)
    text = re.sub(r"(1[1-7])([a-c])\)\s", r"\1 \2) ", text, flags=re.I)
    # (@) -> (a)
    text = re.sub(r"\(@\)", "(a)", text)
    text = re.sub(
        r"\(([a-c@])\)",
        lambda m: f"({chr(ord('a')) if m.group(1) == '@' else m.group(1).lower()})",
        text,
    )
    return text


def _expand_orphan_subparts(text: str) -> str:
    """Attach orphan (b) / b) lines to the preceding main question number."""
    lines = text.splitlines()
    result: list[str] = []
    last_main: str | None = None
    for line in lines:
        main_sub = re.match(
            r"^\s*(1[1-7])\s*[\.\)]?\s*(?:\(@\)|\(([a-c@])\)|([a-c])\))\s*(.*)",
            line,
            re.I,
        )
        if main_sub:
            last_main = main_sub.group(1)
            sub_raw = main_sub.group(2) or main_sub.group(3) or "a"
            sub = "a" if sub_raw == "@" else sub_raw.lower()
            result.append(f"{last_main} {sub}) {main_sub.group(4)}")
            continue
        orphan_paren = re.match(r"^\s*\(([a-c@])\)\s*(.+)", line, re.I)
        if orphan_paren and last_main:
            sub = "a" if orphan_paren.group(1) == "@" else orphan_paren.group(1).lower()
            result.append(f"{last_main} {sub}) {orphan_paren.group(2)}")
            continue
        orphan = re.match(r"^\s*([a-c])\)\s*(.+)", line, re.I)
        if orphan and last_main and not re.match(r"^\s*1[0-7]", line):
            result.append(f"{last_main} {orphan.group(1).lower()}) {orphan.group(2)}")
            continue
        result.append(line)
    return "\n".join(result)


def _extract_q17_items(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split Q17 optional block; return trimmed text and 17a/17b/17c items."""
    patterns = [
        r"17\s+Write any two questions:?\s*(.+)$",
        r"17\s+Write short notes on:?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            trimmed = text[: match.start()]
            items: list[tuple[str, str]] = []
            block = match.group(1)
            for sub_match in re.finditer(
                r"(?:^|\n)\s*(?:\(?([a-c])\)?\)|([a-c])\))\s*(.+?)(?=\n\s*(?:\(?[a-c]\)?\)|[a-c]\))\s|\Z)",
                block,
                re.IGNORECASE | re.DOTALL,
            ):
                sub = (sub_match.group(1) or sub_match.group(2)).lower()
                prompt = _clean_prompt(sub_match.group(3))
                if len(prompt) >= 8:
                    items.append((f"17{sub}", prompt))
            if items:
                return trimmed, items
    return text, []


def _parse_part_b_whole_questions(text: str, items: list[tuple[str, str]]) -> None:
    """Capture Part-B questions without a/b subparts (e.g. '11 Explain...')."""
    existing = {qid for qid, _ in items}
    for match in re.finditer(
        r"(?:^|\n)\s*(1[1-7])[\.\)]?\s+(?!a\)|b\)|c\)|\.?\s*[a-c]\))"
        r"((?:Explain|Write|Discuss|Describe|Compare|Prove|Expiain)[^\n]{10,}?)"
        r"(?=\n\s*1[1-7][\.\)]?\s|\n\s*17\s+Write|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        qnum = match.group(1)
        if qnum in existing or any(qid.startswith(qnum) for qid in existing):
            continue
        prompt = _clean_prompt(match.group(2))
        if len(prompt) >= 12 and not _is_bnf_fragment(prompt):
            items.append((qnum, prompt))
            existing.add(qnum)


def _parse_part_b(section: str) -> list[tuple[str, str]]:
    """Return (question_number like '11a', prompt) pairs."""
    text = _normalize_part_b_text(section)
    text, q17_items = _extract_q17_items(text)
    items: list[tuple[str, str]] = list(q17_items)
    last_main: str | None = None

    marker = re.compile(
        r"(?:^|[\s\n])"
        r"(?:"
        r"(1[1-7])\s*[\.\)]?\s*(?:\(?@?\)?\s*)?([a-c])\)|"
        r"(?:^|\n)\s*\(([a-c@])\)\s*|"
        r"(?:^|\n)\s*([a-c])\)\s*"
        r")",
        re.IGNORECASE,
    )
    matches = list(marker.finditer(text))
    for index, match in enumerate(matches):
        if match.group(1):
            last_main = match.group(1)
            sub = match.group(2).lower()
        elif match.group(3):
            sub_raw = match.group(3)
            sub = "a" if sub_raw == "@" else sub_raw.lower()
            if last_main is None:
                continue
        elif match.group(4):
            sub = match.group(4).lower()
            if last_main is None:
                continue
        else:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        prompt = _clean_prompt(text[start:end])
        prompt = re.split(r"\b17\s+Write (?:any two questions|short notes)", prompt, maxsplit=1, flags=re.I)[0]
        if _is_bnf_fragment(prompt) or len(prompt) < 12:
            continue
        qid = f"{last_main}{sub}"
        if not any(existing[0] == qid for existing in items):
            items.append((qid, prompt))

    _parse_part_b_whole_questions(text, items)

    for match in re.finditer(
        r"([A-Za-z][^.\n]{15,}?parameter passing[^.]*\.?)\s+13\s+a\)",
        text,
        re.IGNORECASE,
    ):
        prompt = _clean_prompt(match.group(1))
        if len(prompt) >= 12 and not any(item[0] == "13a" for item in items):
            items.append(("13a", prompt))

    for index, (qid, prompt) in enumerate(items):
        if qid == "15a":
            roman = re.findall(r"\b[ivx]+\)\s*.+", text, re.IGNORECASE)
            if roman:
                extra = _clean_prompt(" ".join(roman))
                if extra and extra not in prompt:
                    items[index] = (qid, _clean_prompt(f"{prompt} {extra}"))

    return items


def _parse_compulsory_page(text: str) -> list[tuple[str, str, str]]:
    """Parse compulsory Q1(a-g) + Q2-7(a/b). Returns (part, qnum, prompt)."""
    items: list[tuple[str, str, str]] = []
    cleaned = strip_watermarks(text)

    q1_match = re.search(
        r"1\.\s*([a-g]\).*?)(?=^\s*2\.\s*[a-c@]\)|\Z)",
        cleaned,
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    if q1_match:
        block = q1_match.group(1)
        for sub_match in re.finditer(
            r"([a-g])\)\s*(.+?)(?=\n\s*[a-g]\)|\Z)",
            block,
            re.IGNORECASE | re.DOTALL,
        ):
            prompt = _clean_prompt(sub_match.group(2))
            if len(prompt) >= 10:
                sub = sub_match.group(1).lower()
                items.append(("C", f"1{sub}", prompt))

    for main in range(2, 8):
        block_match = re.search(
            rf"{main}\.\s*([a-c@]\).*?)(?=^\s*{main + 1}\.|\Z)",
            cleaned,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        if not block_match:
            block_match = re.search(
                rf"{main}\s*,?\s*@?\)\s*(.+?)(?=^\s*{main + 1}\.|\Z)",
                cleaned,
                re.IGNORECASE | re.DOTALL | re.MULTILINE,
            )
        if not block_match:
            continue
        block = block_match.group(0)
        for sub_match in re.finditer(
            r"([a-c@])\)\s*(.+?)(?=\n\s*[a-c@]\)|\Z)",
            block,
            re.IGNORECASE | re.DOTALL,
        ):
            sub_raw = sub_match.group(1)
            sub = "a" if sub_raw == "@" else sub_raw.lower()
            prompt = _clean_prompt(sub_match.group(2))
            if len(prompt) >= 10:
                items.append(("C", f"{main}{sub}", prompt))

    return items


def _map_unit(
    prompt: str,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
) -> tuple[str | None, str | None]:
    if not outline or not patterns:
        return None, None
    match = _best_keyword_match(prompt, patterns)
    if match is None:
        return None, None
    return match[0], match[1]


def _resolve_unit_section(
    prompt: str,
    *,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
    chemistry: bool,
    part: str | None = None,
    question_number: str | None = None,
) -> tuple[str | None, str | None]:
    if chemistry:
        unit, section = map_chemistry_unit_for_question(
            prompt,
            part=part,
            question_number=question_number,
        )
        if unit:
            return unit, section
    return _map_unit(prompt, outline, patterns)


def _parse_part_ab_text_with_label(
    text: str,
    page: int,
    paper_label: str | None,
    *,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
    chemistry: bool,
) -> list[ExamQuestionDraft]:
    part_a_text, part_b_text = _split_parts(text)
    if chemistry and (not part_a_text or not part_b_text):
        loose_a, loose_b = split_parts_loose(text)
        if loose_a or loose_b:
            part_a_text, part_b_text = loose_a, loose_b
    drafts: list[ExamQuestionDraft] = []

    part_a_items = parse_part_a_subparts(part_a_text) if chemistry else []
    if not part_a_items:
        part_a_items = _parse_part_a(part_a_text)

    for num, prompt in part_a_items:
        unit, section = _resolve_unit_section(
            prompt,
            outline=outline,
            patterns=patterns,
            chemistry=chemistry,
            part="A",
            question_number=num,
        )
        drafts.append(
            ExamQuestionDraft(
                page=page,
                paper_label=paper_label,
                part="A",
                question_number=num,
                prompt_text=prompt,
                unit=unit,
                section_title=section,
                confidence=1.0 if num.isdigit() or re.search(r"[a-g]$", num, re.I) else 0.85,
            )
        )

    for num, prompt in _parse_part_b(part_b_text):
        unit, section = _resolve_unit_section(
            prompt,
            outline=outline,
            patterns=patterns,
            chemistry=chemistry,
            part="B",
            question_number=num,
        )
        confidence = 0.9 if re.match(r"^1[1-7][a-c]?$", num, re.I) else 0.75
        drafts.append(
            ExamQuestionDraft(
                page=page,
                paper_label=paper_label,
                part="B",
                question_number=num,
                prompt_text=prompt,
                unit=unit,
                section_title=section,
                confidence=confidence,
            )
        )

    return drafts


def _parse_ou_chemistry_bundle(
    pages: list[PageText],
    *,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
) -> list[ExamQuestionDraft]:
    readable = sorted(
        [page for page in pages if page.char_count >= _READABLE_CHAR_THRESHOLD],
        key=lambda page: page.page,
    )
    if not readable:
        return []

    merged_text = "\n\n".join(page.text for page in readable)
    anchor_page = readable[0].page
    drafts: list[ExamQuestionDraft] = []

    for header, paper_text in _merge_chemistry_sections(split_ou_bundle_text(merged_text)):
        drafts.extend(
            _parse_ou_chemistry_section(
                header=header,
                paper_text=paper_text,
                page=anchor_page,
                outline=outline,
                patterns=patterns,
            )
        )

    return drafts


def _merge_chemistry_sections(sections: list) -> list:
    """Join continuation pages that share an assigned paper code (062c)."""
    merged: list = []
    for header, paper_text in sections:
        if (
            merged
            and header.code
            and merged[-1][0].code == header.code
        ):
            prev_header, prev_text = merged[-1]
            merged[-1] = (prev_header, f"{prev_text}\n\n{paper_text}")
        else:
            merged.append((header, paper_text))
    return merged


def _chemistry_items_to_drafts(
    items: list[tuple[str, str, str]],
    *,
    page: int,
    paper_label: str | None,
    confidence: float,
) -> list[ExamQuestionDraft]:
    drafts: list[ExamQuestionDraft] = []
    for part, num, prompt in items:
        unit, section = map_chemistry_unit_for_question(
            prompt,
            part=part,
            question_number=num,
        )
        drafts.append(
            ExamQuestionDraft(
                page=page,
                paper_label=paper_label,
                part=part,
                question_number=num,
                prompt_text=prompt,
                unit=unit,
                section_title=section,
                confidence=confidence,
            )
        )
    return drafts


def _parse_ou_chemistry_section(
    *,
    header,
    paper_text: str,
    page: int,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
) -> list[ExamQuestionDraft]:
    """Parse one assigned OU paper. Never drop a located paper on detect_format=skip."""
    paper_label = header.paper_label or _detect_paper_label(paper_text)
    fmt = detect_format(paper_text)
    was_skip = fmt == "skip"
    prior = (header.paper_format or "").strip()
    if was_skip:
        fmt = "compulsory_q1" if prior == "New" else "part_ab"

    confidence = 0.69 if was_skip else 0.9
    drafts: list[ExamQuestionDraft] = []

    if fmt == "compulsory_q1":
        items = expand_new_format_questions(paper_text)
        if len(items) < 8:
            fallback = _parse_compulsory_page(paper_text)
            if len(fallback) > len(items):
                items = fallback
        if len(items) < 2:
            items = harvest_numbered_questions(paper_text, paper_format="New")
        drafts = _chemistry_items_to_drafts(
            items, page=page, paper_label=paper_label, confidence=confidence
        )
    elif fmt in {"part_ab", "continuation"}:
        items = expand_old_format_questions(paper_text)
        drafts = _chemistry_items_to_drafts(
            items, page=page, paper_label=paper_label, confidence=confidence
        )
        if len(drafts) < 12:
            legacy = _parse_part_ab_text_with_label(
                paper_text,
                page,
                paper_label,
                outline=outline,
                patterns=patterns,
                chemistry=True,
            )
            if len(legacy) > len(drafts):
                drafts = legacy
        if not drafts:
            items = harvest_numbered_questions(paper_text, paper_format=prior or "Old")
            drafts = _chemistry_items_to_drafts(
                items, page=page, paper_label=paper_label, confidence=confidence
            )

    if was_skip:
        for draft in drafts:
            draft.confidence = min(draft.confidence, 0.69)
    return drafts


def _parse_part_ab_text(
    text: str,
    page: int,
    *,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
) -> list[ExamQuestionDraft]:
    paper_label = _detect_paper_label(text)
    part_a_text, part_b_text = _split_parts(text)
    drafts: list[ExamQuestionDraft] = []

    for num, prompt in _parse_part_a(part_a_text):
        unit, section = _map_unit(prompt, outline, patterns)
        drafts.append(
            ExamQuestionDraft(
                page=page,
                paper_label=paper_label,
                part="A",
                question_number=num,
                prompt_text=prompt,
                unit=unit,
                section_title=section,
                confidence=1.0 if num.isdigit() else 0.85,
            )
        )

    for num, prompt in _parse_part_b(part_b_text):
        unit, section = _map_unit(prompt, outline, patterns)
        confidence = 0.9 if re.match(r"^1[1-7][a-c]?$", num) else 0.75
        drafts.append(
            ExamQuestionDraft(
                page=page,
                paper_label=paper_label,
                part="B",
                question_number=num,
                prompt_text=prompt,
                unit=unit,
                section_title=section,
                confidence=confidence,
            )
        )

    return drafts


def _parse_merged_text(
    text: str,
    anchor_page: int,
    *,
    outline: DocumentOutline | None,
    patterns: list[tuple[str, str, list[str]]] | None,
) -> list[ExamQuestionDraft]:
    fmt = detect_format(text)
    if fmt == "compulsory_q1":
        paper_label = _detect_paper_label(text)
        drafts: list[ExamQuestionDraft] = []
        for part, num, prompt in _parse_compulsory_page(text):
            unit, section = _map_unit(prompt, outline, patterns)
            drafts.append(
                ExamQuestionDraft(
                    page=anchor_page,
                    paper_label=paper_label,
                    part=part,
                    question_number=num,
                    prompt_text=prompt,
                    unit=unit,
                    section_title=section,
                    confidence=0.88,
                )
            )
        return drafts

    if fmt in {"part_ab", "continuation"}:
        return _parse_part_ab_text(text, anchor_page, outline=outline, patterns=patterns)

    return []


def _group_pages(pages: list[PageText]) -> list[list[PageText]]:
    """Group readable pages; continuation pages merge into prior group."""
    readable = sorted(
        [p for p in pages if p.char_count >= _READABLE_CHAR_THRESHOLD],
        key=lambda p: p.page,
    )
    groups: list[list[PageText]] = []
    current: list[PageText] = []

    for page in readable:
        fmt = detect_format(page.text)
        if fmt == "skip":
            continue
        if fmt == "continuation" and current:
            current.append(page)
        else:
            if current:
                groups.append(current)
            current = [page]
    if current:
        groups.append(current)
    return groups


def parse_exam_questions_from_pages(
    *,
    pages: list[PageText],
    document_id: uuid.UUID,
    course_id: str,
    filename: str,
    outline: DocumentOutline | None = None,
) -> list[ExamQuestionDraft]:
    """Parse structured exam questions from readable past_paper pages."""
    del document_id  # reserved for future multi-doc routing
    patterns = _build_keyword_patterns(outline) if outline else None
    sample_text = pages[0].text if pages else ""

    if is_ou_chemistry_source(course_id=course_id, filename=filename, sample_text=sample_text):
        ou_drafts = _parse_ou_chemistry_bundle(pages, outline=outline, patterns=patterns)
        if ou_drafts:
            logger.info(
                "Parsed %d OU chemistry exam question(s) from bundled document %s",
                len(ou_drafts),
                filename,
            )
            return ou_drafts

    drafts: list[ExamQuestionDraft] = []
    pages_hit: set[int] = set()

    for group in _group_pages(pages):
        merged_text = "\n\n".join(p.text for p in group)
        anchor_page = group[0].page
        page_drafts = _parse_merged_text(
            merged_text,
            anchor_page,
            outline=outline,
            patterns=patterns,
        )
        if page_drafts:
            pages_hit.add(anchor_page)
            for p in group[1:]:
                pages_hit.add(p.page)
        drafts.extend(page_drafts)

    logger.info(
        "Parsed %d exam question(s) from %d page group(s) (%d pages hit)",
        len(drafts),
        len(_group_pages(pages)),
        len(pages_hit),
    )
    return drafts
