# ADR-002: Tool Interface Pattern

## Status

**Accepted** - 2026-07-02

## Context

The agent SDK defines a `Tool` interface. We need to implement tools for Gmail operations. How should we structure the tools?

## Decision

Implement **one tool per operation type** (read, send) with a JSON Schema for parameters.

## Rationale

### Alternatives Considered

1. **Single GmailTool** with action parameter
2. **Separate tools** for each operation
3. **MCP server** exposing Gmail operations

### Chosen: Separate Tools

```go
type GmailReaderTool struct { ... }  // search, thread
type GmailSenderTool struct { ... }  // send
```

## Consequences

### Positive
- Clear tool descriptions for LLM
- Independent parameter schemas
- Easy to test in isolation
- LLM can choose appropriate tool

### Negative
- More code to maintain
- Duplicate userEmail field

## Implementation

```go
type Tool interface {
    Name() string
    DisplayName() string
    Description() string
    Parameters() JSONSchema
    Execute(ctx context.Context, args map[string]any) (any, error)
}
```

Each tool:
1. Returns descriptive name
2. Provides clear description for LLM
3. Defines JSON Schema for parameters
4. Validates args before execution

## Related Decisions

- ADR-001: Use gmcli for Gmail

## Notes

The LLM selects tools based on description quality. Good descriptions = better tool selection.
