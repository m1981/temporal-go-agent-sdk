"""Urgency classification (Phase 3b).

Encodes the decision tree from brief.md > Priority Classification as a
deterministic, testable, rule engine. The LLM provides *soft* triage in
natural language; this module provides the *hard*, auditable answer.
"""

from email_assistant.classify.urgency import (
    ClassificationRules,
    UrgencyClassifier,
)

__all__ = ["ClassificationRules", "UrgencyClassifier"]
