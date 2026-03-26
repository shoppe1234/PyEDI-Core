"""SQLite storage for compare runs, pairs, and diffs.

Replaces Google Sheets I/O from json810Compare/comparator.py.
Uses stdlib sqlite3 — no ORM. All functions accept db_path, no global state.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from pyedi_core.comparator.models import DiscoveryRecord, FieldDiff, MatchPair, RunDiffResult, RunSummary

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

CREATE TABLE IF NOT EXISTS error_discovery (
    id               INTEGER PRIMARY KEY,
    run_id           INTEGER NOT NULL REFERENCES compare_runs(id),
    profile          TEXT NOT NULL,
    segment          TEXT NOT NULL,
    field            TEXT NOT NULL,
    source_value     TEXT,
    target_value     TEXT,
    suggested_severity TEXT NOT NULL DEFAULT 'hard',
    applied          BOOLEAN NOT NULL DEFAULT 0,
    applied_at       TEXT,
    applied_by       TEXT,
    discovered_at    TEXT NOT NULL,
    UNIQUE(profile, segment, field)
);

CREATE INDEX IF NOT EXISTS idx_discovery_profile ON error_discovery(profile);
CREATE INDEX IF NOT EXISTS idx_discovery_applied ON error_discovery(applied);
"""


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it doesn't already exist."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Run forward-only migrations for schema evolution."""
    _add_column_if_missing(conn, "compare_runs", "reclassified_from", "INTEGER")
    _add_column_if_missing(conn, "compare_runs", "trading_partner", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "compare_runs", "transaction_type", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "compare_runs", "run_notes", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "field_crosswalk", "segment", "TEXT DEFAULT '*'")
    _migrate_crosswalk_constraint(conn)


def _migrate_crosswalk_constraint(conn: sqlite3.Connection) -> None:
    """Rebuild field_crosswalk with UNIQUE(profile, segment, field_name) if needed."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='field_crosswalk'"
    ).fetchone()
    if row is None:
        return
    ddl = row[0] or ""
    # Already has segment in the unique constraint
    if "segment, field_name" in ddl:
        return
    # Old constraint: UNIQUE(profile, field_name) — rebuild
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS field_crosswalk_new (
            id              INTEGER PRIMARY KEY,
            profile         TEXT NOT NULL,
            field_name      TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'hard',
            numeric         BOOLEAN NOT NULL DEFAULT 0,
            ignore_case     BOOLEAN NOT NULL DEFAULT 0,
            amount_variance REAL DEFAULT NULL,
            updated_at      TEXT NOT NULL,
            updated_by      TEXT DEFAULT 'system',
            segment         TEXT NOT NULL DEFAULT '*',
            UNIQUE(profile, segment, field_name)
        );
        INSERT OR IGNORE INTO field_crosswalk_new
            (id, profile, field_name, severity, numeric, ignore_case,
             amount_variance, updated_at, updated_by, segment)
        SELECT id, profile, field_name, severity, numeric, ignore_case,
               amount_variance, updated_at, updated_by,
               COALESCE(segment, '*')
        FROM field_crosswalk;
        DROP TABLE field_crosswalk;
        ALTER TABLE field_crosswalk_new RENAME TO field_crosswalk;
        CREATE INDEX IF NOT EXISTS idx_crosswalk_profile ON field_crosswalk(profile);
    """)


def init_db(db_path: str) -> None:
    """Create tables if they don't exist. Idempotent."""
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        _migrate_db(conn)
        conn.commit()
    finally:
        conn.close()


