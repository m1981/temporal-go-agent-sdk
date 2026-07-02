# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Email Assistant project.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-use-gmcli-for-gmail.md) | Use gmcli for Gmail Integration | Accepted | 2026-07-02 |
| [ADR-002](ADR-002-tool-interface-pattern.md) | Tool Interface Pattern | Accepted | 2026-07-02 |
| [ADR-003](ADR-003-anthropic-claude-haiku.md) | Use Anthropic Claude Haiku as LLM | Accepted | 2026-07-02 |
| [ADR-004](ADR-004-token-budget-strategy.md) | Token Budget Strategy | Accepted | 2026-07-02 |
| [ADR-005](ADR-005-scheduling-strategy.md) | Scheduling Strategy | Accepted (Phase 2 superseded by ADR-007) | 2026-07-02 |
| [ADR-006](ADR-006-go-port-on-agent-sdk.md) | Implement the Production Assistant in Go on the Agent SDK | Accepted | 2026-07-02 |
| [ADR-007](ADR-007-temporal-schedules.md) | Temporal Schedules for the Periodic Digest | Accepted | 2026-07-02 |

## ADR Template

```markdown
# ADR-XXX: Title

## Status

**Accepted** | **Deprecated** | **Superseded by ADR-YYY**

## Context

What is the issue that we're seeing that is motivating this decision or change?

## Decision

What is the change that we're proposing and/or doing?

## Consequences

What becomes easier or more difficult to do because of this change?
```

## Rules

1. **Append-only** - Never delete or modify existing ADRs
2. **Number sequentially** - ADR-001, ADR-002, etc.
3. **Date each ADR** - When the decision was made
4. **Link related ADRs** - Reference dependencies
