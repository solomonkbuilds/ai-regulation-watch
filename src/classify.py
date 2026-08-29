"""
Classification: given a diff, ask Claude to (1) summarize the change in
plain English and (2) classify whether it's AI-relevant, in which
category, and with what confidence.

Requires ANTHROPIC_API_KEY to be set in the environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a regulatory compliance analyst assistant. You are given a diff \
showing what changed in a regulatory or standards document. Your job is to:

1. Summarize the change in 2-3 plain-English sentences, written for a compliance \
professional who has not read the diff themselves.
2. Determine whether the change relates to AI — specifically: AI system disclosure \
obligations, AI risk management requirements, or AI development/model governance oversight.
3. If AI-relevant, classify which category it falls into.
4. Give a confidence level and brief reasoning for your classification.

Respond with ONLY a JSON object, no markdown fences, no preamble, matching this schema:
{
  "change_summary": string,
  "ai_relevant": boolean,
  "ai_relevance_category": "disclosure_obligation" | "risk_management" | "model_governance" | "not_ai_related",
  "confidence": "high" | "medium" | "low",
  "reasoning": string
}

Be conservative: if the change is ambiguous or the diff is too sparse to tell, set \
confidence to "low" rather than guessing "high"."""


@dataclass
class Classification:
    change_summary: str
    ai_relevant: bool
    ai_relevance_category: str
    confidence: str
    reasoning: str


def classify_diff(source_name: str, diff_text: str) -> Classification:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_prompt = f"""Source: {source_name}

Diff:
{diff_text}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model did not return valid JSON: {raw!r}") from e

    return Classification(
        change_summary=data["change_summary"],
        ai_relevant=bool(data["ai_relevant"]),
        ai_relevance_category=data["ai_relevance_category"],
        confidence=data["confidence"],
        reasoning=data["reasoning"],
    )
