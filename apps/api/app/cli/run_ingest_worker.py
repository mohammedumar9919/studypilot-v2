"""CLI: python -m app.cli.run_ingest_worker [--once]"""

from __future__ import annotations

import argparse
import time

from app.database import SessionLocal
from app.models import IngestJob
from app.services.ingest_queue import claim_next_job, process_claimed_job


def run_once(phase_filter: str | None = None) -> bool:
    """Claim and process one queued job. phase_filter restricts to fast|heavy|full."""
    with SessionLocal() as session:
        job = claim_next_job(session, phase_filter=phase_filter)
        if job is None:
            session.commit()
            return False
        job_id = job.id
        document_id = job.document_id
        phase = job.phase
        session.commit()

    with SessionLocal() as session:
        job = session.get(IngestJob, job_id)
        if job is None:
            return True
        document = process_claimed_job(session, job)
        print(
            f"[{phase}] Processed job {job_id} document={document_id}: "
            f"status={document.status}, pages={document.page_count}"
        )
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="StudyPilot ingest queue worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job then exit",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between polls when running continuously (default: 2)",
    )
    parser.add_argument(
        "--phase",
        choices=["fast", "heavy", "full"],
        default=None,
        help="Only process jobs of this phase (default: all phases)",
    )
    args = parser.parse_args()

    if args.once:
        processed = run_once(phase_filter=args.phase)
        if not processed:
            label = f"{args.phase}-phase " if args.phase else ""
            print(f"No queued {label}ingest jobs")
        return

    phase_label = f" (phase={args.phase})" if args.phase else ""
    print(f"Ingest worker running{phase_label} (Ctrl+C to stop)")
    while True:
        if not run_once(phase_filter=args.phase):
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
