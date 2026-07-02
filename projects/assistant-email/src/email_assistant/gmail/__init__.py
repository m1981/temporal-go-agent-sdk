"""Gmail integration layer — thin wrapper around the gmcli CLI (see ADR-001)."""

from email_assistant.gmail.gmcli_client import GmcliClient, GmcliError

__all__ = ["GmcliClient", "GmcliError"]