def insert_run(
    db_path: str,
    profile: str,
    source_dir: str,
    target_dir: str,
    match_key: str,
    trading_partner: str = "",
    transaction_type: str = "",
) -> int:
    """Insert a new compare_runs row, return run_id."""
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO compare_runs "
            "(profile, started_at, source_dir, target_dir, match_key, trading_partner, transaction_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (profile, datetime.now(timezone.utc).isoformat(), source_dir, target_dir,
             match_key, trading_partner, transaction_type),
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
    segment: str = "*",
) -> None:
    """Insert or replace a field_crosswalk entry."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO field_crosswalk "
            "(profile, field_name, severity, numeric, ignore_case, amount_variance, "
            "updated_at, updated_by, segment) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (profile, field_name, severity, int(numeric), int(ignore_case),
             amount_variance, datetime.now(timezone.utc).isoformat(), updated_by, segment),
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


def get_crosswalk_field(db_path: str, profile: str, field_name: str, segment: str = "*") -> dict | None:
    """Return a single crosswalk entry, or None."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM field_crosswalk WHERE profile = ? AND field_name = ? AND segment = ?",
            (profile, field_name, segment),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def insert_discoveries(db_path: str, run_id: int, discoveries: list[DiscoveryRecord]) -> int:
    """Bulk-insert discovery records (INSERT OR IGNORE). Returns count inserted."""
    if not discoveries:
        return 0
    conn = _connect(db_path)
    try:
        cursor = conn.executemany(
            "INSERT OR IGNORE INTO error_discovery "
            "(run_id, profile, segment, field, source_value, target_value, "
            "suggested_severity, applied, discovered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
            [
                (run_id, d.profile, d.segment, d.field, d.source_value,
                 d.target_value, d.suggested_severity, d.discovered_at)
                for d in discoveries
            ],
        )
        conn.commit()
        return conn.total_changes
    finally:
        conn.close()


