from __future__ import annotations

from dataclasses import dataclass

from app.services.chunker.base import DOC_KIND_SPECS, estimate_tokens, _split_text
from app.services.pdf_extract import PageText


@dataclass
class ParentChunk:
    page_start: int
    page_end: int
    text: str
    metadata: dict


@dataclass
class ChildChunk:
    parent_index: int
    chunk_index: int
    page: int
    text: str
    token_count: int
    metadata: dict


@dataclass
class ChunkingResult:
    parents: list[ParentChunk]
    children: list[ChildChunk]


def _strip_header(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip().upper() != "MJCET"]
    return "\n".join(lines).strip()


def _page_metadata(page: PageText) -> dict:
    return dict(page.metadata or {})


def _merge_metadata(*parts: dict, doc_kind: str) -> dict:
    merged: dict = {"doc_kind": doc_kind}
    for part in parts:
        for key, value in part.items():
            if value is not None:
                merged[key] = value
    return merged


def _group_pages_for_parents(pages: list[PageText], parent_tokens: int) -> list[list[PageText]]:
    """Token-budget grouping only. Outline unit/section metadata lives on pages/chunks for retrieval."""
    groups: list[list[PageText]] = []
    current: list[PageText] = []
    current_tokens = 0

    for page in pages:
        page_tokens = estimate_tokens(page.text)
        if current and current_tokens + page_tokens > parent_tokens:
            groups.append(current)
            current = [page]
            current_tokens = page_tokens
        else:
            current.append(page)
            current_tokens += page_tokens

    if current:
        groups.append(current)
    return groups


def chunk_pages(pages: list[PageText], doc_kind: str) -> ChunkingResult:
    spec = DOC_KIND_SPECS.get(doc_kind, DOC_KIND_SPECS["notes"])
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []

    nonempty = [p for p in pages if p.char_count > 0]
    if not nonempty:
        return ChunkingResult(parents=[], children=[])

    if doc_kind == "past_paper":
        for page in nonempty:
            text = _strip_header(page.text)
            page_md = _page_metadata(page)
            parents.append(
                ParentChunk(
                    page_start=page.page,
                    page_end=page.page,
                    text=text,
                    metadata=_merge_metadata(page_md, doc_kind=doc_kind),
                )
            )
            parent_index = len(parents) - 1
            for idx, piece in enumerate(_split_text(text, spec.child_tokens, spec.overlap_ratio)):
                children.append(
                    ChildChunk(
                        parent_index=parent_index,
                        chunk_index=idx,
                        page=page.page,
                        text=piece,
                        token_count=estimate_tokens(piece),
                        metadata=_merge_metadata(page_md, doc_kind=doc_kind),
                    )
                )
        return ChunkingResult(parents=parents, children=children)

    groups = _group_pages_for_parents(nonempty, spec.parent_tokens)

    for group in groups:
        combined = "\n\n".join(_strip_header(p.text) for p in group)
        lead_md = _page_metadata(group[0])
        parents.append(
            ParentChunk(
                page_start=group[0].page,
                page_end=group[-1].page,
                text=combined,
                metadata=_merge_metadata(lead_md, doc_kind=doc_kind),
            )
        )
        parent_index = len(parents) - 1
        for idx, piece in enumerate(_split_text(combined, spec.child_tokens, spec.overlap_ratio)):
            page = group[min(idx, len(group) - 1)]
            page_md = _page_metadata(page)
            children.append(
                ChildChunk(
                    parent_index=parent_index,
                    chunk_index=idx,
                    page=page.page,
                    text=piece,
                    token_count=estimate_tokens(piece),
                    metadata=_merge_metadata(page_md, doc_kind=doc_kind),
                )
            )

    return ChunkingResult(parents=parents, children=children)
