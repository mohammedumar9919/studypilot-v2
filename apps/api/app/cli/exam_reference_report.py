"""CLI: python -m app.cli.exam_reference_report --validate --course chemistry"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.exam.reference_report import (
    collect_app_metrics,
    format_validation_report,
    load_golden_reference,
    validate_against_golden,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare exam metrics to chemistry golden reference")
    parser.add_argument("--course", default="chemistry", help="Course id (default: chemistry)")
    parser.add_argument("--validate", action="store_true", help="Diff app DB vs golden reference")
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Path to CHEMISTRY_GOLDEN_REFERENCE.json",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    args = parser.parse_args()

    golden = load_golden_reference(args.golden)

    with SessionLocal() as session:
        if args.validate:
            result = validate_against_golden(
                session,
                args.course,
                golden=golden,
                golden_path=args.golden,
            )
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(format_validation_report(result))
            if not result["passed"]:
                sys.exit(1)
            return

        metrics = collect_app_metrics(session, args.course)
        payload = {"course_id": args.course, "metrics": metrics, "golden_meta": golden["meta"]}
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
