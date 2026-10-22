"""Exercise project 04's real cleaning, model summary, SQLite and vault pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from .agents import COURSE_ROOT
from pipeline.analysis_service import analyze_file
from pipeline import research_intelligence as store


async def run(corpus: Path, output: Path) -> dict:
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Collect the public corpus first")
    destination = COURSE_ROOT / "data/github/jsonl/course04_source_tracking_contents.jsonl"
    expected_input = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in [*rows, rows[0], {}])
    if destination.exists() and destination.read_text(encoding="utf-8") != expected_input:
        raise FileExistsError("Demo input contains other content; preserve it before continuing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Include one duplicate and one empty row to verify the real cleanup path.
    destination.write_text(expected_input, encoding="utf-8")
    academic = COURSE_ROOT / "knowledge/academic"
    social = COURSE_ROOT / "knowledge/social"
    (academic / "30-来源/自动采集").mkdir(parents=True, exist_ok=True)
    social.mkdir(parents=True, exist_ok=True)
    os.environ["OBSIDIAN_ACADEMIC_VAULT_PATH"] = str(academic)
    os.environ["OBSIDIAN_SOCIAL_VAULT_PATH"] = str(social)
    os.environ["OBSIDIAN_VAULT_PATH"] = str(academic)
    if not os.getenv("AI_API_KEY") and os.getenv("OPENAI_API_KEY"):
        os.environ["AI_API_KEY"] = os.environ["OPENAI_API_KEY"]
        os.environ["AI_BASE_URL"] = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    os.environ["AI_BATCH_SIZE"] = "10"
    meta = await analyze_file(str(destination.relative_to(COURSE_ROOT / "data")))
    with store._connect() as connection:
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("documents", "analyses", "evidence", "analysis_runs")}
    archive = list(academic.rglob("*.md"))
    summaries = meta["batch_summaries"]
    summary = {
        "input_count": meta["input_count"], "output_count": meta["output_count"],
        "scope_excluded": meta["scope_excluded"], "ai_enabled": meta["ai_enabled"],
        "source_file": str(destination.relative_to(COURSE_ROOT)),
        "output_file": "data/" + meta["output_file"], "database_counts": counts,
        "academic_notes": len(archive),
        "archive_contains_source_link": any(rows[0]["url"] in note.read_text(encoding="utf-8") for note in archive),
        "batches": [{"batch": batch["batch"], "record_count": batch["record_count"],
                     "verification": batch.get("verification"), "citation_count": len(batch.get("citations", []))}
                    for batch in summaries],
    }
    if not summary["output_count"] or not archive or not summary["archive_contains_source_link"]:
        raise RuntimeError("End-to-end archive verification failed")
    if summary["ai_enabled"] and not any(batch.get("verification", {}).get("status") == "source-matched" for batch in summaries):
        raise RuntimeError("No model summary passed original-source matching")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.corpus, args.output)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
