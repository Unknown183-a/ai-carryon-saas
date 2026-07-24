"""
Backfill (Phase 5 task): embed and load a handful of past scripts and
research summaries from the *old* pipeline into Qdrant's `scripts` and
`research` collections, so retrieval has something to find on day one
instead of starting completely cold.

This project's old pipeline (the pre-SaaS "AI CarryON" repo — a single
SQLite database, partitioned by channel) isn't reachable from this
environment, so this script reads from a plain JSON export instead of
querying that SQLite DB directly. Point `--seed-file` at a real export
when running this for real; `ai/rag/seed_data/sample_backfill.json`
ships a small illustrative example (3 scripts, 2 research summaries) in
the exact shape this script expects, so the wiring can be verified
end-to-end without needing that export on hand yet.

JSON shape expected:
{
  "scripts": [
    {"channel_id": "...", "video_id": "...", "text": "...", "views": 12345}
  ],
  "research": [
    {"channel_id": "...", "topic": "...", "text": "...", "source_urls": [...], "date": "YYYY-MM-DD"}
  ]
}

Run with:
    python -m ai.rag.backfill --seed-file ai/rag/seed_data/sample_backfill.json
(from backend/, with PYTHONPATH set the same way as the phase test scripts)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from ai.rag.retriever import store_chunks


def backfill_scripts(entries: list[dict]) -> int:
    total = 0
    for entry in entries:
        total += store_chunks(
            "scripts",
            entry["text"],
            metadata={
                "channel_id": entry["channel_id"],
                "video_id": entry.get("video_id", "unknown"),
                "views": entry.get("views", 0),
            },
        )
    return total


def backfill_research(entries: list[dict]) -> int:
    total = 0
    for entry in entries:
        total += store_chunks(
            "research",
            entry["text"],
            metadata={
                "channel_id": entry["channel_id"],
                "topic": entry["topic"],
                "source_urls": entry.get("source_urls", []),
                "date": entry.get("date", "unknown"),
            },
        )
    return total


def run_backfill(seed_file: str) -> dict[str, int]:
    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scripts_written = backfill_scripts(data.get("scripts", []))
    research_written = backfill_research(data.get("research", []))
    return {"scripts_chunks_written": scripts_written, "research_chunks_written": research_written}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-file",
        default=os.path.join(os.path.dirname(__file__), "seed_data", "sample_backfill.json"),
        help="Path to a JSON export in the shape documented at the top of this file.",
    )
    args = parser.parse_args()

    result = run_backfill(args.seed_file)
    print(f"Backfill complete: {result}")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    main()
