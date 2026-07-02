"""SQLite-backed thread memory.

Why SQLite?
-----------
* Zero-ops (single file), works everywhere Python does.
* Transactional writes → safe even if a run is killed mid-way.
* Trivial to migrate to Postgres/pgvector later (see brief.md Memory Architecture).

Schema is intentionally tiny; long-term semantic memory belongs in a future
component (see Phase 3+ in dev-order.md).
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from email_assistant.domain.email import Priority

_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    thread_id       TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    sender          TEXT NOT NULL,
    last_seen_utc   TEXT NOT NULL,
    last_priority   TEXT NOT NULL,
    notified_utc    TEXT
);
CREATE INDEX IF NOT EXISTS ix_threads_last_seen ON threads(last_seen_utc);
"""


@dataclass(frozen=True, slots=True)
class ThreadRecord:
    """One row in the ``threads`` table."""

    thread_id: str
    subject: str
    sender: str
    last_seen_utc: datetime
    last_priority: Priority
    notified_utc: datetime | None = None


class ThreadStore:
    """Persistent record of every thread the assistant has processed.

    Thread-safe under multi-threaded access via an ``RLock`` around the
    connection. For our single-process cron model this is overkill but cheap.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._tx() as cur:
            cur.executescript(_SCHEMA)

    # ------------------------------------------------------------------ API

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert(self, record: ThreadRecord) -> None:
        """Insert or update a thread. ``notified_utc`` is preserved if not set."""
        with self._tx() as cur:
            cur.execute(
                """
                INSERT INTO threads
                    (thread_id, subject, sender, last_seen_utc, last_priority, notified_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    subject        = excluded.subject,
                    sender         = excluded.sender,
                    last_seen_utc  = excluded.last_seen_utc,
                    last_priority  = excluded.last_priority,
                    notified_utc   = COALESCE(excluded.notified_utc, threads.notified_utc)
                """,
                (
                    record.thread_id,
                    record.subject,
                    record.sender,
                    _iso(record.last_seen_utc),
                    record.last_priority.value,
                    _iso(record.notified_utc) if record.notified_utc else None,
                ),
            )

    def get(self, thread_id: str) -> ThreadRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
        return _row_to_record(row) if row else None

    def known_ids(self) -> set[str]:
        """Return the full set of thread IDs the store has ever seen."""
        with self._lock:
            rows = self._conn.execute("SELECT thread_id FROM threads").fetchall()
        return {r["thread_id"] for r in rows}

    def mark_notified(self, thread_id: str, when: datetime | None = None) -> None:
        """Record that we've notified the user about this thread."""
        when = when or datetime.now(UTC)
        with self._tx() as cur:
            cur.execute(
                "UPDATE threads SET notified_utc = ? WHERE thread_id = ?",
                (_iso(when), thread_id),
            )

    # -------------------------------------------------------------- internals

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        with self._lock, self._conn:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()


# ---------------------------------------------------------------- module utils


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _row_to_record(row: sqlite3.Row) -> ThreadRecord:
    return ThreadRecord(
        thread_id=row["thread_id"],
        subject=row["subject"],
        sender=row["sender"],
        last_seen_utc=datetime.fromisoformat(row["last_seen_utc"]),
        last_priority=Priority(row["last_priority"]),
        notified_utc=(
            datetime.fromisoformat(row["notified_utc"]) if row["notified_utc"] else None
        ),
    )
