"""CLI: python -m app.cli.ingest path/to.pdf --course PPL --kind notes"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.database import SessionLocal
from app.services.ingestion import ingest_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a PDF into StudyPilot")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--course", required=True, help="Course id, e.g. PPL")
    parser.add_argument("--kind", required=True, choices=["notes", "textbook", "syllabus", "past_paper"])
    parser.add_argument("--name", default=None, help="Optional course display name")
    args = parser.parse_args()

    with SessionLocal() as session:
        doc = ingest_document(
            session,
            file_path=args.pdf_path,
            course_id=args.course,
            doc_kind=args.kind,
            course_name=args.name,
        )
        print(f"Ingested {doc.filename}: status={doc.status}, pages={doc.page_count}")
        if doc.extraction_quality:
            print(f"  extraction_quality={doc.extraction_quality}")
        if doc.error_message:
            print(f"  error={doc.error_message}")


if __name__ == "__main__":
    main()
