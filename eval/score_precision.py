"""Score retrieval replay output against golden_set.jsonl."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def page_hit(expected_pages: list[int], retrieved_pages: list[int], tolerance: int = 1) -> bool:
    if not expected_pages:
        return False
    expanded = {p + d for p in expected_pages for d in range(-tolerance, tolerance + 1)}
    return any(p in expanded for p in retrieved_pages)


def score(golden: list[dict], results: list[dict]) -> dict:
    by_id = {r["id"]: r for r in results}
    in_corpus = [g for g in golden if g.get("category") != "out_of_corpus"]
    ooc = [g for g in golden if g.get("category") == "out_of_corpus"]

    hits = 0
    misses: list[str] = []
    for g in in_corpus:
        r = by_id.get(g["id"])
        if not r:
            misses.append(g["id"])
            continue
        pages = r.get("retrieved_pages", [])
        if page_hit(g.get("expected_pages", []), pages):
            hits += 1
        else:
            misses.append(g["id"])

    ooc_hits = 0
    ooc_misses: list[str] = []
    for g in ooc:
        r = by_id.get(g["id"], {})
        if r.get("status") == "not_in_materials":
            ooc_hits += 1
        else:
            ooc_misses.append(g["id"])

    n = len(in_corpus) or 1
    return {
        "precision_at_5": hits / n,
        "hits": hits,
        "total_in_corpus": len(in_corpus),
        "misses": misses,
        "ooc_refusal_rate": ooc_hits / (len(ooc) or 1),
        "ooc_hits": ooc_hits,
        "ooc_total": len(ooc),
        "ooc_misses": ooc_misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden_path", type=Path)
    parser.add_argument("results_path", type=Path)
    args = parser.parse_args()

    golden = load_jsonl(args.golden_path)
    results = load_jsonl(args.results_path)
    report = score(golden, results)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
