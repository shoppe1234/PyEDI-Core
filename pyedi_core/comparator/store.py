"""SQLite storage for compare runs, pairs, and diffs.

Replaces Google Sheets I/O from json810Compare/comparator.py.
Uses stdlib sqlite3 — no ORM. All functions accept db_path, no global state.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from pyedi_core.comparator.models import FieldDiff, MatchPair, RunSummary

_SCHEMA = """
CREATE TABLE IF NOT EXISTS compare_runs (
    id          INTEGER PRIMARY KEY,
    profile     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source_dir  TEXT NOT NULL,
    target_dir  TEXT NOT NULL,
    match_key   TEXT NOT NULL,
    total_pairs INTEGER DEFAULT 0,
    matched     INTEGER DEFAULT 0,
    mismatched  INTEGER DEFAULT 0,
    unmatched   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS compare_pairs (
    id                  INTEGER PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES compare_runs(id),
    source_file         TEXT NOT NULL,
    source_tx_index     INTEGER NOT NULL DEFAULT 0,
    target_file         TEXT,
    target_tx_index     INTEGER DEFAULT 0,
    match_value         TEXT NOT NULL,
    status              TEXT NOT NULL,
    diff_count          INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS compare_diffs (
    id              INTEGER PRIMARY KEY,
    pair_id         INTEGER NOT NULL REFERENCES compare_pairs(id),
    segment         TEXT NOT NULL,
    field           TEXT NOT NULL,
    severity        TEXT NOT NULL,
    source_value    TEXT,
    target_value    TEXT,
    description     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_profile ON compare_runs(profile);
CREATE INDEX IF NOT EXISTS idx_pairs_run_id ON compare_pairs(run_id);
CREATE INDEX IF NOT EXISTS idx_pairs_status ON compare_pairs(status);
CREATE INDEX IF NOT EXISTS idx_diffs_pair_id ON compare_diffs(pair_id);
CREATE INDEX IF NOT EXISTS idx_diffs_severity ON compare_diffs(severity);

CREATE TABLE IF NOT EXISTS field_crosswalk (
    id              INTEGER PRIMARY KEY,
    profile         TEXT NOT NULL,
    field_name      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'hard',
    numeric         BOOLEAN NOT NULL DEFAULT 0,
    ignore_case     BOOLEAN NOT NULL DEFAULT 0,
    amount_variance REAL DEFAULT NULL,
    updated_at      TEXT NOT NULL,
    updated_by      TEXT DEFAULT 'system',
    UNIQUE(profile, field_name)
);

CREATE INDEX IF NOT EXISTS idx_crosswalk_profile ON field_crosswalk(profile);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    """Create tables if they don't exist. Idempotent."""
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_run(db_path: str, profile: str, source_dir: str, target_dir: str, match_key: str) -> int:
    """Insert a new compare_runs row, return run_id."""
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO compare_runs (profile, started_at, source_dir, target_dir, match_key) "
            "VALUES (?, ?, ?, ?, ?)",
            (profile, datetime.now(timezone.utc).isoformat(), source_dir, target_dir, match_key),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def update_run(db_path: str, run_id: int, summary: RunSummary) -> None:
    """Update run with finished_at and summary counts."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE compare_runs SET finished_at = ?, total_pairs = ?, matched = ?, "
            "mismatched = ?, unmatched = ? WHERE id = ?",
            (summary.finished_at, summary.total_pairs, summary.matched,
             summary.mismatched, summary.unmatched, run_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_pair(db_path: str, run_id: int, pair: MatchPair, status: str, diff_count: int) -> int:
    """Insert compare_pairs row, return pair_id."""
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO compare_pairs "
            "(run_id, source_file, source_tx_index, target_file, target_tx_index, match_value, status, diff_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                pair.source.file_path,
                pair.source.transaction_index,
                pair.target.file_path if pair.target else None,
                pair.target.transaction_index if pair.target else 0,
                pair.match_value,
                status,
                diff_count,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def insert_diffs(db_path: str, pair_id: int, diffs: list[FieldDiff]) -> None:
    """Bulk insert compare_diffs rows."""
    if not diffs:
        return
    conn = _connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO compare_diffs (pair_id, segment, field, severity, source_value, target_value, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (pair_id, d.segment, d.field, d.severity, d.source_value, d.target_value, d.description)
                for d in diffs
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_runs(db_path: str, profile: str | None = None, limit: int = 20) -> list[RunSummary]:
    """Query compare_runs, optionally filtered by profile."""
    conn = _connect(db_path)
    try:
        if profile:
            rows = conn.execute(
                "SELECT * FROM compare_runs WHERE profile = ? ORDER BY id DESC LIMIT ?",
                (profile, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM compare_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_run_summary(r) for r in rows]
    finally:
        conn.close()


def get_run(db_path: str, run_id: int) -> RunSummary | None:
    """Get a single run by ID."""
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM compare_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return _row_to_run_summary(row)
    finally:
        conn.close()


def get_pairs(db_path: str, run_id: int, status: str | None = None, limit: int = 50) -> list[dict]:
    """Query compare_pairs for a run, optionally filtered by status."""
    conn = _connect(db_path)
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM compare_pairs WHERE run_id = ? AND status = ? ORDER BY id LIMIT ?",
                (run_id, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM compare_pairs WHERE run_id = ? ORDER BY id LIMIT ?",
                (run_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_diffs(db_path: str, pair_id: int) -> list[FieldDiff]:
    """Query compare_diffs for a pair."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM compare_diffs WHERE pair_id = ? ORDER BY id",
            (pair_id,),
        ).fetchall()
        return [
            FieldDiff(
                segment=r["segment"],
                field=r["field"],
                severity=r["severity"],
                source_value=r["source_value"],
                target_value=r["target_value"],
                description=r["description"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def upsert_crosswalk(
    db_path: str,
    profile: str,
    field_name: str,
    severity: str = "hard",
    numeric: bool = False,
    ignore_case: bool = False,
    amount_variance: float | None = None,
    updated_by: str = "system",
) -> None:
    """Insert or replace a field_crosswalk entry."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO field_crosswalk "
            "(profile, field_name, severity, numeric, ignore_case, amount_variance, updated_at, updated_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (profile, field_name, severity, int(numeric), int(ignore_case),
             amount_variance, datetime.now(timezone.utc).isoformat(), updated_by),
        )
        conn.commit()
    finally:
        conn.close()


def get_crosswalk(db_path: str, profile: str) -> list[dict]:
    """Return all crosswalk entries for a profile."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM field_crosswalk WHERE profile = ? ORDER BY field_name",
            (profile,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_crosswalk_field(db_path: str, profile: str, field_name: str) -> dict | None:
    """Return a single crosswalk entry, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM field_crosswalk WHERE profile = ? AND field_name = ?",
            (profile, field_name),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _row_to_run_summary(row: sqlite3.Row) -> RunSummary:
    """Convert a sqlite3.Row to RunSummary dataclass."""
    return RunSummary(
        run_id=row["id"],
        profile=row["profile"],
        total_pairs=row["total_pairs"],
        matched=row["matched"],
        mismatched=row["mismatched"],
        unmatched=row["unmatched"],
        started_at=row["started_at"],
        finished_at=row["finished_at"] or "",
    )
