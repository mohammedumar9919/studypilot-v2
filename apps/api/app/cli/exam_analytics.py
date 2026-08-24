"""CLI: python -m app.cli.exam_analytics --course PPL"""

from __future__ import annotations

import argparse
import json

from app.database import SessionLocal
from app.services.exam.analytics import compute_exam_analytics


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
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print predictions summary instead of full JSON",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        payload = compute_exam_analytics(
            session,
            args.course,
            limit=args.limit,
            offset=args.offset,
            sort=args.sort,
            include_unclassified=args.include_unclassified,
            min_questions=args.min_questions,
            include_structure=args.include_structure,
        )

    if args.summary_only:
        predictions = payload.get("predictions") or {}
        items = predictions.get("items") or []
        print(
            f"course={payload.get('course_id')} ready={payload.get('analytics_ready')} "
            f"formula={predictions.get('formula_version')} top_n={predictions.get('top_n')} "
            f"predicted={len(items)}"
        )
        for item in items[:10]:
            reasons = ",".join(item.get("reasons") or []) or "-"
            print(
                f"  #{item.get('rank')} {item.get('label')} "
                f"score={item.get('score')} reasons={reasons}"
            )
        return

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
