# ADR-004: Token Budget Strategy

## Status

**Accepted** - 2026-07-02

## Context

The email assistant runs every 2 hours, consuming tokens each time. We need to control costs while maintaining quality.

## Decision

Set a **50,000 token budget per run** with automatic stopping when exceeded.

## Rationale

### Usage Estimation

| Component | Tokens/Run | Runs/Day | Daily Total |
|---|---|---|---|
| System prompt | 500 | 12 | 6,000 |
| Email list | 2,000 | 12 | 24,000 |
| Analysis | 1,000 | 12 | 12,000 |
| Summary | 500 | 12 | 6,000 |
| **Total** | **4,000** | **12** | **48,000** |

### Budget Setting

- **Per run**: 50,000 tokens (10x average)
- **Daily limit**: Not enforced yet (future)
- **Alert threshold**: 80% of budget

## Consequences

### Positive
- Predictable costs
- Prevents runaway token usage
- Graceful degradation

### Negative
- May cut off complex analysis
- Requires monitoring

## Implementation

```go
agent.NewAgent(
    agent.WithMaxTokens(50000),
    // ...
)
```

The SDK automatically:
1. Tracks token usage per LLM call
2. Stops when budget exceeded
3. Returns partial results

## Cost Estimate

| Model | Cost/1K tokens | Daily Cost |
|---|---|---|
| Haiku | $0.00025 | ~$0.01 |
| Sonnet | $0.003 | ~$0.15 |
| GPT-4 | $0.03 | ~$1.50 |

## Related Decisions

- ADR-003: Use Anthropic Claude Haiku

## Notes

Monitor actual usage and adjust budget accordingly.
