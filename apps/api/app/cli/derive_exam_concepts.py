"""CLI: python -m app.cli.derive_exam_concepts --course PPL"""

from __future__ import annotations

import argparse
import json

from app.database import SessionLocal
from app.services.exam.concept_derive import derive_exam_concepts_for_course


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive exam concepts for a course from parsed PYQs")
    parser.add_argument("--course", required=True, help="Course id, e.g. PPL")
    args = parser.parse_args()

    with SessionLocal() as session:
        stats = derive_exam_concepts_for_course(session, args.course)
        session.commit()
        payload = {
            "course_id": stats.course_id,
            "question_count": stats.question_count,
            "concept_count": stats.concept_count,
            "classified_concept_count": stats.classified_concept_count,
            "alias_count": stats.alias_count,
            "linked_questions": stats.linked_questions,
            "unclassified_only_questions": stats.unclassified_only_questions,
            "unclassified_pct": stats.unclassified_pct,
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
