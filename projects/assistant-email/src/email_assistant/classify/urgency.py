"""Rule-based urgency classifier.

The rules mirror brief.md's flowchart:

    From Boss?           ─┐
    From Family?         ─┤─► URGENT
    Deadline today?      ─┤
    Meeting <2h away?    ─┘
    From Client?           ─► IMPORTANT
    otherwise              ─► LOW

Configuration is data (:class:`ClassificationRules`), so tuning the assistant
means editing a small dataclass — no code changes to the classifier itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from email_assistant.domain.email import Email, Priority

_URGENT_KEYWORDS: tuple[str, ...] = (
    "urgent",
    "asap",
    "immediately",
    "today",
    "deadline",
    "action required",
    "security alert",
    "password",
    "verify",
    "suspended",
    "pilnie",  # PL: urgent
    "natychmiast",  # PL: immediately
)

_PROMOTIONAL_LABELS: frozenset[str] = frozenset(
    {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS", "CATEGORY_UPDATES"}
)


@dataclass(frozen=True, slots=True)
class ClassificationRules:
    """Data-only description of the user's inbox.

    All matching is case-insensitive and substring-based on the sender field.
    """

    boss_senders: tuple[str, ...] = ()
    family_senders: tuple[str, ...] = ()
    client_senders: tuple[str, ...] = ()
    urgent_keywords: tuple[str, ...] = _URGENT_KEYWORDS

    @property
    def _boss_re(self) -> re.Pattern[str]:
        return _compile(self.boss_senders)

    @property
    def _family_re(self) -> re.Pattern[str]:
        return _compile(self.family_senders)

    @property
    def _client_re(self) -> re.Pattern[str]:
        return _compile(self.client_senders)


@dataclass(frozen=True, slots=True)
class UrgencyClassifier:
    """Classifies :class:`Email` objects against :class:`ClassificationRules`.

    Stateless and cheap — safe to instantiate per run.
    """

    rules: ClassificationRules = field(default_factory=ClassificationRules)

    def classify(self, email: Email) -> Priority:
        sender = email.sender.lower()
        subject = email.subject.lower()
        labels = {lbl.strip() for lbl in email.labels.split(",") if lbl.strip()}

        # Rules 1-2: identity-based URGENT (boss / family)
        if self.rules._boss_re.search(sender) or self.rules._family_re.search(sender):
            return Priority.URGENT

        # Rules 3-4: keyword-based URGENT (deadlines, security alerts, ...)
        if _contains_any(subject, self.rules.urgent_keywords):
            return Priority.URGENT

        # Rule 5: known clients
        if self.rules._client_re.search(sender):
            return Priority.IMPORTANT

        # Anything landing in a promo/social/forum bucket is definitively LOW
        if labels & _PROMOTIONAL_LABELS:
            return Priority.LOW

        # Default: important-looking inbox mail is IMPORTANT, else LOW
        if "INBOX" in labels and "IMPORTANT" in labels:
            return Priority.IMPORTANT
        return Priority.LOW

    def classify_all(self, emails: list[Email]) -> list[Email]:
        """Return a new list with each email's priority set."""
        return [e.with_priority(self.classify(e)) for e in emails]


# ---------------------------------------------------------------- module utils


def _compile(patterns: tuple[str, ...]) -> re.Pattern[str]:
    """Compile a case-insensitive OR-regex; matches nothing when empty."""
    if not patterns:
        return re.compile(r"(?!x)x")  # never matches
    joined = "|".join(re.escape(p.lower()) for p in patterns)
    return re.compile(joined, re.IGNORECASE)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)
