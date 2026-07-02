"""Deterministic summary formatting.

The LLM writes prose; this module writes the *skeleton* — the block the user
can trust to always look the same and to reflect ground-truth counts.

Kept pure (no I/O): easy to unit-test, easy to reuse as an email body, a
Slack message, or a log line.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from email_assistant.domain.email import Email, Priority

_SECTIONS: tuple[tuple[Priority, str], ...] = (
    (Priority.URGENT, "🚨 URGENT"),
    (Priority.IMPORTANT, "⭐ IMPORTANT"),
    (Priority.LOW, "📋 LOW"),
)
_MAX_ITEMS_PER_SECTION = 5


@dataclass(frozen=True, slots=True)
class Summary:
    """Structured summary — good for tests, logging, and templating."""

    total: int
    by_priority: dict[Priority, list[Email]]

    @property
    def urgent_count(self) -> int:
        return len(self.by_priority.get(Priority.URGENT, []))

    @property
    def has_urgent(self) -> bool:
        return self.urgent_count > 0


@dataclass(frozen=True, slots=True)
class SummaryFormatter:
    """Builds a :class:`Summary` and renders it as Markdown."""

    max_items_per_section: int = _MAX_ITEMS_PER_SECTION

    # ------------------------------------------------------------------ build

    def summarize(self, emails: Iterable[Email]) -> Summary:
        buckets: dict[Priority, list[Email]] = {p: [] for p in Priority}
        total = 0
        for e in emails:
            total += 1
            priority = e.priority or Priority.LOW
            buckets[priority].append(e)
        return Summary(total=total, by_priority=buckets)

    # ------------------------------------------------------------------ render

    def render(self, summary: Summary) -> str:
        lines: list[str] = [
            f"# Email Summary — {summary.total} emails "
            f"({summary.urgent_count} urgent)",
            "",
        ]
        for priority, header in _SECTIONS:
            bucket = summary.by_priority.get(priority, [])
            if not bucket:
                continue
            lines.append(f"## {header} ({len(bucket)})")
            for e in bucket[: self.max_items_per_section]:
                lines.append(f"- **{e.subject}** — {e.sender} ({e.date})")
            if len(bucket) > self.max_items_per_section:
                extra = len(bucket) - self.max_items_per_section
                lines.append(f"- …and {extra} more")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def summarize_and_render(self, emails: Iterable[Email]) -> tuple[Summary, str]:
        summary = self.summarize(emails)
        return summary, self.render(summary)
