"""Exception hierarchy for the email assistant.

Rationale
---------
A shallow, purpose-built hierarchy lets ``__main__`` map exceptions to exit
codes and callers to catch by *intent* rather than by concrete type. All
subclasses of :class:`EmailAssistantError` are safe to render to end-users;
anything else is a programmer bug and should propagate.
"""

from __future__ import annotations


class EmailAssistantError(Exception):
    """Base class for all recoverable, user-facing errors."""


class ConfigError(EmailAssistantError):
    """Missing or invalid configuration (env vars, files, etc.)."""


class GmailError(EmailAssistantError):
    """Something went wrong talking to Gmail (via gmcli)."""


class LLMError(EmailAssistantError):
    """Something went wrong talking to the LLM."""


class ToolExecutionError(EmailAssistantError):
    """A tool raised an unexpected error during execution."""


class BudgetExceededError(EmailAssistantError):
    """The run stopped because a token or iteration budget was hit."""
