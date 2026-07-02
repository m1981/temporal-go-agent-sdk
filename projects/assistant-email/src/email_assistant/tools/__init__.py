"""LLM-facing tools (see ADR-002: one tool per operation type)."""

from email_assistant.tools.base import Tool, ToolResult
from email_assistant.tools.gmail_reader import GmailReaderTool
from email_assistant.tools.gmail_sender import GmailSenderTool

__all__ = ["GmailReaderTool", "GmailSenderTool", "Tool", "ToolResult"]
