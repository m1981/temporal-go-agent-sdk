"""Pure domain types — no I/O, no framework dependencies."""

from email_assistant.domain.email import Email, Priority

__all__ = ["Email", "Priority"]
