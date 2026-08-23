"""CLI: python -m app.cli.exam_parse_audit --course chemistry"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.exam.parse_audit import (
    DEFAULT_REPORT_PATH,
    audit_course,
    write_audit_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Forensic audit of chemistry exam parse (SP-062a)")
    parser.add_argument("--course", default="chemistry", help="Course id (default: chemistry)")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report path (default: docs/reports/CHEMISTRY_PARSE_AUDIT.md)",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Path to CHEMISTRY_GOLDEN_REFERENCE.json",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        result = audit_course(session, args.course, golden_path=args.golden)

    report_path = write_audit_report(result, args.output)
    print(
        f"course={result.course_id} db_rows={result.db_question_rows} "
        f"replay_drafts={result.replay_draft_rows} "
        f"papers_found={len(result.papers_found)} "
        f"papers_missing={len(result.papers_missing)}"
    )
    print(f"report={report_path}")
    for reason, count in result.drop_counts.items():
        print(f"  drop_{reason}={count}")
    if result.papers_missing:
        print("missing_codes=" + ",".join(result.papers_missing))
    sys.exit(0)


if __name__ == "__main__":
    main()
