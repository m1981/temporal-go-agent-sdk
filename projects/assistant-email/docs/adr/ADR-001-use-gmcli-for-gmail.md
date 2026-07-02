# ADR-001: Use gmcli for Gmail Integration

## Status

**Accepted** - 2026-07-02

## Context

We need to integrate with Gmail to read and send emails. Options considered:

1. **Direct Gmail API** - Build OAuth2 + API client from scratch
2. **Google Go SDK** - Use google.golang.org/api/gmail/v1
3. **gmcli** - Use existing CLI tool that wraps Gmail API

## Decision

Use **gmcli** as the Gmail integration layer by wrapping CLI commands in Go tools.

## Rationale

### Pros
- **Zero OAuth code** - gmcli handles all authentication
- **Proven implementation** - Already working, tested
- **Simple integration** - Just `exec.Command("gmcli", ...)`
- **Easy debugging** - Can test commands manually
- **No dependencies** - No Google SDK in go.mod

### Cons
- **Process overhead** - Spawning external process per call
- **Parsing required** - Must parse CLI output
- **Limited error handling** - CLI errors are strings
- **No streaming** - Must wait for full output

## Consequences

### Positive
- Implementation time: 30 minutes vs 2+ hours
- No OAuth token management in Go
- Easy to test and debug
- User can verify with CLI directly

### Negative
- ~50ms overhead per CLI call
- Must maintain output parsing logic
- Breaking changes in gmcli could affect us

## Implementation

```go
type GmailReaderTool struct {
    userEmail string
}

func (t *GmailReaderTool) Execute(ctx context.Context, args map[string]any) (any, error) {
    cmd := exec.CommandContext(ctx, "gmcli", t.userEmail, "search", query)
    output, err := cmd.CombinedOutput()
    // Parse output...
}
```

## Alternatives Considered

### Direct Gmail API
- **Pros**: Full control, streaming, better errors
- **Cons**: Complex OAuth, token refresh, 200+ lines of code

### Google Go SDK
- **Pros**: Official, type-safe
- **Cons**: Heavy dependency, complex setup

## Related Decisions

- ADR-002: Tool Interface Pattern

## Notes

gmcli must be installed on the system:
```bash
npm install -g @mariozechner/gmcli
```
