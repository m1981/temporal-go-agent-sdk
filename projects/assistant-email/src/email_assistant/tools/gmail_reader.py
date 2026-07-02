"""Gmail reader tool — LLM-facing wrapper over :class:`GmcliClient`."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from email_assistant.gmail import GmcliClient
from email_assistant.tools.base import JsonSchema, ToolResult

_DEFAULT_QUERY = "newer_than:1d"
_DEFAULT_MAX_RESULTS = 20


@dataclass(frozen=True, slots=True)
class GmailReaderTool:
    """Search Gmail and read full threads.

    Two actions:
    - ``search``: run a Gmail query and return a list of email metadata rows.
    - ``thread``: return the full body of one thread.

    The action-dispatch pattern (rather than two separate tools) matches ADR-002
    while keeping the LLM's tool inventory small.
    """

    client: GmcliClient

    # ------------------------------------------------------------------ Tool

    @property
    def name(self) -> str:
        return "gmail_reader"

    @property
    def display_name(self) -> str:
        return "Gmail Reader"

    @property
    def description(self) -> str:
        return (
            "Search and read emails from Gmail. Use this to find recent emails, "
            "search by sender, subject, or date. Returns a list with id, date, "
            "sender, subject, and labels. To read a full thread, call again with "
            "action='thread' and the thread_id from a prior search."
        )

    @property
    def parameters(self) -> JsonSchema:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "thread"],
                    "description": "'search' to find emails, 'thread' to read a full thread.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Gmail search query (e.g. 'newer_than:2h', "
                        "'from:boss@company.com', 'is:unread subject:urgent'). "
                        f"Defaults to '{_DEFAULT_QUERY}'."
                    ),
                },
                "thread_id": {
                    "type": "string",
                    "description": "Thread ID (required when action='thread').",
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Max emails to return (default {_DEFAULT_MAX_RESULTS}).",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action")
        if action == "search":
            return self._search(args)
        if action == "thread":
            return self._thread(args)
        raise ValueError(f"Unknown action: {action!r} (expected 'search' or 'thread')")

    # -------------------------------------------------------------- internals

    def _search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = (args.get("query") or _DEFAULT_QUERY).strip()
        max_results = int(args.get("max_results") or _DEFAULT_MAX_RESULTS)
        emails = self.client.search(query, max_results=max_results)
        return {
            "query": query,
            "total_count": len(emails),
            "emails": [asdict(e) for e in emails],
        }

    def _thread(self, args: dict[str, Any]) -> dict[str, Any]:
        thread_id = (args.get("thread_id") or "").strip()
        if not thread_id:
            raise ValueError("thread_id is required for action='thread'")
        content = self.client.thread(thread_id)
        return {"thread_id": thread_id, "content": content}
