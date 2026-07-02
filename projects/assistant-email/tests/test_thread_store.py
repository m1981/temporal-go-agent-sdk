"""Phase 3a: SQLite thread memory."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from email_assistant.domain.email import Priority
from email_assistant.memory import ThreadRecord, ThreadStore


@pytest.fixture
def store(tmp_path: Path) -> ThreadStore:
    s = ThreadStore(tmp_path / "mem.sqlite")
    yield s
    s.close()


def _rec(thread_id: str, priority: Priority = Priority.URGENT) -> ThreadRecord:
    return ThreadRecord(
        thread_id=thread_id,
        subject="hi",
        sender="a@b",
        last_seen_utc=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
        last_priority=priority,
    )


def test_upsert_and_get_roundtrip(store: ThreadStore) -> None:
    store.upsert(_rec("T1"))
    got = store.get("T1")
    assert got is not None
    assert got.thread_id == "T1"
    assert got.last_priority == Priority.URGENT


def test_upsert_updates_existing_row(store: ThreadStore) -> None:
    store.upsert(_rec("T1", Priority.URGENT))
    store.upsert(_rec("T1", Priority.LOW))
    got = store.get("T1")
    assert got is not None
    assert got.last_priority == Priority.LOW


def test_known_ids_returns_all(store: ThreadStore) -> None:
    store.upsert(_rec("T1"))
    store.upsert(_rec("T2"))
    assert store.known_ids() == {"T1", "T2"}


def test_mark_notified_persists(store: ThreadStore) -> None:
    store.upsert(_rec("T1"))
    store.mark_notified("T1")
    got = store.get("T1")
    assert got is not None
    assert got.notified_utc is not None
    assert got.notified_utc.tzinfo is not None


def test_mark_notified_preserved_across_upsert(store: ThreadStore) -> None:
    store.upsert(_rec("T1"))
    store.mark_notified("T1")
    # A subsequent upsert without notified_utc should not clear it.
    store.upsert(_rec("T1", Priority.IMPORTANT))
    got = store.get("T1")
    assert got is not None
    assert got.notified_utc is not None
    assert got.last_priority == Priority.IMPORTANT


def test_get_missing_returns_none(store: ThreadStore) -> None:
    assert store.get("nope") is None


def test_store_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deep" / "mem.sqlite"
    ThreadStore(path).close()
    assert path.parent.is_dir()
