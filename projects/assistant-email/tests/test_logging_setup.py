"""Phase 2c: structured logging."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from email_assistant.logging_setup import (
    JsonFormatter,
    RunContextFilter,
    configure_logging,
)


def test_configure_returns_run_id() -> None:
    run_id = configure_logging(level="INFO", json_output=False)
    assert len(run_id) == 12
    assert run_id.isalnum()


def test_configure_is_idempotent() -> None:
    configure_logging(level="INFO")
    configure_logging(level="INFO")
    assert len(logging.getLogger().handlers) == 1


def test_run_context_filter_injects_id() -> None:
    f = RunContextFilter("abc123")
    rec = logging.LogRecord("t", logging.INFO, "x", 1, "hi", None, None)
    assert f.filter(rec) is True
    assert rec.run_id == "abc123"  # type: ignore[attr-defined]


def test_json_formatter_emits_valid_json_with_extras() -> None:
    fmt = JsonFormatter()
    rec = logging.LogRecord("t", logging.INFO, "x", 1, "hello", None, None)
    rec.tool = "gmail_reader"
    rec.run_id = "abc"
    out = fmt.format(rec)
    payload = json.loads(out)
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"
    assert payload["tool"] == "gmail_reader"
    assert payload["run_id"] == "abc"


@pytest.mark.parametrize("json_output", [True, False])
def test_configure_writes_to_stderr(
    json_output: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(level="INFO", json_output=json_output)
    logging.getLogger("email_assistant.test").info("ping", extra={"foo": "bar"})
    captured = capsys.readouterr()
    assert "ping" in captured.err
    if json_output:
        # last non-empty line should be valid JSON
        line = [ln for ln in captured.err.splitlines() if ln.strip()][-1]
        payload = json.loads(line)
        assert payload["foo"] == "bar"


def test_json_formatter_captures_exception() -> None:
    fmt = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = logging.LogRecord(
            "t", logging.ERROR, "x", 1, "err", None, sys.exc_info()
        )
    payload = json.loads(fmt.format(rec))
    assert "ValueError: boom" in payload["exc"]


def _capture(json_output: bool) -> tuple[logging.Logger, StringIO]:
    """(Unused helper kept for readability of the test above.)"""
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    if json_output:
        handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("email_assistant.test_capture")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger, buf
