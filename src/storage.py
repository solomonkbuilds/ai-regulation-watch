"""
SQLite storage layer for AI Reg Watch.

Schema:
  sources   - static metadata about each monitored source (mirrors sources.yaml)
  snapshots - every fetched version of a source's content (hash + raw text)
  changes   - a detected diff between two consecutive snapshots, plus the
              LLM classification/summary for that diff
"""

from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Iterator

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_reg_watch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    type TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(id),
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_source ON snapshots(source_id, fetched_at);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(id),
    detected_at TEXT NOT NULL,
    prev_snapshot_id INTEGER REFERENCES snapshots(id),
    new_snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
    diff_text TEXT NOT NULL,
    change_summary TEXT,
    ai_relevant INTEGER,              -- 0/1, NULL if not yet classified
    ai_relevance_category TEXT,       -- disclosure_obligation | risk_management | model_governance | not_ai_related
    confidence TEXT,                  -- high | medium | low
    reasoning TEXT
);

CREATE INDEX IF NOT EXISTS idx_changes_source ON changes(source_id, detected_at);
"""


@dataclass
class Snapshot:
    id: Optional[int]
    source_id: str
    fetched_at: str
    content_hash: str
    raw_text: str


@dataclass
class ChangeRecord:
    id: Optional[int]
    source_id: str
    detected_at: str
    prev_snapshot_id: Optional[int]
    new_snapshot_id: int
    diff_text: str
    change_summary: Optional[str] = None
    ai_relevant: Optional[bool] = None
    ai_relevance_category: Optional[str] = None
    confidence: Optional[str] = None
    reasoning: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_source(conn: sqlite3.Connection, source: dict) -> None:
    conn.execute(
        """
        INSERT INTO sources (id, name, url, type, notes)
        VALUES (:id, :name, :url, :type, :notes)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, url=excluded.url,
            type=excluded.type, notes=excluded.notes
        """,
        source,
    )


def get_latest_snapshot(conn: sqlite3.Connection, source_id: str) -> Optional[Snapshot]:
    row = conn.execute(
        "SELECT * FROM snapshots WHERE source_id = ? ORDER BY fetched_at DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    if row is None:
        return None
    return Snapshot(**dict(row))


def insert_snapshot(conn: sqlite3.Connection, snap: Snapshot) -> int:
    cur = conn.execute(
        """
        INSERT INTO snapshots (source_id, fetched_at, content_hash, raw_text)
        VALUES (?, ?, ?, ?)
        """,
        (snap.source_id, snap.fetched_at, snap.content_hash, snap.raw_text),
    )
    return cur.lastrowid


def insert_change(conn: sqlite3.Connection, change: ChangeRecord) -> int:
    cur = conn.execute(
        """
        INSERT INTO changes (
            source_id, detected_at, prev_snapshot_id, new_snapshot_id,
            diff_text, change_summary, ai_relevant, ai_relevance_category,
            confidence, reasoning
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            change.source_id,
            change.detected_at,
            change.prev_snapshot_id,
            change.new_snapshot_id,
            change.diff_text,
            change.change_summary,
            None if change.ai_relevant is None else int(change.ai_relevant),
            change.ai_relevance_category,
            change.confidence,
            change.reasoning,
        ),
    )
    return cur.lastrowid


def list_changes(conn: sqlite3.Connection, ai_relevant_only: bool = False) -> list[dict]:
    query = "SELECT * FROM changes"
    if ai_relevant_only:
        query += " WHERE ai_relevant = 1"
    query += " ORDER BY detected_at DESC"
    rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]
