"""Gmail sender tool — LLM-facing wrapper for outgoing mail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from email_assistant.gmail import GmcliClient
from email_assistant.tools.base import JsonSchema, ToolResult


@dataclass(frozen=True, slots=True)
class GmailSenderTool:
    """Send an email (or reply to a thread) via gmcli.

    Kept intentionally strict: all fields are required except ``thread_id`` so
    that a hallucinated call still fails fast rather than sending garbage.
    """

    client: GmcliClient

    # ------------------------------------------------------------------ Tool

    @property
    def name(self) -> str:
        return "gmail_sender"

    @property
    def display_name(self) -> str:
        return "Gmail Sender"

    @property
    def description(self) -> str:
        return (
            "Send an email using Gmail. Use ONLY when the user explicitly asks "
            "to send. Always echo recipient, subject, and body before calling."
        )

    @property
    def parameters(self) -> JsonSchema:
        return {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address(es), comma-separated.",
                },
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Email body (plain text)."},
                "thread_id": {
                    "type": "string",
                    "description": "Thread ID to reply to (optional).",
                },
            },
            "required": ["to", "subject", "body"],
        }

    def execute(self, args: dict[str, Any]) -> ToolResult:
        to = _require(args, "to")
        subject = _require(args, "subject")
        body = _require(args, "body")
        thread_id = (args.get("thread_id") or "").strip() or None

        output = self.client.send(to=to, subject=subject, body=body, thread_id=thread_id)
        return {
            "success": True,
            "to": to,
            "subject": subject,
            "thread_id": thread_id,
            "message": "Email sent successfully",
            "output": output.strip(),
        }


def _require(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key!r} is required and must be a non-empty string")
    return value.strip()
