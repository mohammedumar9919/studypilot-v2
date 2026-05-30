"""
Replay golden-set questions against the retrieval pipeline (no LLM).

Writes eval/reports/latest.jsonl for score_precision.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "eval" / "golden_set.jsonl"
REPORT_DIR = REPO_ROOT / "eval" / "reports"


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> int:
    if not GOLDEN_PATH.exists():
        print(f"Missing golden set: {GOLDEN_PATH}", file=sys.stderr)
        return 1

    golden = load_golden(GOLDEN_PATH)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
    try:
        from app.services.rag.retrieve import replay_golden_set  # type: ignore

        results = replay_golden_set(golden)
    except Exception as exc:
        print(f"Retrieval replay failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    out_path = REPORT_DIR / "latest.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")

    categories: dict[str, int] = {}
    for row in golden:
        cat = row.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    print(f"Golden set: {len(golden)} questions")
    print(f"Categories: {categories}")
    print(f"Report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
