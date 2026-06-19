# Do-not-repeat checklist (from cursortest audit)

## RAG (SEV-1)
- No vector search without HNSW index
- No vector-only retrieval — hybrid RRF + rerank + gate required
- No past_paper in Study mode retrieval
- No feature work before golden-set precision@5 >= 70%
- Hierarchical parent-child chunks required

## Ingest
- Single PDF extract path (PyMuPDF sort + column clip + OCR fallback)
- Idempotent re-ingest (delete old chunks before re-index)
- Local FastEmbed only — no OpenRouter embeddings
- Flag extraction_quality per document

## Security / process
- Workspace ownership on all course routes (SP-012 Phase B)
- No query-time exam LLM JSON extract; ingest-time PYQ structure requires schema validation + idempotent re-ingest
- No sanitizer ladder — confidence gate instead
- pytest DB credentials must match docker-compose
