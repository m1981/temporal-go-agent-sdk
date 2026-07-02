"""Structured logging.

Two modes:
- **text** (default, dev-friendly): timestamp + level + name + message + extras.
- **json** (``LOG_JSON=1``): one JSON object per line, ready for shipping to
  a log aggregator.

A run-scoped ``run_id`` is injected via :class:`RunContextFilter` so every
line for a single agent invocation can be correlated.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from typing import Any

_STANDARD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }
)


class RunContextFilter(logging.Filter):
    """Injects a per-run correlation ID onto every record."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON-lines formatter with `extra=` support."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> str:
    """Idempotently configure the root logger. Returns the generated ``run_id``."""
    run_id = uuid.uuid4().hex[:12]

    root = logging.getLogger()
    root.setLevel(level)
    # Wipe pre-existing handlers so calling twice (e.g. in tests) is safe.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RunContextFilter(run_id))
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [run=%(run_id)s]: %(message)s"
            )
        )
    root.addHandler(handler)

    # Quiet chatty third-party libs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return run_id
