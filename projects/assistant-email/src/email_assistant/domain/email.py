"""Email domain types.

These are pure value objects. They do not know about Gmail, gmcli, or the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Priority(StrEnum):
    """Classification of an email's urgency (see brief.md > Priority Classification)."""

    URGENT = "URGENT"
    IMPORTANT = "IMPORTANT"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class Email:
    """A single parsed email row from `gmcli search`.

    ``id`` is the Gmail thread ID (gmcli's search returns thread-level rows).
    """

    id: str
    date: str
    sender: str
    subject: str
    labels: str = ""
    priority: Priority | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def with_priority(self, priority: Priority) -> Email:
        """Return a copy with priority set (frozen dataclass ⇒ no mutation)."""
        return Email(
            id=self.id,
            date=self.date,
            sender=self.sender,
            subject=self.subject,
            labels=self.labels,
            priority=priority,
            tags=self.tags,
        )
