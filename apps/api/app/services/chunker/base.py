from dataclasses import dataclass


@dataclass
class ChunkSpec:
    child_tokens: int
    parent_tokens: int
    overlap_ratio: float


DOC_KIND_SPECS: dict[str, ChunkSpec] = {
    "notes": ChunkSpec(child_tokens=700, parent_tokens=1350, overlap_ratio=0.12),
    "textbook": ChunkSpec(child_tokens=800, parent_tokens=1750, overlap_ratio=0.12),
    "syllabus": ChunkSpec(child_tokens=500, parent_tokens=900, overlap_ratio=0.10),
    "past_paper": ChunkSpec(child_tokens=400, parent_tokens=800, overlap_ratio=0.12),
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _split_text(text: str, max_tokens: int, overlap_ratio: float) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= max_tokens:
        return [text.strip()]

    overlap = max(1, int(max_tokens * overlap_ratio))
    step = max(1, max_tokens - overlap)
    chunks: list[str] = []
    start = 0
    while start < len(words):
        piece = words[start : start + max_tokens]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if start + max_tokens >= len(words):
            break
        start += step
    return chunks
