"""
Change detection: compare a new snapshot's text against the previous one
and produce a human/LLM-readable diff.

We use difflib rather than a heavier diffing library to keep this dependency-
free and easy to reason about. For very large documents, consider chunking
by section before diffing (see docs/evaluation.md for notes on this).
"""

from __future__ import annotations

import difflib


def has_changed(old_hash: str | None, new_hash: str) -> bool:
    return old_hash != new_hash


def build_diff(old_text: str, new_text: str, context_lines: int = 2) -> str:
    """
    Returns a unified-diff-style string. Text is normalized (whitespace
    collapsed) upstream, so we split on sentences rather than lines to get
    a more meaningful diff granularity than difflib's default line mode.
    """
    old_sentences = _split_sentences(old_text)
    new_sentences = _split_sentences(new_text)

    diff = difflib.unified_diff(
        old_sentences,
        new_sentences,
        lineterm="",
        n=context_lines,
    )
    return "\n".join(diff)


def _split_sentences(text: str) -> list[str]:
    # Simple sentence splitter — good enough for regulatory prose, which is
    # generally well-punctuated. Swap for a proper NLP sentence tokenizer
    # (e.g. nltk.sent_tokenize) if you need higher fidelity.
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def diff_is_trivial(diff_text: str, min_changed_chars: int = 40) -> bool:
    """
    Filters out noise diffs (e.g. a single date string or view counter
    changing) before spending an LLM call on classification.
    """
    changed_chars = sum(
        len(line) for line in diff_text.splitlines() if line.startswith(("+", "-"))
    )
    return changed_chars < min_changed_chars
