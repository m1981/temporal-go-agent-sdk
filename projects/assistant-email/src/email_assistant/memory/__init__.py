"""Thread memory (Phase 3a) — remembers what the assistant has already seen.

Design goal: idempotent runs. If the agent already surfaced a thread as
URGENT in a prior run, we shouldn't wake the user again. See brief.md
> Notification Logic.
"""

from email_assistant.memory.thread_store import ThreadRecord, ThreadStore

__all__ = ["ThreadRecord", "ThreadStore"]
