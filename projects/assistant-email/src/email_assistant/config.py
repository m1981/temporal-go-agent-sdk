"""Configuration loading.

All environment access happens here. Downstream code receives an immutable
:class:`Settings` value object and never calls ``os.getenv`` itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from email_assistant.errors import ConfigError

_DEFAULT_MODEL = "claude-haiku-4-5"
_DEFAULT_MAX_TOKENS = 2048
_DEFAULT_MAX_ITERATIONS = 10
_DEFAULT_TOKEN_BUDGET = 50_000
_DEFAULT_QUIET_HOURS = "22-07"


@dataclass(frozen=True, slots=True)
class Settings:
    """All runtime configuration, resolved once at startup."""

    anthropic_api_key: str
    user_email: str
    model: str
    max_tokens: int
    max_iterations: int
    token_budget: int
    log_level: str
    log_json: bool
    memory_path: Path
    quiet_hours: str

    @classmethod
    def load(cls, *, dotenv_path: Path | None = None) -> Settings:
        """Read env vars (optionally seeding from a ``.env`` file).

        Raises :class:`ConfigError` on missing required values so ``main`` can
        translate that to a clean exit rather than a stack trace.
        """
        if dotenv_path is None:
            # Default: project-root .env, same behaviour as the Go skeleton.
            dotenv_path = Path.cwd() / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path, override=False)

        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is required (set it in .env or the environment)"
            )

        user_email = os.getenv("USER_EMAIL", "").strip()
        if not user_email:
            raise ConfigError("USER_EMAIL is required")

        return cls(
            anthropic_api_key=api_key,
            user_email=user_email,
            model=os.getenv("ANTHROPIC_MODEL", _DEFAULT_MODEL),
            max_tokens=_int_env("MAX_TOKENS", _DEFAULT_MAX_TOKENS),
            max_iterations=_int_env("MAX_ITERATIONS", _DEFAULT_MAX_ITERATIONS),
            token_budget=_int_env("TOKEN_BUDGET", _DEFAULT_TOKEN_BUDGET),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            log_json=_bool_env("LOG_JSON", default=False),
            memory_path=Path(os.getenv("MEMORY_PATH", ".data/memory.sqlite")),
            quiet_hours=os.getenv("QUIET_HOURS", _DEFAULT_QUIET_HOURS),
        )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
