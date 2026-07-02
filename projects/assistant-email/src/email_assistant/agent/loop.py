"""Anthropic tool-use loop.

Design notes
------------
* We depend on the :class:`~email_assistant.tools.base.Tool` protocol, never
  on concrete tool classes — the loop is reusable for any future tools.
* Token budget and iteration cap come from ADR-004: hard stops protect us
  from runaway conversations.
* Errors raised inside a tool are captured and fed back to the LLM as a
  ``is_error`` tool_result block, so the model can self-correct instead of
  crashing the whole run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, cast

from anthropic import Anthropic, AnthropicError
from anthropic.types import Message, MessageParam, TextBlock, ToolParam, ToolUseBlock

from email_assistant.errors import LLMError
from email_assistant.tools.base import Tool, to_anthropic_schema

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """The outcome of a single :meth:`ClaudeAgent.run` call."""

    content: str
    iterations: int
    input_tokens: int
    output_tokens: int
    stop_reason: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ClaudeAgent:
    """Runs a single Claude conversation with tool-use enabled.

    Parameters mirror the Go SDK's ``WithXxx`` options (ADR parity):
    - ``model`` — LLM identifier (ADR-003: ``claude-haiku-4-5``)
    - ``tools`` — concrete implementations of :class:`Tool`
    - ``max_tokens`` — per-response cap (Anthropic requirement)
    - ``max_iterations`` — hard cap on tool-use turns (ADR-004)
    - ``token_budget`` — cumulative in+out budget across the run (ADR-004)
    """

    client: Anthropic
    model: str
    tools: list[Tool]
    system_prompt: str
    max_tokens: int = 1024
    max_iterations: int = 10
    token_budget: int = 50_000
    _tool_index: dict[str, Tool] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tool_index = {t.name: t for t in self.tools}
        if len(self._tool_index) != len(self.tools):
            raise ValueError("Duplicate tool names detected")

    # ------------------------------------------------------------------ run

    def run(self, user_query: str) -> AgentResult:
        """Drive the tool-use loop until the model stops or a budget is hit."""
        messages: list[MessageParam] = [{"role": "user", "content": user_query}]
        tool_schemas: list[ToolParam] = [
            cast(ToolParam, to_anthropic_schema(t)) for t in self.tools
        ]

        total_in = total_out = 0
        last: Message | None = None

        for iteration in range(1, self.max_iterations + 1):
            log.info(
                "agent.iteration.start",
                extra={"iter": iteration, "tokens_used": total_in + total_out},
            )
            try:
                last = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.system_prompt,
                    tools=tool_schemas,
                    messages=messages,
                )
            except AnthropicError as exc:
                raise LLMError(f"Anthropic call failed on iteration {iteration}: {exc}") from exc
            total_in += last.usage.input_tokens
            total_out += last.usage.output_tokens

            # Persist the assistant turn verbatim.
            messages.append({"role": "assistant", "content": last.content})

            if last.stop_reason != "tool_use":
                log.info(
                    "agent.finish",
                    extra={"reason": last.stop_reason, "iter": iteration},
                )
                break

            tool_results = self._run_tool_calls(last)
            messages.append({"role": "user", "content": cast(Any, tool_results)})

            if total_in + total_out >= self.token_budget:
                log.warning(
                    "agent.budget_exceeded",
                    extra={"used": total_in + total_out, "budget": self.token_budget},
                )
                break
        else:
            log.warning("agent.max_iterations", extra={"cap": self.max_iterations})

        assert last is not None  # loop runs at least once
        return AgentResult(
            content=_final_text(last),
            iterations=iteration,
            input_tokens=total_in,
            output_tokens=total_out,
            stop_reason=last.stop_reason or "unknown",
        )

    # ---------------------------------------------------------------- helpers

    def _run_tool_calls(self, msg: Message) -> list[dict[str, Any]]:
        """Execute every ``tool_use`` block in a model turn.

        Returns Anthropic ``tool_result`` blocks in the same order as the model
        emitted them (Anthropic requires 1-to-1 pairing).
        """
        results: list[dict[str, Any]] = []
        for block in msg.content:
            if not isinstance(block, ToolUseBlock):
                continue
            log.info(
                "tool.call",
                extra={"tool": block.name, "tool_use_id": block.id},
            )
            try:
                tool = self._tool_index[block.name]
            except KeyError:
                results.append(_tool_error(block.id, f"Unknown tool: {block.name}"))
                continue

            try:
                output = tool.execute(dict(block.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _serialize(output),
                    }
                )
            except Exception as exc:  # surface to the model as tool_result, not stderr
                log.exception("tool.error", extra={"tool": block.name})
                results.append(_tool_error(block.id, f"{type(exc).__name__}: {exc}"))
        return results


# ---------------------------------------------------------------- module utils


def _serialize(value: Any) -> str:
    """Convert a tool return value to a string suitable for Anthropic."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def _tool_error(tool_use_id: str, message: str) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": message,
        "is_error": True,
    }


def _final_text(msg: Message) -> str:
    """Concatenate all text blocks in the final assistant message."""
    return "\n".join(b.text for b in msg.content if isinstance(b, TextBlock)).strip()
