"""Tests for the LLM-facing tools — pure unit tests, no network."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from email_assistant.domain.email import Email
from email_assistant.gmail import GmcliClient
from email_assistant.tools import GmailReaderTool, GmailSenderTool, Tool
from email_assistant.tools.base import to_anthropic_schema


def _reader() -> tuple[GmailReaderTool, MagicMock]:
    client = MagicMock(spec=GmcliClient)
    return GmailReaderTool(client=client), client


def test_reader_conforms_to_protocol() -> None:
    r, _ = _reader()
    assert isinstance(r, Tool)


def test_reader_search_returns_serializable_payload() -> None:
    r, client = _reader()
    client.search.return_value = [Email("1", "d", "a@b", "s", "L")]
    out = r.execute({"action": "search", "query": "newer_than:2h", "max_results": 5})
    assert out["total_count"] == 1
    assert out["emails"][0]["id"] == "1"
    client.search.assert_called_once_with("newer_than:2h", max_results=5)


def test_reader_search_defaults_when_query_missing() -> None:
    r, client = _reader()
    client.search.return_value = []
    r.execute({"action": "search"})
    client.search.assert_called_once_with("newer_than:1d", max_results=20)


def test_reader_thread_requires_thread_id() -> None:
    r, _ = _reader()
    with pytest.raises(ValueError, match="thread_id"):
        r.execute({"action": "thread"})


def test_reader_rejects_unknown_action() -> None:
    r, _ = _reader()
    with pytest.raises(ValueError, match="Unknown action"):
        r.execute({"action": "nuke"})


def test_sender_requires_all_fields() -> None:
    s = GmailSenderTool(client=MagicMock(spec=GmcliClient))
    with pytest.raises(ValueError, match="'to'"):
        s.execute({"subject": "x", "body": "y"})


def test_sender_calls_client_and_reports_success() -> None:
    client = MagicMock(spec=GmcliClient)
    client.send.return_value = "ok"
    s = GmailSenderTool(client=client)

    out = s.execute({"to": "a@b", "subject": "hi", "body": "yo"})

    assert out["success"] is True
    assert out["to"] == "a@b"
    client.send.assert_called_once_with(to="a@b", subject="hi", body="yo", thread_id=None)


def test_anthropic_schema_shape() -> None:
    r, _ = _reader()
    schema = to_anthropic_schema(r)
    assert schema["name"] == "gmail_reader"
    assert "input_schema" in schema
    assert schema["input_schema"]["required"] == ["action"]
