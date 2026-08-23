"""CLI: python -m app.cli.exam_analytics --course PPL"""

from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.services.exam.analytics import compute_exam_analytics_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Print exam concept analytics JSON for a course")
    parser.add_argument("--course", required=True, help="Course id, e.g. PPL")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sort", default="weightage_desc")
    parser.add_argument("--include-unclassified", action="store_true")
    parser.add_argument("--min-questions", type=int, default=1)
    parser.add_argument(
        "--include-structure",
        default="auto",
        choices=["auto", "true", "false"],
        help="Tier 3 structure block (default: auto)",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        print(
            compute_exam_analytics_json(
                session,
                args.course,
                limit=args.limit,
                offset=args.offset,
                sort=args.sort,
                include_unclassified=args.include_unclassified,
                min_questions=args.min_questions,
                include_structure=args.include_structure,
            )
        )


if __name__ == "__main__":
    main()
