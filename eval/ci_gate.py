"""CI eval gate — score replay output and exit non-zero if below thresholds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "eval"))

from score_precision import load_jsonl, score  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail CI if retrieval metrics below thresholds.")
    parser.add_argument(
        "--golden",
        type=Path,
        default=REPO_ROOT / "eval" / "golden_set.jsonl",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=REPO_ROOT / "eval" / "reports" / "latest.jsonl",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=float(__import__("os").environ.get("EVAL_PRECISION_MIN", "1.0")),
        help="Minimum precision@5 (default 1.0 / 100%%)",
    )
    parser.add_argument(
        "--min-ooc",
        type=float,
        default=float(__import__("os").environ.get("EVAL_OOC_MIN", "1.0")),
        help="Minimum OOC refusal rate (default 1.0 = 10/10)",
    )
    parser.add_argument(
        "--match-results",
        action="store_true",
        help="Score only golden rows present in results (for GOLDEN_LIMIT smoke runs)",
    )
    args = parser.parse_args()

    if not args.golden.exists():
        print(f"Missing golden set: {args.golden}", file=sys.stderr)
        return 1
    if not args.results.exists():
        print(f"Missing replay results: {args.results}", file=sys.stderr)
        return 1

    golden = load_jsonl(args.golden)
    results = load_jsonl(args.results)
    if args.match_results:
        replayed_ids = {r["id"] for r in results}
        golden = [g for g in golden if g["id"] in replayed_ids]
        print(f"Scoring {len(golden)} replayed questions (match-results mode)")

    report = score(golden, results)
    precision = report["precision_at_5"]
    ooc = report["ooc_refusal_rate"]

    print(json.dumps(report, indent=2))

    passed = precision >= args.min_precision and ooc >= args.min_ooc
    if passed:
        print(
            f"CI GATE PASS: precision@5={precision:.4f} (>={args.min_precision}), "
            f"OOC={report['ooc_hits']}/{report['ooc_total']} (>={args.min_ooc})"
        )
        return 0

    print(
        f"CI GATE FAIL: precision@5={precision:.4f} (need >={args.min_precision}), "
        f"OOC={report['ooc_hits']}/{report['ooc_total']} (need >={args.min_ooc}), "
        f"misses={report.get('misses', [])}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

