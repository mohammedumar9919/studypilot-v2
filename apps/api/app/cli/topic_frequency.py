"""CLI: python -m app.cli.topic_frequency --course PPL"""

from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.services.exam.topic_frequency import compute_topic_frequency_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Print PYQ topic frequency JSON for a course")
    parser.add_argument("--course", required=True, help="Course id, e.g. PPL")
    args = parser.parse_args()

    with SessionLocal() as session:
        print(compute_topic_frequency_json(session, args.course))


if __name__ == "__main__":
    main()
