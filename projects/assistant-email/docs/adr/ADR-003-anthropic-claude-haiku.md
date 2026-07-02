# ADR-003: Use Anthropic Claude Haiku as LLM

## Status

**Accepted** - 2026-07-02

## Context

We need an LLM for the email assistant. Options:

1. **OpenAI GPT-4** - Most capable
2. **Anthropic Claude Sonnet** - Balanced
3. **Anthropic Claude Haiku** - Fast, cheap
4. **Local models** - Self-hosted

## Decision

Use **Anthropic Claude Haiku (claude-haiku-4-5)** for the email assistant.

## Rationale

### Selection Criteria

| Criteria | GPT-4 | Sonnet | Haiku | Local |
|---|---|---|---|---|
| Speed | Slow | Medium | **Fast** | Varies |
| Cost | High | Medium | **Low** | Free |
| Quality | High | High | **Good** | Varies |
| API | OpenAI | Anthropic | **Anthropic** | Self |

### Why Haiku?

1. **Speed** - Email summaries need quick response
2. **Cost** - Running every 2 hours, cost matters
3. **Quality** - Good enough for email classification
4. **Existing key** - User has Anthropic API key

## Consequences

### Positive
- Fast response times (~1-2s)
- Low cost per run (~$0.01)
- Good classification accuracy

### Negative
- May miss nuanced context
- Less capable than GPT-4 for complex analysis

## Implementation

```go
llmClient, err := anthropic.NewClient(
    llm.WithAPIKey(apiKey),
    llm.WithModel("claude-haiku-4-5"),
)
```

## Alternatives Considered

### GPT-4
- **Pros**: Most capable
- **Cons**: Slower, 10x more expensive

### Local Models
- **Pros**: Free, private
- **Cons**: Setup complexity, quality varies

## Related Decisions

- ADR-004: Token Budget Strategy

## Notes

Can upgrade to Sonnet if Haiku quality is insufficient.
