"""Phase 3c: summary formatter."""

from __future__ import annotations

from email_assistant.domain.email import Email, Priority
from email_assistant.notify import SummaryFormatter


def _e(idx: int, priority: Priority | None) -> Email:
    return Email(
        id=str(idx),
        date="2026-07-02",
        sender=f"s{idx}@x.io",
        subject=f"Subject {idx}",
        labels="INBOX",
        priority=priority,
    )


def test_summarize_counts_by_priority() -> None:
    f = SummaryFormatter()
    emails = [
        _e(1, Priority.URGENT),
        _e(2, Priority.URGENT),
        _e(3, Priority.IMPORTANT),
        _e(4, None),  # untagged → LOW
    ]
    s = f.summarize(emails)
    assert s.total == 4
    assert s.urgent_count == 2
    assert s.has_urgent is True
    assert len(s.by_priority[Priority.LOW]) == 1


def test_render_contains_sections_and_headers() -> None:
    f = SummaryFormatter()
    _, rendered = f.summarize_and_render(
        [_e(1, Priority.URGENT), _e(2, Priority.IMPORTANT), _e(3, Priority.LOW)]
    )
    assert "🚨 URGENT" in rendered
    assert "⭐ IMPORTANT" in rendered
    assert "📋 LOW" in rendered
    assert "Subject 1" in rendered


def test_render_truncates_and_shows_overflow() -> None:
    f = SummaryFormatter(max_items_per_section=2)
    emails = [_e(i, Priority.LOW) for i in range(5)]
    _, rendered = f.summarize_and_render(emails)
    assert "…and 3 more" in rendered


def test_render_skips_empty_sections() -> None:
    f = SummaryFormatter()
    _, rendered = f.summarize_and_render([_e(1, Priority.LOW)])
    assert "URGENT" not in rendered
    assert "IMPORTANT" not in rendered
    assert "📋 LOW" in rendered


def test_no_urgent_when_zero() -> None:
    f = SummaryFormatter()
    s = f.summarize([_e(1, Priority.LOW)])
    assert s.has_urgent is False
    assert s.urgent_count == 0
