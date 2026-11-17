"""SQLite prototype for idempotent measurement and checkpoint persistence.

No automatic database creation on import; callers explicitly choose the path.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_key)
);
CREATE TABLE IF NOT EXISTS sync_checkpoints (
    stream TEXT PRIMARY KEY,
    cursor TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_measurements_source ON measurements(source);
"""


def canonical_json(record):
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_key(record):
    """Deterministic fallback for snapshot records, not a customer test ID."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


class Storage:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def checkpoint(self, stream):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT cursor FROM sync_checkpoints WHERE stream = ?", (stream,)
            ).fetchone()
            return row[0] if row else None

    def ingest_batch(self, stream, records, cursor):
        """Atomically insert records and advance cursor.

        records: iterable of (source, stable_source_key, JSON-serializable payload).
        A collision with a different payload is an error; the checkpoint stays put.
        The cursor must be the last *fully processed* journal event.
        """
        if not isinstance(stream, str) or not stream:
            raise ValueError("stream must be nonempty")
        if not isinstance(cursor, str) or not cursor:
            raise ValueError("cursor must be nonempty")
        inserted = 0
        duplicates = 0
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                for source, key, payload in records:
                    if not source or not key:
                        raise ValueError("source and key must be nonempty")
                    serialized = canonical_json(payload)
                    result = connection.execute(
                        "INSERT OR IGNORE INTO measurements(source, source_key, payload_json) VALUES (?, ?, ?)",
                        (source, key, serialized),
                    )
                    if result.rowcount:
                        inserted += 1
                    else:
                        existing = connection.execute(
                            "SELECT payload_json FROM measurements WHERE source=? AND source_key=?",
                            (source, key),
                        ).fetchone()
                        if existing is None or existing[0] != serialized:
                            raise ValueError("source key collision with different payload")
                        duplicates += 1
                connection.execute(
                    """INSERT INTO sync_checkpoints(stream, cursor) VALUES (?, ?)
                       ON CONFLICT(stream) DO UPDATE SET cursor=excluded.cursor,
                           updated_at=CURRENT_TIMESTAMP""",
                    (stream, cursor),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return {"inserted": inserted, "duplicates": duplicates, "cursor": cursor}

    def list_measurements(self, source=None, limit=100):
        if not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self.connect() as connection:
            if source is None:
                rows = connection.execute(
                    "SELECT source, source_key, payload_json FROM measurements ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            else:
                rows = connection.execute(
                    "SELECT source, source_key, payload_json FROM measurements WHERE source=? ORDER BY id DESC LIMIT ?",
                    (source, limit),
                )
            return [
                {"source": s, "source_key": k, "payload": json.loads(p)}
                for s, k, p in rows
            ]
