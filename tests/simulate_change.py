"""
Simulate a source change for demo/testing purposes.

Why this exists: regulatory pages don't change on a convenient schedule.
This script lets you prove the full pipeline (diff -> classify -> store ->
dashboard) works end-to-end without waiting on a real-world update, by
taking the most recent real snapshot for a source, injecting a synthetic
change into a copy of it, and feeding both through the normal diff +
classify + store path — the exact same code path a real change would use.

This is a test fixture, not a way to fake data permanently: the injected
snapshot is clearly labeled as simulated in storage, and this script prints
a loud warning every time it runs so it's never run by accident in the
scheduled GitHub Actions job.

Usage:
    python -m tests.simulate_change --source nist_ai_rmf
    python -m tests.simulate_change --source nist_ai_rmf --skip-classification
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src import storage, ingest, diff_detect, classify  # noqa: E402

# A synthetic sentence injected into the copied snapshot to simulate a real
# regulatory update. Written to plausibly resemble real NIST/EU AI Act
# language so the classifier is exercised realistically.
SIMULATED_ADDITION = (
    " NIST has published updated guidance requiring organizations deploying "
    "generative AI systems to disclose AI-generated content to end users and "
    "maintain documentation of model training data provenance as part of "
    "ongoing risk management obligations."
)


def simulate_change(source_id: str, skip_classification: bool = False) -> None:
    storage.init_db()

    with storage.get_conn() as conn:
        latest = storage.get_latest_snapshot(conn, source_id)
        if latest is None:
            print(
                f"No existing snapshot found for '{source_id}'. Run "
                f"`python -m src.main --source {source_id}` first to "
                f"establish a real baseline before simulating a change against it.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"[SIMULATED] Using real snapshot from {latest.fetched_at} as the baseline.")

        old_text = latest.raw_text
        new_text = old_text + SIMULATED_ADDITION

        new_snapshot = storage.Snapshot(
            id=None,
            source_id=source_id,
            fetched_at=storage.now_iso(),
            content_hash=ingest.hash_text(new_text),
            raw_text=new_text,
        )
        new_snapshot_id = storage.insert_snapshot(conn, new_snapshot)

        diff_text = diff_detect.build_diff(old_text, new_text)
        print("\n--- Simulated diff ---")
        print(diff_text)
        print("--- end diff ---\n")

        change = storage.ChangeRecord(
            id=None,
            source_id=source_id,
            detected_at=storage.now_iso(),
            prev_snapshot_id=latest.id,
            new_snapshot_id=new_snapshot_id,
            diff_text=diff_text,
        )

        if not skip_classification:
            print("[SIMULATED] Sending diff to Claude for classification...")
            result = classify.classify_diff(f"[SIMULATED CHANGE] {source_id}", diff_text)
            change.change_summary = f"[SIMULATED FOR DEMO] {result.change_summary}"
            change.ai_relevant = result.ai_relevant
            change.ai_relevance_category = result.ai_relevance_category
            change.confidence = result.confidence
            change.reasoning = result.reasoning
        else:
            change.change_summary = "[SIMULATED FOR DEMO] Classification skipped."

        storage.insert_change(conn, change)
        print(f"[SIMULATED] Change recorded (ai_relevant={change.ai_relevant}).")
        print(
            "\nNOTE: this change is clearly labeled '[SIMULATED FOR DEMO]' in "
            "the dashboard. Delete it from the database before treating your "
            "change log as a real audit trail, or keep it and be upfront "
            "about it being a test case — both are fine, just don't present "
            "it as a real detected regulatory change."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source id to simulate a change for")
    parser.add_argument("--skip-classification", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print("SIMULATING A CHANGE FOR DEMO/TESTING PURPOSES.")
    print("This is not a real detected regulatory change.")
    print("=" * 70)
    print()

    simulate_change(args.source, skip_classification=args.skip_classification)


if __name__ == "__main__":
    main()
