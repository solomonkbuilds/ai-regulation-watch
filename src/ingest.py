"""
Ingestion: fetch a source's current content and normalize it to plain text
so it can be hashed and diffed consistently.

Supports:
  - html: fetch page, optionally scope to a CSS selector, strip tags/nav noise
  - pdf:  fetch PDF bytes, extract text

Keep this module dumb and deterministic. Anything "smart" (summarizing,
classifying) belongs in classify.py.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

USER_AGENT = "ai-reg-watch/0.1 (+https://github.com/yourusername/ai-reg-watch)"
TIMEOUT_SECONDS = 30


@dataclass
class FetchResult:
    source_id: str
    raw_text: str
    content_hash: str


def normalize_text(text: str) -> str:
    """Collapse whitespace so trivial formatting shifts don't register as changes."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_html(url: str, selector: str | None = None) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Strip elements that create noise but rarely reflect substantive change
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    scope = soup.select_one(selector) if selector else soup
    if scope is None:
        scope = soup  # fall back to whole page if selector doesn't match

    text = scope.get_text(separator=" ")
    return normalize_text(text)


def fetch_pdf(url: str) -> str:
    import pdfplumber  # local import: only needed for pdf-type sources

    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()

    text_parts = []
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)

    return normalize_text(" ".join(text_parts))


def fetch_source(source: dict) -> FetchResult:
    """source is one entry from config/sources.yaml (as a dict)."""
    if source["type"] == "html":
        text = fetch_html(source["url"], source.get("selector"))
    elif source["type"] == "pdf":
        text = fetch_pdf(source["url"])
    else:
        raise ValueError(f"Unknown source type: {source['type']}")

    return FetchResult(
        source_id=source["id"],
        raw_text=text,
        content_hash=hash_text(text),
    )
