# Temporal Go Agent SDK

> Type: A | Status: active | Horizon: H1 | Role: Temporal Go lang agent SDK
> Charter: docs/AGENT-CHARTER.md | Profile: Appendix A.1

Temporal Go lang agent SDK

## For agents
Read `AGENTS.md` first. Governance: `docs/DOC-GOVERNANCE-TEMPLATE.md`.

A Go SDK for building durable AI agents with [Temporal](https://temporal.io). This SDK provides a clean abstraction for creating agents that can survive crashes, resume from failures, and run for hours or days.

## Features

- **Dual Runtime**: Run agents in-process or distributed with Temporal
- **AG-UI Protocol**: Real-time streaming with industry-standard events
- **Memory System**: Scoped long-term memory with vector stores
- **Tool System**: Extensible tool framework with approval gates
- **Sub-Agent Delegation**: Recursive agent composition
- **Observability**: OpenTelemetry native tracing and metrics

## Quick Start

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/agenticenv/agent-sdk-go/pkg/agent"
    "github.com/agenticenv/agent-sdk-go/pkg/llm/openai"
)

func main() {
    // Create LLM client
    llm, err := openai.NewClient(
        openai.WithAPIKey("your-api-key"),
        openai.WithModel("gpt-4"),
    )
    if err != nil {
        log.Fatal(err)
    }

    // Create agent
    a, err := agent.NewAgent(
        agent.WithLLM(llm),
        agent.WithMaxIterations(10),
        agent.WithMaxTokens(100000), // Token budget
    )
    if err != nil {
        log.Fatal(err)
    }
    defer a.Close()

    // Run agent
    result, err := a.Run(context.Background(), "What is the meaning of life?", nil)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println(result.Content)
}
```

## With Temporal (Durable Execution)

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/agenticenv/agent-sdk-go/pkg/agent"
    "github.com/agenticenv/agent-sdk-go/pkg/llm/openai"
)

func main() {
    // Create LLM client
    llm, err := openai.NewClient(
        openai.WithAPIKey("your-api-key"),
        openai.WithModel("gpt-4"),
    )
    if err != nil {
        log.Fatal(err)
    }

    // Create agent with Temporal
    a, err := agent.NewAgent(
        agent.WithLLM(llm),
        agent.WithTemporalConfig(agent.TemporalConfig{
            TaskQueue: "agent-queue",
        }),
    )
    if err != nil {
        log.Fatal(err)
    }
    defer a.Close()

    // Run agent (survives crashes!)
    result, err := a.Run(context.Background(), "Analyze this codebase", nil)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Println(result.Content)
}
```

## Refactoring Improvements

This SDK includes several improvements over the original implementation:

### 1. Shared Tool Execution Logic
- Extracted common tool execution flow into `base.Runtime`
- Consistent message format across local and temporal runtimes

### 2. Token Budget Enforcement
- `WithMaxTokens(n int64)` option to limit cumulative token usage
- Automatic stopping when budget exceeded

### 3. Typed Error Classification
- `ToolExecutionError` distinguishes fatal (infrastructure) from non-fatal (business) errors
- Better logging and retry decisions

### 4. Tool Output Truncation
- `MaxToolOutputTokens` to prevent context overflow
- Automatic truncation with word-boundary awareness

### 5. Deterministic Activity IDs
- Predictable IDs for better debugging and idempotency
- Format: `prefix_runID_iteration[_extra]`

### 6. Retry Policies
- Optimized retry policies for different operation types
- LLM calls: 10 attempts with exponential backoff
- Tool execution: 3 attempts

### 7. TTL-Based Approval Store
- Automatic cleanup of expired approval tokens
- Prevents memory leaks from unresolved approvals

### 8. Structured Output Validation
- JSON validation for structured output formats
- Schema validation for required fields

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          Agent Layer                         │
│  Run() | Stream() | RunAsync() | Close()                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                        Runtime Layer                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   Local Runtime     │    │    Temporal Runtime          │ │
│  │   (in-process)      │    │    (distributed)             │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                      Infrastructure                          │
│  LLM Providers | Memory | Tools | Observability             │
└─────────────────────────────────────────────────────────────┘
```

## License

MIT
