# ADR-006: Implement the Production Assistant in Go on the Agent SDK

## Status

**Accepted** - 2026-07-02

## Context

ADRs 001-005 describe the email assistant in terms of the repo's Go agent
SDK — their code samples call `agent.NewAgent`, `agent.WithMaxTokens`, and
`anthropic.NewClient(llm.WithAPIKey...)`. The walking skeleton, however, was
delivered in Python (`projects/assistant-email`) with a hand-rolled
Anthropic tool-use loop, budgets, and config plumbing. That deviation was
never recorded, and roughly 40% of the Python code re-implements what
`pkg/agent` ships tested (loop, budgets, tool registry, dual runtime).

## Decision

Build the production assistant in **Go on the agent SDK**
(`projects/assistant-email-go`), and keep the Python project as the
**executable specification**: same classification rules, memory semantics,
and digest output, used as a comparison oracle.

- The SDK owns the tool-use loop, iteration cap, and token budget
  (ADR-004's `WithMaxIterations` / `WithMaxTokens` are now literal).
- Novel logic ports as pure packages: `classify`, `notify`, `memory`
  (SQLite, pure-Go driver, schema-compatible with the Python store),
  `gmail` (the single gmcli seam, ADR-001), `pipeline`, `config`.
- The deterministic digest pipeline keeps running beside the LLM narrative
  as the ground-truth audit trail.

## Consequences

### Positive
- ~200 lines of loop/budget code deleted, replaced by tested SDK code.
- `AGENT_RUNTIME=temporal` switches the same binary to the durable runtime.
- The assistant dogfoods the SDK with a real scheduled, stateful workload.

### Negative
- Two implementations exist until the Python one is retired; behavior
  drift must be checked against the oracle.
- Contributors need Go for production changes.

## Deviations Noted

`gmail_reader` keeps the Python port's `action` parameter
(`search`/`thread`) inside one tool. ADR-002 chose "separate tools per
operation" and explicitly rejected action dispatch; the split today is
reader vs sender (per ADR-002), but read operations are action-dispatched
within the reader (contra ADR-002's rationale). Recorded here rather than
silently diverging; revisit if the tool inventory grows.

## Related Decisions

- ADR-001 (gmcli seam), ADR-002 (tool pattern), ADR-004 (budgets)
- ADR-007 (Temporal Schedules) builds on this port.
