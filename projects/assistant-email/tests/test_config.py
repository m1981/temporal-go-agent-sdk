"""Settings.load() covers Phase 2a (.env loading + validation)."""

from __future__ import annotations

import pytest

from email_assistant.config import Settings
from email_assistant.errors import ConfigError


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in [
        "ANTHROPIC_API_KEY", "USER_EMAIL", "ANTHROPIC_MODEL",
        "MAX_TOKENS", "MAX_ITERATIONS", "TOKEN_BUDGET",
        "LOG_LEVEL", "LOG_JSON", "MEMORY_PATH", "QUIET_HOURS",
    ]:
        monkeypatch.delenv(var, raising=False)


def test_load_requires_api_key(_clean_env: None) -> None:
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        Settings.load(dotenv_path=__import__("pathlib").Path("/nonexistent"))


def test_load_requires_user_email(
    monkeypatch: pytest.MonkeyPatch, _clean_env: None
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    with pytest.raises(ConfigError, match="USER_EMAIL"):
        Settings.load(dotenv_path=__import__("pathlib").Path("/nonexistent"))


def test_load_defaults(monkeypatch: pytest.MonkeyPatch, _clean_env: None) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")

    s = Settings.load(dotenv_path=__import__("pathlib").Path("/nonexistent"))

    assert s.anthropic_api_key == "sk-test"
    assert s.user_email == "user@example.com"
    assert s.model == "claude-haiku-4-5"
    assert s.max_tokens == 2048
    assert s.max_iterations == 10
    assert s.token_budget == 50_000
    assert s.log_json is False


def test_load_int_env_invalid(monkeypatch: pytest.MonkeyPatch, _clean_env: None) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("MAX_TOKENS", "not-a-number")
    with pytest.raises(ConfigError, match="MAX_TOKENS"):
        Settings.load(dotenv_path=__import__("pathlib").Path("/nonexistent"))


def test_load_bool_env(monkeypatch: pytest.MonkeyPatch, _clean_env: None) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("USER_EMAIL", "user@example.com")
    monkeypatch.setenv("LOG_JSON", "true")
    s = Settings.load(dotenv_path=__import__("pathlib").Path("/nonexistent"))
    assert s.log_json is True
