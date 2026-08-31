"""
Evaluation harness for the AI-relevance classifier.

Why this exists: the classifier is the riskiest part of this pipeline —
false negatives mean a real AI-governance change goes unnoticed, false
positives create alert fatigue. This script runs the classifier against a
small hand-labeled test set and reports accuracy, so classifier changes
(prompt edits, model swaps) can be evaluated objectively instead of by feel.

Usage:
    python tests/eval_classifier.py

Extend eval_set.jsonl with real examples as you collect them from actual
monitored sources — aim for at least 20-30 labeled examples before trusting
the accuracy number.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.classify import classify_diff  # noqa: E402

EVAL_SET_PATH = Path(__file__).resolve().parent / "eval_set.jsonl"


def load_eval_set() -> list[dict]:
    examples = []
    with open(EVAL_SET_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def run_eval() -> None:
    examples = load_eval_set()
    correct = 0
    results = []

    for ex in examples:
        prediction = classify_diff(ex["source_name"], ex["diff_text"])
        is_correct = prediction.ai_relevant == ex["expected_ai_relevant"]
        correct += is_correct
        results.append(
            {
                "id": ex["id"],
                "expected": ex["expected_ai_relevant"],
                "predicted": prediction.ai_relevant,
                "correct": is_correct,
                "confidence": prediction.confidence,
            }
        )
        status = "PASS" if is_correct else "FAIL"
        print(f"[{status}] {ex['id']}: expected={ex['expected_ai_relevant']} "
              f"predicted={prediction.ai_relevant} confidence={prediction.confidence}")

    accuracy = correct / len(examples) if examples else 0
    print(f"\nAccuracy: {correct}/{len(examples)} ({accuracy:.1%})")

    # Write results for docs/evaluation.md to reference
    out_path = Path(__file__).resolve().parent / "eval_results.json"
    with open(out_path, "w") as f:
        json.dump({"accuracy": accuracy, "results": results}, f, indent=2)


if __name__ == "__main__":
    run_eval()
