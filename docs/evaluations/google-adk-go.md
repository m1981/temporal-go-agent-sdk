# Evaluation dossier: github.com/google/adk-go @ 0c88126

> Reader: SDK contributors deciding what to borrow, avoid, or position against | Enables: borrow/avoid decisions with pinned evidence; feeds PAT entries and ADR-011 | Update-trigger: re-evaluation at a new upstream release, or a cited finding challenged

Evaluated 2026-07-11 at commit `0c88126` (module `google.golang.org/adk/v2`;
no git tags, no CHANGELOG). All citations are `file:line` at that SHA.
Evidence class: VERIFIED(subagent code-read at 0c88126) unless marked
otherwise. Local clone: `/Users/michal/PycharmProjects/agent-eval/adk-go`.

## Identity

Google's Gemini-only agent kit: ONE provider-agnostic-shaped loop
(`internal/llminternal/base_flow.go:103`) but only Gemini registered
(anthropic/openai/ollama greps = 0; Vertex is a genai backend variant
`googlellm/variant.go:38`; apigee delegates to gemini `apigee.go:45`).
`iter.Seq2[*session.Event, error]` event streams end-to-end
(`agent/agent.go:46`). Two execution engines: the LLM Flow loop and a durable
graph engine (`workflow/scheduler.go:74`) with per-node retry(5×)/timeout/
max-concurrency. Resume is reconstructed from the session event log at
HITL/long-running-tool pause boundaries (`workflow/persistence.go:80-116`) —
no serialized run blob; mid-step crash loses the step. A2A client+server;
MCP client only; REST + Vertex Agent Engine deploy CLI (`cmd/adkgo`).

## P0 findings (avoid list)

1. **Unbounded core loop** (AP-01/AP-08): no max-iteration, token, or cost
   enforcement in `Flow.Run`; termination is solely `IsFinalResponse`
   (`session/session.go:212`); `LoopAgent.MaxIterations=0` means infinite
   (`loopagent/agent.go:33,97`).
2. **System-prompt injection** (AP-05, worst variant): session-state and
   artifact values template-expanded verbatim into system instructions — only
   the variable NAME is validated (`instruction_processor.go:143,146,163`).
3. **Panic stack traces sent to the model** (AP-05): functiontool recovers
   panics and folds `debug.Stack()` into the error string
   (`functiontool/function.go:187-191`) which flows to
   `{"error": err.Error()}` → `FunctionResponse` (`base_flow.go:1275,1179`).
   Telemetry serializes full tool responses into span attributes
   unconditionally (`internal/telemetry/telemetry.go:158-182`).
4. **No history bounding, no per-tool timeout** (AP-08/AP-09): full
   branch-filtered event history into every request
   (`contents_processor.go:63`; summarize/truncate greps = 0); only plugin
   shutdown has a timeout (`runner/runner.go:63`).
5. **Shared-session transfer** (AP-10): `transfer_to_agent` runs the target
   inline on the same ctx/session (`base_flow.go:663-684`); Parallel gives
   fresh branch contexts but shared Session/Artifacts/Memory
   (`parallelagent/agent.go:83-92`). HITL confirmation exists but is
   default-allow and EXPERIMENTAL (`tool/tool.go:126,136,210`).

## Worth borrowing (see PAT entries)

- **Typed FunctionResponse envelopes** — results enter model contents as
  structured `genai.FunctionResponse{Response: map[string]any}` parts, not
  string concatenation (`base_flow.go:1179-1183`). → PAT-003.
- **Injectable time/UUID for replay-safe events** — `platform.Now(ctx)` /
  `platform.NewUUID(ctx)` with provider overrides (`platform/time.go:34`,
  `session/session.go:226-232`). → PAT-004.
- **Event-log-derived HITL resume** — interrupts persisted as events;
  `ReconstructRunState` re-derives paused state by scanning history
  (`persistence.go:80-116`, `run_node.go:132-141`). Lighter-weight cousin of
  Temporal replay; informs our signal/approval design. → PAT-005.
- **Request-processor pipeline** — instructions/contents/tools assembled by
  ordered processors over `*LLMRequest` (`instruction_processor.go:41`,
  `contents_processor.go:37`, `tools_processor.go:28`). → PAT-006.
- **`iter.Seq2` event-stream spine** (`agent/agent.go:46`) and the graph
  engine's per-node Timeout/Retry/MaxConcurrency
  (`workflow/config.go:81,110`, `workflow.go:191`) as API-shape references
  for our pipeline-step layer (wk-0bdbd4e4). → PAT-007.
- **Generics function-tool with derived JSON schema** —
  `functiontool.New[TArgs,TResults]` + `jsonschema.For[T]`
  (`functiontool/function.go:79,272`). → PAT-008.

## Verdict

Best execution skeleton of the evaluated set, undermined by an unbounded loop
and the widest injection surface; Gemini-only is architectural (live/bidi,
caching, telemetry all assume genai types). Design reference — the strongest
one — not an adoption candidate unless all-in on GCP.

## Unknowns

Whether `platform.RunTasks` recovers panics from non-functiontool tools;
whether classic Sequential/Parallel/Loop roots participate in resume; whether
span content-capture can be filtered downstream; per-call-site confirmation
defaults.