def get_discoveries(db_path: str, profile: str, applied: bool | None = None) -> list[dict]:
    """Return discovery records for a profile, optionally filtered by applied status."""
    conn = _connect(db_path)
    try:
        if applied is None:
            rows = conn.execute(
                "SELECT * FROM error_discovery WHERE profile = ? ORDER BY id",
                (profile,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM error_discovery WHERE profile = ? AND applied = ? ORDER BY id",
                (profile, int(applied)),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def apply_discovery(db_path: str, discovery_id: int, applied_by: str = "user") -> None:
    """Mark a discovery as applied (sets applied=1, applied_at, applied_by)."""
    conn = _connect(db_path)
    try:
        conn.execute(
            "UPDATE error_discovery SET applied = 1, applied_at = ?, applied_by = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), applied_by, discovery_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_severity_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY severity for all diffs in a run."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.severity, COUNT(*) as cnt FROM compare_diffs d "
            "JOIN compare_pairs p ON d.pair_id = p.id "
            "WHERE p.run_id = ? GROUP BY d.severity",
            (run_id,),
        ).fetchall()
        return {r["severity"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_segment_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY segment for all diffs in a run."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.segment, COUNT(*) as cnt FROM compare_diffs d "
            "JOIN compare_pairs p ON d.pair_id = p.id "
            "WHERE p.run_id = ? GROUP BY d.segment",
            (run_id,),
        ).fetchall()
        return {r["segment"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_field_breakdown(db_path: str, run_id: int) -> dict[str, int]:
    """COUNT(*) GROUP BY field for all diffs in a run."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.field, COUNT(*) as cnt FROM compare_diffs d "
            "JOIN compare_pairs p ON d.pair_id = p.id "
            "WHERE p.run_id = ? GROUP BY d.field",
            (run_id,),
        ).fetchall()
        return {r["field"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_top_errors(db_path: str, run_id: int, limit: int = 10) -> list[dict]:
    """Top N (segment, field) combos by occurrence count."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.segment, d.field, COUNT(*) as cnt FROM compare_diffs d "
            "JOIN compare_pairs p ON d.pair_id = p.id "
            "WHERE p.run_id = ? GROUP BY d.segment, d.field "
            "ORDER BY cnt DESC LIMIT ?",
            (run_id, limit),
        ).fetchall()
        return [{"segment": r["segment"], "field": r["field"], "count": r["cnt"]} for r in rows]
    finally:
        conn.close()


def compare_two_runs(db_path: str, run_id_a: int, run_id_b: int) -> RunDiffResult:
    """Diff two runs by (segment, field) keys. Returns new/resolved/changed/unchanged."""
    conn = _connect(db_path)
    try:
        def _get_diff_set(rid: int) -> dict[tuple[str, str], dict]:
            rows = conn.execute(
                "SELECT d.segment, d.field, d.severity, d.source_value, d.target_value, d.description "
                "FROM compare_diffs d JOIN compare_pairs p ON d.pair_id = p.id "
                "WHERE p.run_id = ?",
                (rid,),
            ).fetchall()
            result: dict[tuple[str, str], dict] = {}
            for r in rows:
                key = (r["segment"], r["field"])
                result[key] = dict(r)
            return result

        diffs_a = _get_diff_set(run_id_a)
        diffs_b = _get_diff_set(run_id_b)

        keys_a = set(diffs_a.keys())
        keys_b = set(diffs_b.keys())

        new_errors = [diffs_b[k] for k in keys_b - keys_a]
        resolved_errors = [diffs_a[k] for k in keys_a - keys_b]

        changed_errors = []
        unchanged_count = 0
        for k in keys_a & keys_b:
            if diffs_a[k]["severity"] != diffs_b[k]["severity"]:
                changed_errors.append({
                    "segment": k[0], "field": k[1],
                    "severity_a": diffs_a[k]["severity"],
                    "severity_b": diffs_b[k]["severity"],
                })
            else:
                unchanged_count += 1

        return RunDiffResult(
            new_errors=new_errors,
            resolved_errors=resolved_errors,
            changed_errors=changed_errors,
            unchanged_count=unchanged_count,
        )
    finally:
        conn.close()


def get_all_diffs_for_run(db_path: str, run_id: int) -> list[dict]:
    """Return all diffs for a run, joined with pair info."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT d.*, p.match_value, p.source_file, p.target_file, p.id as pair_id "
            "FROM compare_diffs d JOIN compare_pairs p ON d.pair_id = p.id "
            "WHERE p.run_id = ?",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def clone_run_for_reclassify(db_path: str, original_run_id: int) -> int:
    """Create a new run row cloned from original, with reclassified_from set. Returns new run_id."""
    conn = _connect(db_path)
    try:
        orig = conn.execute("SELECT * FROM compare_runs WHERE id = ?", (original_run_id,)).fetchone()
        if orig is None:
            raise ValueError(f"Run {original_run_id} not found")
        cursor = conn.execute(
            "INSERT INTO compare_runs "
            "(profile, started_at, source_dir, target_dir, match_key, reclassified_from) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (orig["profile"], datetime.now(timezone.utc).isoformat(),
             orig["source_dir"], orig["target_dir"], orig["match_key"], original_run_id),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def clone_pairs_for_reclassify(db_path: str, original_run_id: int, new_run_id: int) -> dict[int, int]:
    """Copy pairs from original run to new run. Returns {old_pair_id: new_pair_id}."""
    conn = _connect(db_path)
    try:
        orig_pairs = conn.execute(
            "SELECT * FROM compare_pairs WHERE run_id = ?", (original_run_id,),
        ).fetchall()
        mapping: dict[int, int] = {}
        for p in orig_pairs:
            cursor = conn.execute(
                "INSERT INTO compare_pairs "
                "(run_id, source_file, source_tx_index, target_file, target_tx_index, "
                "match_value, status, diff_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (new_run_id, p["source_file"], p["source_tx_index"],
                 p["target_file"], p["target_tx_index"], p["match_value"],
                 p["status"], 0),
            )
            mapping[p["id"]] = cursor.lastrowid  # type: ignore[assignment]
        conn.commit()
        return mapping
    finally:
        conn.close()


def _row_to_run_summary(row: sqlite3.Row) -> RunSummary:
    """Convert a sqlite3.Row to RunSummary dataclass."""
    # Safe access for columns that may not exist in older DBs
    row_dict = dict(row)
    return RunSummary(
        run_id=row_dict["id"],
        profile=row_dict["profile"],
        total_pairs=row_dict["total_pairs"],
        matched=row_dict["matched"],
        mismatched=row_dict["mismatched"],
        unmatched=row_dict["unmatched"],
        started_at=row_dict["started_at"],
        finished_at=row_dict.get("finished_at") or "",
        reclassified_from=row_dict.get("reclassified_from"),
        trading_partner=row_dict.get("trading_partner") or "",
        transaction_type=row_dict.get("transaction_type") or "",
    )
