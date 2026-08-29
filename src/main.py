"""
Orchestrator: for every source in config/sources.yaml,
  1. fetch current content
  2. compare against the latest stored snapshot
  3. if changed (and non-trivial), diff + classify + store

Run manually:
    python -m src.main

Run for a single source (useful while debugging one source's scraping):
    python -m src.main --source nist_ai_rmf

This is also what the GitHub Actions workflow calls on a schedule.
"""

from __future__ import annotations

import argparse
import sys

import yaml
from pathlib import Path
from dotenv import load_dotenv

from . import storage, ingest, diff_detect, classify

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"

# Load ANTHROPIC_API_KEY (and any other secrets) from a local .env file if
# present. Safe to call even if .env doesn't exist — it just no-ops.
load_dotenv()


def load_sources() -> list[dict]:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    all_sources = config["sources"]
    return [s for s in all_sources if s.get("active", True)]


def process_source(conn, source: dict, skip_classification_flag: bool = False) -> None:
    # A source can opt out of classification permanently (e.g. terms-of-use
    # restrictions on feeding content to AI/ML systems) via its config entry,
    # independent of the --skip-classification CLI flag used for local testing.
    skip_classification = skip_classification_flag or source.get("skip_classification", False)
    print(f"[{source['id']}] fetching...")
    try:
        result = ingest.fetch_source(source)
    except Exception as e:
        print(f"[{source['id']}] FETCH FAILED: {e}", file=sys.stderr)
        return

    prev = storage.get_latest_snapshot(conn, source["id"])

    if prev and not diff_detect.has_changed(prev.content_hash, result.content_hash):
        print(f"[{source['id']}] no change")
        return

    new_snapshot = storage.Snapshot(
        id=None,
        source_id=source["id"],
        fetched_at=storage.now_iso(),
        content_hash=result.content_hash,
        raw_text=result.raw_text,
    )
    new_snapshot_id = storage.insert_snapshot(conn, new_snapshot)

    if prev is None:
        print(f"[{source['id']}] first snapshot recorded, nothing to diff against")
        return

    diff_text = diff_detect.build_diff(prev.raw_text, result.raw_text)

    if diff_detect.diff_is_trivial(diff_text):
        print(f"[{source['id']}] change detected but trivial, skipping classification")
        return

    print(f"[{source['id']}] change detected, classifying...")

    change = storage.ChangeRecord(
        id=None,
        source_id=source["id"],
        detected_at=storage.now_iso(),
        prev_snapshot_id=prev.id,
        new_snapshot_id=new_snapshot_id,
        diff_text=diff_text,
    )

    if not skip_classification:
        try:
            result_cls = classify.classify_diff(source["name"], diff_text)
            change.change_summary = result_cls.change_summary
            change.ai_relevant = result_cls.ai_relevant
            change.ai_relevance_category = result_cls.ai_relevance_category
            change.confidence = result_cls.confidence
            change.reasoning = result_cls.reasoning
        except Exception as e:
            print(f"[{source['id']}] CLASSIFICATION FAILED: {e}", file=sys.stderr)
    else:
        change.change_summary = "Classification skipped for this source (see config/sources.yaml notes) — flagged for manual review."

    storage.insert_change(conn, change)
    print(f"[{source['id']}] change recorded (ai_relevant={change.ai_relevant})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Only process this source id")
    parser.add_argument(
        "--skip-classification",
        action="store_true",
        help="Skip the Claude API call (useful for testing ingestion/diffing without API costs)",
    )
    args = parser.parse_args()

    storage.init_db()
    sources = load_sources()

    if args.source:
        sources = [s for s in sources if s["id"] == args.source]
        if not sources:
            print(f"No source with id '{args.source}' in config", file=sys.stderr)
            sys.exit(1)

    with storage.get_conn() as conn:
        for source in sources:
            storage.upsert_source(conn, source)

        for source in sources:
            process_source(conn, source, skip_classification_flag=args.skip_classification)


if __name__ == "__main__":
    main()
