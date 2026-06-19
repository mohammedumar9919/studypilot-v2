"""One-off: remove non-PPL documents wrongly ingested under the PPL course.

Root cause of OOC 8/10 gate failure: `engineering chemistry updated.pdf` was
ingested under course_id=PPL, so out-of-corpus chemistry/physics questions
(ppl-ooc-04 Faraday, ppl-ooc-06 Maxwell) retrieved chemistry pages instead of
refusing. The chemistry course keeps its own copy; this only prunes PPL.

Run from apps/api with the MAIN db:
    $env:DATABASE_URL = "postgresql+psycopg://studypilot:studypilot@localhost:5433/studypilot"
    python -m scripts.cleanup_ppl_corpus
"""

from __future__ import annotations

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Document
from app.services.ingestion import _delete_document_chunks

# Canonical PPL corpus — anything else under course_id=PPL is pollution.
ALLOWED_PPL_FILENAMES = {"PPL notes.pdf", "PPL previous papers.pdf"}


def main() -> None:
    with SessionLocal() as session:
        ppl_docs = list(
            session.scalars(select(Document).where(Document.course_id == "PPL")).all()
        )
        removed = []
        for doc in ppl_docs:
            if doc.filename in ALLOWED_PPL_FILENAMES:
                continue
            _delete_document_chunks(session, doc.id)
            session.delete(doc)
            removed.append(doc.filename)
        session.commit()

        if removed:
            print(f"Removed from PPL course: {removed}")
        else:
            print("PPL corpus already clean — no documents removed.")

        remaining = list(
            session.scalars(
                select(Document.filename).where(Document.course_id == "PPL")
            ).all()
        )
        print(f"PPL documents now: {sorted(remaining)}")


if __name__ == "__main__":
    main()
