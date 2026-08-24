"""CLI: python -m app.cli.exam_parse_audit --course chemistry|PPL"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.exam.parse_audit import REPO_ROOT, audit_course, write_audit_report
from app.services.exam.reference_report import resolve_golden_path

_REPORT_DEFAULTS: dict[str, Path] = {
    "chemistry": REPO_ROOT / "docs" / "reports" / "CHEMISTRY_PARSE_AUDIT.md",
    "ppl": REPO_ROOT / "docs" / "reports" / "PPL_PARSE_AUDIT.md",
}


def _default_report_path(course_id: str) -> Path:
    key = course_id.strip().lower()
    if key in _REPORT_DEFAULTS:
        return _REPORT_DEFAULTS[key]
    return REPO_ROOT / "docs" / "reports" / f"{course_id.strip().upper()}_PARSE_AUDIT.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Forensic audit of exam parse vs golden reference (SP-062a/064e)")
    parser.add_argument("--course", default="chemistry", help="Course id (chemistry, PPL, …)")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Markdown report path (default: docs/reports/{COURSE}_PARSE_AUDIT.md)",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Override golden reference JSON path",
    )
    args = parser.parse_args()

    golden_path = args.golden or resolve_golden_path(args.course)
    if golden_path is None:
        print(f"No golden reference found for course={args.course!r}", file=sys.stderr)
        sys.exit(2)

    with SessionLocal() as session:
        result = audit_course(session, args.course, golden_path=golden_path)

    report_path = write_audit_report(result, args.output or _default_report_path(args.course))
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
