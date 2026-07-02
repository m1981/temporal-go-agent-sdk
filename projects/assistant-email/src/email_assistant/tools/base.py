"""Tool protocol — the seam between the agent loop and any concrete tool.

Following ADR-002: each concrete tool implements a single operation type and
exposes a self-describing JSON Schema. The agent depends only on this
protocol, never on a concrete tool.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Anthropic's tool spec is just a JSON Schema object. Kept as ``dict`` to avoid
# leaking anthropic types into the domain.
JsonSchema = dict[str, Any]
ToolResult = Any


@runtime_checkable
class Tool(Protocol):
    """Contract every tool must satisfy.

    Named to match the Go SDK (``Name``, ``DisplayName``, …) so the two
    implementations remain conceptually parallel — see docs/adr/ADR-002.
    """

    @property
    def name(self) -> str:
        """Snake-case identifier the LLM will use to invoke this tool."""

    @property
    def display_name(self) -> str:
        """Human-readable label for logs and UIs."""

    @property
    def description(self) -> str:
        """Prose description shown to the LLM. Quality here drives tool choice."""

    @property
    def parameters(self) -> JsonSchema:
        """JSON Schema for the tool's arguments."""

    def execute(self, args: dict[str, Any]) -> ToolResult:
        """Run the tool. Return a JSON-serialisable value."""


def to_anthropic_schema(tool: Tool) -> dict[str, Any]:
    """Adapt a :class:`Tool` to Anthropic's tool-use schema.

    Kept as a free function so tools themselves stay free of SDK details.
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }
