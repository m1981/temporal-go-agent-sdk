# Evaluation dossier: github.com/Ingenimax/agent-sdk-go @ 71a421c

> Reader: SDK contributors deciding what to borrow, avoid, or position against | Enables: borrow/avoid decisions with pinned evidence; feeds PAT entries and ADR-011 | Update-trigger: re-evaluation at a new upstream release, or a cited finding challenged

Evaluated 2026-07-11 at commit `71a421c` (v0.0.36 era; 36 tags, no CHANGELOG).
All citations are `file:line` at that SHA. Evidence class: VERIFIED(subagent
code-read at 71a421c) unless marked otherwise. Local clone:
`/Users/michal/PycharmProjects/agent-eval/agent-sdk-go`.

## Identity

General-purpose breadth-first agent framework: 7 LLM providers, MCP client AND
server, A2A both directions, gRPC remote agents, GraphRAG (Weaviate), YAML
agent config, OTEL+Langfuse. No durable execution of any kind (greps for
temporal/cadence/restate/inngest/dbos = 0; `pkg/interfaces/task.go:79` doc
comments mention temporal workflows that do not exist — doc–code divergence).

## P0 findings (avoid list)

1. **The agent loop lives inside each LLM provider — seven hand-written
   copies** (AP-13). `pkg/llm/openai/client.go:561`,
   `pkg/llm/anthropic/client.go:1087`, plus gemini/azureopenai/deepseek/
   ollama/vllm. Already diverged: OpenAI parallel tool path aborts on error
   (`openai/client.go:777`) while the serial path continues (`:943`).
2. **Tool execution effectively ungated** (AP-12). No per-tool approval;
   `ToolRestriction` guardrail is a regex on prompt text
   (`pkg/guardrails/tool_restriction.go:22`) never wired to Execute; the
   agent's `WithGuardrails` hook (`pkg/interfaces/guardrails.go:6`,
   ProcessInput/ProcessOutput) has NO in-repo implementation — the shipped
   guardrails.Pipeline implements a different interface. Only real gate:
   coarse whole-plan approval, default-on (`pkg/agent/agent.go:632,970`).
3. **Prompt injection** (AP-05): tool results verbatim, errors as raw
   `fmt.Sprintf("Error: %v", err)` in every provider
   (`openai/client.go:812,943`; `anthropic/client.go:2122`).
4. **No run bounds, no durability** (AP-08): maxIterations default 2
   (`openai/client.go:436`, `agent.go:633`) is the only loop bound; no
   token/cost cap (usage tracked in `pkg/agent/usage_tracker.go`, never
   enforced); no recover() around synchronous Execute; no per-tool timeout;
   crash loses the run.
5. **Subagent memory sharing** (AP-10): config-built subagents inherit the
   parent's memory instance (`agent.go:1953-1955`).
6. The anti-loop guard appends `[WARNING: ... You may be in a loop]` to tool
   results — the invariant is delegated to the model (AP-01)
   (`openai/client.go:871`).

## Worth borrowing (see PAT entries)

- **LLM summarization-compaction of history**: `ConversationSummary`
  (`pkg/memory/conversation_summary.go:76-84,161`), plus Redis LTrim caps and
  1 MB message cap (`factory.go:81`). → PAT-001.
- **Traced-decorator observability**: `NewTracedLLM`/`TracedMemory` wrap the
  interfaces (`pkg/tracing/traced_llm.go:19`), Langfuse over OTEL
  (`langfuse.go:14`). → PAT-002.
- Roadmap signal, not design: MCP **server** exposure (`pkg/mcp/mcp.go:114,718`)
  and provider breadth (Bedrock/Vertex as Anthropic/Gemini backends).

## Verdict

Breadth reference and cautionary tale: do not import anything from its
execution core. Its two genuinely good subsystems (memory compaction, traced
decorators) are detachable designs, not code dependencies.

## Unknowns

Whether requirePlanApproval=true survives all construction paths; post-approval
resume wiring end-to-end; streaming-path append semantics (partially read).
