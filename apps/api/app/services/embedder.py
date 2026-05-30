from __future__ import annotations

from functools import lru_cache

from fastembed import TextEmbedding

from app.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> TextEmbedding:
    return TextEmbedding(model_name=settings.embedding_model)


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    if not texts:
        return []
    prefix = "Represent this sentence for searching relevant passages: " if is_query else ""
    inputs = [prefix + t for t in texts]
    return [list(vec) for vec in get_embedder().embed(inputs)]
