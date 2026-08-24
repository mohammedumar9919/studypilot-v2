"""CLI: python -m app.cli.exam_reference_report --validate --course <id>"""

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
    resolve_golden_path,
    validate_against_golden,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare exam metrics to per-subject golden reference (SP-064c)",
    )
    parser.add_argument("--course", default="chemistry", help="Course id (default: chemistry)")
    parser.add_argument("--validate", action="store_true", help="Diff app DB vs golden reference")
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Override path to {COURSE}_GOLDEN_REFERENCE.json",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of table")
    args = parser.parse_args()

    golden_path = resolve_golden_path(args.course, override=args.golden)

    with SessionLocal() as session:
        if args.validate:
            try:
                result = validate_against_golden(
                    session,
                    args.course,
                    golden_path=golden_path or args.golden,
                )
            except FileNotFoundError as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(2)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(format_validation_report(result))
            if not result["passed"]:
                sys.exit(1)
            return

        if golden_path is None:
            print(
                f"No golden reference found for course={args.course!r}. "
                "Add docs/reports/{COURSE}_GOLDEN_REFERENCE.json or use --golden.",
                file=sys.stderr,
            )
            sys.exit(2)

        golden = load_golden_reference(golden_path)
        metrics = collect_app_metrics(session, args.course)
        payload = {
            "course_id": args.course,
            "golden_path": str(golden_path),
            "metrics": metrics,
            "golden_meta": golden["meta"],
        }
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
