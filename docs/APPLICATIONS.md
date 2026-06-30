# Applications You Can Build With This SDK

Based on the codebase analysis, here are the practical applications:

---

## 1. Durable Customer Support Agent

```go
// Survives crashes, resumes conversations
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithTools(knowledgeBase, ticketSystem, emailTool),
    agent.WithMemory(memoryConfig),
    agent.WithTemporalConfig(temporalCfg),
    agent.WithMaxTokens(500000),  // Token budget
)

// Customer asks complex question, agent:
// 1. Searches knowledge base
// 2. Creates support ticket
// 3. Sends follow-up email
// 4. If server crashes mid-way → resumes from exact point
result, _ := agent.Run(ctx, "My order #12345 hasn't arrived", nil)
```

**Why Temporal matters:** Customer requests that take 10+ minutes (searching docs, checking databases, sending emails) survive server restarts.

---

## 2. Multi-Step Code Review Pipeline

```go
// Sub-agents for different review aspects
reviewerAgent, _ := agent.NewAgent(
    agent.WithLLM(claudeClient),
    agent.WithSubAgents(
        securityAgent,    // Checks for vulnerabilities
        performanceAgent, // Finds bottlenecks
        styleAgent,       // Code style issues
    ),
)

result, _ := reviewerAgent.Run(ctx, "Review PR #456", nil)
// Parent agent delegates to sub-agents, collects results
```

**Use cases:**
- CI/CD integration
- Automated PR reviews
- Security scanning

---

## 3. Financial Report Generator

```go
// Long-running analysis that MUST complete
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithTools(
        databaseQuery,
        spreadsheetGenerator,
        pdfCreator,
        emailSender,
    ),
    agent.WithMaxIterations(50),  // Complex multi-step
    agent.WithTemporalConfig(temporalCfg),
)

// Process takes 2 hours:
// 1. Query 10 databases
// 2. Aggregate data
// 3. Generate charts
// 4. Create PDF report
// 5. Email to stakeholders
// Temporal ensures it completes even with failures
result, _ := agent.Run(ctx, "Generate Q4 financial report", nil)
```

---

## 4. Real-Time Streaming Chatbot (AG-UI)

```go
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithTools(searchTool, calculatorTool),
    agent.WithStream(true),  // AG-UI protocol
)

// Stream events to frontend
stream, _ := agent.Stream(ctx, "Explain quantum computing", nil)

for event := range stream {
    switch event.Type() {
    case events.AgentEventTypeTextMessageContent:
        // Real-time token streaming to UI
        sendToFrontend(event.Content)
    case events.AgentEventTypeToolCallStart:
        // Show "Searching..." in UI
        showToolIndicator(event.ToolName)
    }
}
```

**Frontend integration:**
- React/Vue/Svelte apps
- WebSocket connections
- Real-time tool status

---

## 5. Human-in-the-Loop Approval System

```go
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithTools(deployTool, deleteDatabaseTool),
    agent.WithApprovalHandler(func(ctx context.Context, req *types.ApprovalRequest) {
        // Send Slack notification
        sendSlackMessage("Agent wants to: " + req.Value.ToolName)
        // Wait for human approval
        req.Respond(types.ApprovalStatusApproved)
    }),
)

// Agent asks before dangerous operations
result, _ := agent.Run(ctx, "Deploy v2.1 to production", nil)
```

**Use cases:**
- Production deployments
- Financial transactions
- Database modifications
- Legal document signing

---

## 6. RAG-Powered Document Assistant

```go
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithMemory(memoryConfig),  // pgvector or Weaviate
    agent.WithRetrievers(
        companyDocsRetriever,
        legalDocsRetriever,
    ),
)

// Agent searches documents, remembers context
result1, _ := agent.Run(ctx, "What's our vacation policy?", nil)
result2, _ := agent.Run(ctx, "How does it compare to industry standard?", nil)
// Remembers previous context from memory
```

---

## 7. Automated Data Pipeline

```go
// Multi-agent system for ETL
orchestrator, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithSubAgents(
        extractorAgent,    // Pulls from APIs
        transformerAgent,  // Cleans/transforms data
        loaderAgent,       // Loads to data warehouse
        validatorAgent,    // Checks data quality
    ),
    agent.WithTemporalConfig(temporalCfg),
)

// Process 1000 files over several hours
result, _ := orchestrator.Run(ctx, "Process all CSV files from S3", nil)
```

---

## 8. MCP-Integrated Agent

```go
// Connect to external tools via MCP
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithMCPConfig(mcp.Config{
        Servers: []mcp.ServerConfig{
            {Name: "filesystem", Command: "mcp-filesystem"},
            {Name: "github", Command: "mcp-github"},
            {Name: "slack", Command: "mcp-slack"},
        },
    }),
)

// Agent can access files, GitHub, Slack
result, _ := agent.Run(ctx, "Find the bug report from yesterday and fix it", nil)
```

---

## 9. A2A (Agent-to-Agent) Federation

```go
// Agents communicate across services
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithA2AConfig(a2a.Config{
        Peers: []a2a.PeerConfig{
            {URL: "http://inventory-service:8080"},
            {URL: "http://shipping-service:8080"},
        },
    }),
)

// Agent delegates to remote agents
result, _ := agent.Run(ctx, "Check stock and arrange shipping for order #789", nil)
```

---

## 10. Observability & Monitoring Agent

```go
// Built-in OpenTelemetry
agent, _ := agent.NewAgent(
    agent.WithLLM(openaiClient),
    agent.WithObservabilityConfig(observability.Config{
        Tracer:  otelTracer,
        Metrics: otelMetrics,
        Logs:    otelLogs,
    }),
)

// Every LLM call, tool execution is traced
// Metrics exported to Grafana/Datadog
result, _ := agent.Run(ctx, "Analyze error rates", nil)
```

---

## Architecture Patterns

| Pattern | Use Case | Example |
|---|---|---|
| **Sequential** | Simple tasks | "Summarize this document" |
| **Parallel tools** | Fast execution | "Search 5 databases simultaneously" |
| **Sub-agents** | Complex workflows | "Review code (security + style + perf)" |
| **Temporal** | Long-running | "Process 10,000 files" |
| **Streaming** | Real-time UI | "Chat interface with token streaming" |
| **Human-in-loop** | Approval flows | "Deploy to production" |
| **Memory** | Conversational | "Remember user preferences" |

---

## Quick Start Examples

```bash
# Clone the repo
git clone https://github.com/m1981/temporal-go-agent-sdk.git
cd temporal-go-agent-sdk

# Run simple agent
go run examples/simple_agent/main.go

# Run with tools
go run examples/agent_with_tools/basic/main.go

# Run with streaming
go run examples/agent_with_stream/main.go

# Run with sub-agents
go run examples/agent_with_subagents/main.go

# Run with Temporal (durable)
go run examples/agent_with_temporal_client/main.go
```

---

## What Makes This SDK Unique

| Feature | This SDK | LangChain | AutoGen |
|---|---|---|---|
| **Crash recovery** | ✅ Temporal | ❌ | ❌ |
| **Streaming protocol** | ✅ AG-UI | ⚠️ Custom | ⚠️ Custom |
| **Token budget** | ✅ Built-in | ❌ | ❌ |
| **Typed errors** | ✅ Fatal vs Business | ❌ | ❌ |
| **Tool output limits** | ✅ Automatic | ❌ | ❌ |
| **Deterministic IDs** | ✅ Yes | ❌ | ❌ |

**Bottom line:** This SDK is designed for **production systems** that need durability, observability, and reliability.
