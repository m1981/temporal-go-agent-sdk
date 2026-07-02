"""Deterministic post-processing pipeline (Phase 3 integration).

The agent's job is to *talk*. This pipeline's job is to *record*:
classify every fetched email against user rules, persist thread memory, and
render a stable Markdown summary. The two run side-by-side so we always
have a ground-truth audit trail regardless of what the LLM wrote.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from email_assistant.classify import UrgencyClassifier
from email_assistant.domain.email import Email, Priority
from email_assistant.gmail import GmcliClient
from email_assistant.memory import ThreadRecord, ThreadStore
from email_assistant.notify import Summary, SummaryFormatter

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DigestResult:
    """What the deterministic pipeline produced for a single run."""

    summary: Summary
    rendered: str
    new_thread_ids: set[str]

    @property
    def has_new_urgent(self) -> bool:
        urgent = self.summary.by_priority.get(Priority.URGENT, [])
        return any(e.id in self.new_thread_ids for e in urgent)


@dataclass
class DigestPipeline:
    """Compose the three Phase-3 features into one pass over the inbox.

    Injectable so tests can hand in fakes for every collaborator.
    """

    gmail: GmcliClient
    classifier: UrgencyClassifier
    formatter: SummaryFormatter
    memory: ThreadStore

    def run(self, query: str = "newer_than:2h", *, max_results: int = 50) -> DigestResult:
        emails = self.gmail.search(query, max_results=max_results)
        classified = self.classifier.classify_all(emails)

        known = self.memory.known_ids()
        new_ids = {e.id for e in classified if e.id not in known}

        summary, rendered = self.formatter.summarize_and_render(classified)
        self._persist(classified)

        log.info(
            "digest.done",
            extra={
                "total": summary.total,
                "urgent": summary.urgent_count,
                "new": len(new_ids),
                "has_new_urgent": any(
                    e.id in new_ids
                    for e in summary.by_priority.get(Priority.URGENT, [])
                ),
            },
        )
        return DigestResult(summary=summary, rendered=rendered, new_thread_ids=new_ids)

    # -------------------------------------------------------------- internals

    def _persist(self, emails: list[Email]) -> None:
        now = datetime.now(UTC)
        for e in emails:
            self.memory.upsert(
                ThreadRecord(
                    thread_id=e.id,
                    subject=e.subject,
                    sender=e.sender,
                    last_seen_utc=now,
                    last_priority=e.priority or Priority.LOW,
                )
            )
