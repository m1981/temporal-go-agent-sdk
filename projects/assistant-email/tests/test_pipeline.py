"""Phase 3 integration: DigestPipeline composes classifier + memory + formatter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from email_assistant.classify import ClassificationRules, UrgencyClassifier
from email_assistant.domain.email import Email
from email_assistant.gmail import GmcliClient
from email_assistant.memory import ThreadStore
from email_assistant.notify import SummaryFormatter
from email_assistant.pipeline import DigestPipeline


def _pipeline(tmp_path: Path, emails: list[Email]) -> tuple[DigestPipeline, ThreadStore]:
    gmail = MagicMock(spec=GmcliClient)
    gmail.search.return_value = emails
    store = ThreadStore(tmp_path / "mem.sqlite")
    return (
        DigestPipeline(
            gmail=gmail,
            classifier=UrgencyClassifier(
                rules=ClassificationRules(boss_senders=("boss@corp",))
            ),
            formatter=SummaryFormatter(),
            memory=store,
        ),
        store,
    )


def test_pipeline_classifies_and_persists(tmp_path: Path) -> None:
    emails = [
        Email("T1", "d", "boss@corp.com", "urgent thing", "INBOX"),
        Email("T2", "d", "spam@promo.com", "Sale!", "CATEGORY_PROMOTIONS"),
    ]
    pipeline, store = _pipeline(tmp_path, emails)

    digest = pipeline.run()

    assert digest.summary.total == 2
    assert digest.summary.urgent_count == 1
    assert digest.new_thread_ids == {"T1", "T2"}
    assert store.known_ids() == {"T1", "T2"}
    store.close()


def test_pipeline_second_run_marks_no_new(tmp_path: Path) -> None:
    emails = [Email("T1", "d", "boss@corp.com", "u", "INBOX")]
    pipeline, store = _pipeline(tmp_path, emails)

    first = pipeline.run()
    assert first.new_thread_ids == {"T1"}

    second = pipeline.run()
    assert second.new_thread_ids == set()
    assert second.has_new_urgent is False
    store.close()


def test_has_new_urgent_true_when_new_urgent_arrives(tmp_path: Path) -> None:
    emails = [Email("T1", "d", "boss@corp.com", "u", "INBOX")]
    pipeline, store = _pipeline(tmp_path, emails)
    digest = pipeline.run()
    assert digest.has_new_urgent is True
    store.close()


def test_pipeline_renders_markdown(tmp_path: Path) -> None:
    emails = [Email("T1", "d", "boss@corp.com", "hey", "INBOX")]
    pipeline, store = _pipeline(tmp_path, emails)
    digest = pipeline.run()
    assert "🚨 URGENT" in digest.rendered
    assert "hey" in digest.rendered
    store.close()
