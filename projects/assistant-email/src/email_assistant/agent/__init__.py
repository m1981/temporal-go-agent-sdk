"""The agent runtime: LLM tool-use loop + prompt construction."""

from email_assistant.agent.loop import AgentResult, ClaudeAgent
from email_assistant.agent.prompt import build_system_prompt

__all__ = ["AgentResult", "ClaudeAgent", "build_system_prompt"]
