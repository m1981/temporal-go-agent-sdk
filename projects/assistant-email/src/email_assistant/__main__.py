"""Entry point — wires configuration, tools, and the agent loop together.

Exit codes
----------
* 0 — run completed successfully
* 2 — configuration error (missing env vars, bad values)
* 3 — Gmail / gmcli error
* 4 — LLM error
* 1 — anything else unexpected
"""

from __future__ import annotations

import logging

from anthropic import Anthropic, AnthropicError

from email_assistant.agent import AgentResult, ClaudeAgent, build_system_prompt
from email_assistant.classify import ClassificationRules, UrgencyClassifier
from email_assistant.config import Settings
from email_assistant.errors import (
    ConfigError,
    EmailAssistantError,
    GmailError,
    LLMError,
)
from email_assistant.gmail import GmcliClient
from email_assistant.logging_setup import configure_logging
from email_assistant.memory import ThreadStore
from email_assistant.notify import SummaryFormatter
from email_assistant.pipeline import DigestPipeline, DigestResult
from email_assistant.tools import GmailReaderTool, GmailSenderTool, Tool

_DEFAULT_USER_QUERY = (
    "Please check my recent emails and provide a summary.\n"
    "Focus on:\n"
    "1. Any urgent or important emails\n"
    "2. Emails that need a response\n"
    "3. Group similar emails together\n"
    "4. Ignore newsletters and promotions unless they seem important"
)


def main() -> int:
    # --- 1. Config (Phase 2a) --------------------------------------------
    try:
        settings = Settings.load()
    except ConfigError as exc:
        # Config errors precede logging setup, so print plainly.
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2

    # --- 2. Logging (Phase 2c) -------------------------------------------
    run_id = configure_logging(level=settings.log_level, json_output=settings.log_json)
    log = logging.getLogger("email_assistant")
    log.info(
        "run.start",
        extra={"user": settings.user_email, "model": settings.model},
    )

    # --- 3. Dependencies --------------------------------------------------
    gmcli = GmcliClient(user_email=settings.user_email)
    tools: list[Tool] = [
        GmailReaderTool(client=gmcli),
        GmailSenderTool(client=gmcli),
    ]
    agent = ClaudeAgent(
        client=Anthropic(api_key=settings.anthropic_api_key),
        model=settings.model,
        tools=tools,
        system_prompt=build_system_prompt(settings.user_email),
        max_tokens=settings.max_tokens,
        max_iterations=settings.max_iterations,
        token_budget=settings.token_budget,
    )

    # --- 4. Deterministic pipeline (Phase 3) -----------------------------
    memory = ThreadStore(settings.memory_path)
    pipeline = DigestPipeline(
        gmail=gmcli,
        classifier=UrgencyClassifier(rules=_load_rules()),
        formatter=SummaryFormatter(),
        memory=memory,
    )

    # --- 5. Run (Phase 2b: typed error handling) -------------------------
    try:
        digest = pipeline.run()
        result = agent.run(_DEFAULT_USER_QUERY)
    except GmailError as exc:
        log.error("run.failed.gmail", extra={"err": str(exc)})
        return 3
    except (LLMError, AnthropicError) as exc:
        log.error("run.failed.llm", extra={"err": str(exc)})
        return 4
    except EmailAssistantError as exc:
        log.error("run.failed", extra={"err": str(exc)})
        return 1
    finally:
        memory.close()

    _print_report(result, digest)
    log.info(
        "run.finish",
        extra={
            "iterations": result.iterations,
            "tokens": result.total_tokens,
            "stop_reason": result.stop_reason,
            "run_id": run_id,
        },
    )
    return 0


def _load_rules() -> ClassificationRules:
    """Read user-classification rules from env vars (comma-separated).

    Later this can graduate to a YAML file; env keeps parity with the Go skeleton.
    """
    import os

    def _tuple(name: str) -> tuple[str, ...]:
        raw = os.getenv(name, "").strip()
        return tuple(p.strip() for p in raw.split(",") if p.strip())

    return ClassificationRules(
        boss_senders=_tuple("BOSS_SENDERS"),
        family_senders=_tuple("FAMILY_SENDERS"),
        client_senders=_tuple("CLIENT_SENDERS"),
    )


def _print_report(result: AgentResult, digest: DigestResult) -> None:
    """Render both the deterministic digest and the LLM narrative to stdout."""
    bar = "=" * 60
    print(f"\n{bar}\nDETERMINISTIC DIGEST\n{bar}")
    print(digest.rendered)
    print(f"{bar}\nLLM NARRATIVE\n{bar}")
    print(result.content)
    print(bar)
    print(
        f"iterations={result.iterations} "
        f"tokens={result.total_tokens} "
        f"(in={result.input_tokens} out={result.output_tokens}) "
        f"stop={result.stop_reason} "
        f"new_urgent={digest.has_new_urgent}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
