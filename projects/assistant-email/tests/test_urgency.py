"""Phase 3b: urgency classifier — the deterministic ground truth."""

from __future__ import annotations

from email_assistant.classify import ClassificationRules, UrgencyClassifier
from email_assistant.domain.email import Email, Priority


def _email(**kw: object) -> Email:
    defaults: dict[str, object] = {
        "id": "T",
        "date": "2026-07-02",
        "sender": "someone@example.com",
        "subject": "hello",
        "labels": "INBOX",
    }
    defaults.update(kw)
    return Email(**defaults)  # type: ignore[arg-type]


def _classifier(**rules: object) -> UrgencyClassifier:
    return UrgencyClassifier(rules=ClassificationRules(**rules))  # type: ignore[arg-type]


def test_boss_sender_is_urgent() -> None:
    c = _classifier(boss_senders=("boss@corp.com",))
    assert c.classify(_email(sender="Boss <boss@corp.com>")) == Priority.URGENT


def test_family_sender_is_urgent() -> None:
    c = _classifier(family_senders=("mom@family.io",))
    assert c.classify(_email(sender="Mom <mom@family.io>")) == Priority.URGENT


def test_urgent_keyword_in_subject() -> None:
    c = _classifier()
    assert c.classify(_email(subject="URGENT: server down")) == Priority.URGENT
    assert c.classify(_email(subject="Please verify your account")) == Priority.URGENT


def test_client_sender_is_important() -> None:
    c = _classifier(client_senders=("@bigclient.com",))
    assert c.classify(_email(sender="pm@bigclient.com")) == Priority.IMPORTANT


def test_promotional_labels_are_low() -> None:
    c = _classifier()
    assert c.classify(
        _email(labels="INBOX,CATEGORY_PROMOTIONS")
    ) == Priority.LOW


def test_important_label_bumps_to_important() -> None:
    c = _classifier()
    assert c.classify(_email(labels="INBOX,IMPORTANT")) == Priority.IMPORTANT


def test_default_is_low() -> None:
    c = _classifier()
    assert c.classify(_email(sender="stranger@nowhere", labels="INBOX")) == Priority.LOW


def test_boss_beats_promotional() -> None:
    """A promo-labelled email from the boss should still be URGENT."""
    c = _classifier(boss_senders=("boss@corp",))
    assert c.classify(
        _email(sender="boss@corp.com", labels="CATEGORY_PROMOTIONS")
    ) == Priority.URGENT


def test_classify_all_preserves_length_and_ids() -> None:
    c = _classifier(boss_senders=("boss@corp",))
    emails = [_email(id="1", sender="boss@corp.com"), _email(id="2")]
    out = c.classify_all(emails)
    assert [e.id for e in out] == ["1", "2"]
    assert out[0].priority == Priority.URGENT


def test_empty_rules_do_not_crash() -> None:
    c = UrgencyClassifier()  # all defaults
    assert c.classify(_email()) == Priority.LOW
