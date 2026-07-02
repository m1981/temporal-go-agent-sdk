"""Thin, testable wrapper around the ``gmcli`` binary (ADR-001).

Rationale for this seam
-----------------------
Every piece of I/O in this project — every ``subprocess.run`` — lives here.
That means the agent, the tools, and the tests can operate on parsed
:class:`Email` objects without ever touching the shell. Swapping gmcli for the
Gmail REST API later means rewriting only this file.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass

from email_assistant.domain.email import Email
from email_assistant.errors import GmailError

log = logging.getLogger(__name__)

# gmcli tabular output separator (5 columns: id \t date \t from \t subject \t labels).
_SEARCH_COLUMNS = 5
_DEFAULT_TIMEOUT_S = 30.0


class GmcliError(GmailError):
    """Raised when ``gmcli`` exits non-zero, is missing, or times out.

    Kept as a subclass of :class:`GmailError` so callers can catch by
    intent ("anything Gmail-shaped") without depending on the CLI detail.
    """


@dataclass(frozen=True, slots=True)
class GmcliClient:
    """Invokes ``gmcli`` for a single Gmail account.

    Parameters
    ----------
    user_email:
        The Gmail account that has been previously registered via
        ``gmcli accounts add``.
    binary:
        Path or name of the ``gmcli`` executable. Injectable for tests.
    timeout_s:
        Hard wall-clock timeout applied to every invocation.
    """

    user_email: str
    binary: str = "gmcli"
    timeout_s: float = _DEFAULT_TIMEOUT_S

    # ------------------------------------------------------------------ public

    def search(self, query: str, max_results: int = 20) -> list[Email]:
        """Return recent emails matching a Gmail search query.

        ``query`` uses Gmail's native search syntax (``newer_than:2h``,
        ``from:boss@company.com``, …). Results are truncated to ``max_results``.
        """
        raw = self._run(["search", query, "--max", str(max_results)])
        return list(self._parse_search(raw))

    def thread(self, thread_id: str) -> str:
        """Return the raw thread content (all messages, headers, and body)."""
        if not thread_id:
            raise ValueError("thread_id must be non-empty")
        return self._run(["thread", thread_id])

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        thread_id: str | None = None,
    ) -> str:
        """Send a message (or reply, if ``thread_id`` given). Returns gmcli output."""
        args = ["send", "--to", to, "--subject", subject, "--body", body]
        if thread_id:
            args.extend(["--thread", thread_id])
        return self._run(args)

    # ---------------------------------------------------------------- internal

    def _run(self, args: Iterable[str]) -> str:
        if shutil.which(self.binary) is None:
            raise GmcliError(
                f"{self.binary!r} not found on PATH. "
                "Install with `npm install -g @mariozechner/gmcli`."
            )
        cmd = [self.binary, self.user_email, *args]
        log.debug("gmcli.exec", extra={"cmd": cmd})
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GmcliError(f"gmcli timed out after {self.timeout_s}s: {cmd}") from exc
        except FileNotFoundError as exc:
            raise GmcliError(f"gmcli binary missing: {self.binary}") from exc

        if result.returncode != 0:
            raise GmcliError(
                f"gmcli exited {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout

    @staticmethod
    def _parse_search(raw: str) -> Iterable[Email]:
        """Yield :class:`Email` records from tab-separated gmcli output.

        Skips the header row and any pagination footer (``# Next page: …``).
        """
        lines = raw.strip().splitlines()
        if len(lines) <= 1:
            return
        for line in lines[1:]:
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t", _SEARCH_COLUMNS - 1)
            if len(parts) < _SEARCH_COLUMNS:
                log.warning("gmcli.search.skip_row", extra={"line": line})
                continue
            yield Email(
                id=parts[0].strip(),
                date=parts[1].strip(),
                sender=parts[2].strip(),
                subject=parts[3].strip(),
                labels=parts[4].strip(),
            )
