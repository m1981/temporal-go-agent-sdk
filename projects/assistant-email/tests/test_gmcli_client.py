"""Unit tests for GmcliClient — no real gmcli invocation."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from email_assistant.domain.email import Email
from email_assistant.gmail import GmcliClient, GmcliError

_SEARCH_OUTPUT = (
    "id\tdate\tfrom\tsubject\tlabels\n"
    "17abc\t2026-07-02\tboss@corp.com\tQ3 review\tINBOX,IMPORTANT\n"
    "17def\t2026-07-02\tnews@x.io\tWeekly\tINBOX,CATEGORY_PROMOTIONS\n"
    "# Next page: token=xyz\n"
)


def _fake_run(returncode: int = 0, stdout: str = "", stderr: str = "") -> object:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_search_parses_rows() -> None:
    client = GmcliClient(user_email="u@x.io")
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run",
               return_value=_fake_run(stdout=_SEARCH_OUTPUT)):
        emails = client.search("newer_than:1d")
    assert emails == [
        Email("17abc", "2026-07-02", "boss@corp.com", "Q3 review", "INBOX,IMPORTANT"),
        Email("17def", "2026-07-02", "news@x.io", "Weekly", "INBOX,CATEGORY_PROMOTIONS"),
    ]


def test_search_respects_max_results() -> None:
    client = GmcliClient(user_email="u@x.io")
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run",
               return_value=_fake_run(stdout=_SEARCH_OUTPUT)) as mock_run:
        client.search("newer_than:1d", max_results=5)
    args = mock_run.call_args[0][0]
    assert "--max" in args and "5" in args


def test_search_raises_when_gmcli_missing() -> None:
    client = GmcliClient(user_email="u@x.io")
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value=None), \
         pytest.raises(GmcliError, match="not found on PATH"):
        client.search("q")


def test_run_raises_on_nonzero_exit() -> None:
    client = GmcliClient(user_email="u@x.io")
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run",
               return_value=_fake_run(returncode=1, stderr="auth failed")), \
         pytest.raises(GmcliError, match="auth failed"):
        client.search("q")


def test_run_raises_on_timeout() -> None:
    client = GmcliClient(user_email="u@x.io", timeout_s=0.01)

    def raise_timeout(*_a: object, **_kw: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["gmcli"], timeout=0.01)

    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run", side_effect=raise_timeout), \
         pytest.raises(GmcliError, match="timed out"):
        client.search("q")


def test_thread_requires_id() -> None:
    client = GmcliClient(user_email="u@x.io")
    with pytest.raises(ValueError, match="thread_id"):
        client.thread("")


def test_send_builds_correct_args() -> None:
    client = GmcliClient(user_email="u@x.io")
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run",
               return_value=_fake_run(stdout="sent")) as mock_run:
        out = client.send(to="a@b.io", subject="hi", body="yo", thread_id="T1")
    assert out == "sent"
    args = mock_run.call_args[0][0]
    assert args[:2] == ["gmcli", "u@x.io"]
    assert "--to" in args and "a@b.io" in args
    assert "--thread" in args and "T1" in args


def test_parse_search_skips_malformed_rows() -> None:
    client = GmcliClient(user_email="u@x.io")
    bad = "id\tdate\tfrom\tsubject\tlabels\ntoo\tfew\tcols\n"
    with patch("email_assistant.gmail.gmcli_client.shutil.which", return_value="/usr/bin/gmcli"), \
         patch("email_assistant.gmail.gmcli_client.subprocess.run",
               return_value=_fake_run(stdout=bad)):
        emails = client.search("q")
    assert emails == []
