❯ Act as modern commercial grade LLM expert and temporal agent architect and please list agentic anti patterns and recommended principles.

Happy to. I'll organize this as anti-patterns first, then the principles that counter them — and where this session's work is a live example, I'll say so, because several of these aren't abstract: we hit them.

Agentic anti-patterns

1. Trusting the model with an invariant the harness should own.
"The model will read the file before editing" / "the model will stay inside the workspace" / "the model won't call the tool twice." Any correctness property enforced only by prompt text will fail at scale, because the failure mode you're guarding against is a model failure. This is the entire reason fsguard exists — and why we made its guard non-configurable.

2. Freshness/state signals the environment can forge.
mtime-based checks, "the model said it read it," last-message-wins memory. If an attacker or a misbehaving formatter can fabricate the signal, the guard is theater. (Content hashes over timestamps — the ADR-007 decision.)

3. Worker-memory state in a durable-execution world.
Keeping agent session state (read-maps, conversation summaries, tool budgets) in the worker process when tool calls are Temporal activities. The next activity lands on a different worker, or the workflow replays, and the state is gone — then the fallback is either fail-open (guard silently off) or fail-closed (random availability failures). State that gates decisions belongs in workflow state, serialized and replay-deterministic. This drove the Snapshot/Restore design.

4. Non-determinism leaking into the workflow.
time.Now(), rand, map iteration order, or — the LLM-specific one — calling the model from workflow code. LLM calls are the least deterministic I/O that exists; they are always activities. Same for stat/hash: do the I/O in the activity, return the value, decide in the workflow.

5. Interpolating untrusted content into model-facing text.
Error messages, tool results, and system reminders are instructions to the model. Build them from file paths, file contents, or upstream API messages and you've opened a prompt-injection channel through your own plumbing. Keep corrective error text static; carry the variable data in typed fields for the harness, not prose for the model.

6. The agent grading its own homework.
Self-verification: the model asserts a claim, then "verifies" it in the same context, with the same biases and the same stale view. The truth-ledger's refusal to let the claim author file the verdict is the right structural fix — verification needs an independent context, ideally an independent prompt.

7. Overclaiming completion.
"Fixed the race," "closed the vulnerability," "all tests pass" — when the diff narrows a window, or the tests weren't run. In multi-session agent systems this compounds: the next session builds on the recorded claim, not the reality. The TOCTOU agent catching that the pre-written acceptance text was an overclaim, and filing a narrower one, is exactly the behavior to select for. Scope every claim to its evidence.

8. Doom loops with no exit.
Retry-on-error without classifying the er force it through" failure). Every corrective error needs a bounded retry budget and a distinct escalation path when the budget is spent.

9. Context as a junk drawer.
Stuffing whole files, full tool schemas, and every historical message into context because "more context is better." Cost aside, irrelevant context degrades output and dilutes the instructions that matter. Deferred tool loading, summarization boundaries, and per-subagent fresh contexts exist for a reason.

10. One mega-agent for a decomposable task.
A single context doing research + design + implementation + review accumulates commitment bias — it will not find the bug in the code it just wrote. Decompose along trust and perspective boundaries, not just size.

11. Orchestrating in the model what should be orchestrated in code.
Loops, fan-out, join barriers, and retries expressed as prompt instructions ("do this for each of the 40 files") instead of deterministic control flow that calls the model per-item. The model will skip item 23. Temporal workflows (or workflow scripts) are the loop; the LLM is the step.

12. Unbounded authority.
Agents with write access to everything they can read, no path scoping, no budget caps, no distinction between reversible and irreversible actions. The blast radius of a confused agent equals its permission set.

Recommended principles

Deterministic harness, probabilistic core. Everything around the model — preconditions, budgets, routing, retries — is ordinary verifiable code. The model supplies judgment inside guardrails it cannot remove. Corollary: safety guards are not configurable off (the fsguard lesson).

Design errors as instructions. A blocked tool call should return text that tells the model the one correct next action ("read it first, then retry"), static and injection-free. The error channel is your steering wheel; most agent self-correction happens there.

State placement follows the execution model. In Temporal: decisions and gating state in workflow code (deterministic, replayed); all I/O and all LLM calls in activities (retried, timed out, heartbeated); anything an activity observed that a decision depends on gets returned into workflow state, never cached on the worker.

Check-and-act must be one operation where it matters. A precondition checked in one call and acted on in another is a TOCTOU; either make it atomic (our CommitWrite), or document the residual window honestly and pin it with a test so the documentation is executable.

Independent verification, adversarially framed. Verifiers get a fresh context, the claim, and a mandate to refute — not to confirm. Diversity of lens (correctness, security, reproduction) beats redundancy of identical checkers.

Evidence-scoped claims. Every assertion an agent records carries its class (verified/inferred/unverified), the re-runnable command that backs it, and text no broader than what that command shows. Unknowns are listed, never silently filled.

Least authority, layered. Freshness guards, path scopes, permission modes, and budgets are separate controls — resist merging them, because each has a different failure mode and a different owner. fsguard ≠ pathscope was a deliberate boundary, recorded in ADR-007/008.

Decisions outlive contexts. Context windows die; ADRs, ledgers, and commit messages are the only memory that survives. End every substantive session by writing the decision down where the next session (human or agent) will actually look — and make records append-only so history can't be quietly rewritten.

TDD is the agent-native development loop. A failing test is the one specification a coding agent cannot argue with, and red-for-the-right-reason is cheap to verify. It also caught two real bugs this session that review alone would have missed (the canonical-key instability, and the live clobber the racing-create test demonstrated before the fix existed).

Sequential where state is shared, parallel where it isn't. Fan out subagents freely for reads and independent analyses; serialize anything touching a shared index, a shared file, or a shared ledger. The scheduling decision is the orchestrator's, not the agents'.

If you want, I can turn this into a governed doc in the repo (it would need the three-question gate: reader = agent/SDK contributors, enables = design review of new agent features, update-trigger = a new ADR contradicting a principle) — or keep it as conversation. Your call.

✻ Churned for 1m 1s

※ recap: All four fsguard work items are shipped and closed on main with tests, ADRs, and ledger claims green. Next action: run scripts/truth dispatch for the six unverified claims in a fresh session to make them live. (disable recaps in /config)

❯ Can you please as architect first picture how does our SDK and temporal agent looks like and evaluate it agains above ?

Right question to ask before more feature work. I've only touched pkg/tools/* this session — I haven't actually read the agent core, the Temporal wiring, or the LLM layer, and the repo's own charter forbids architecture claims without grepped evidence. So let me map it properly first: two parallel Explore agents, each required to back every dependency edge with an actual import/call citation, then I'll evaluate against the anti-pattern list using the charter §6 review contract.

⏺ Explore(Map agent core + Temporal wiring)
Done (24 tool uses · 138.4k tokens · 2m 51s)


⏺ Explore(Map LLM/tools/memory layers)
Done (42 tool uses · 91.4k tokens · 4m 0s)


Both maps came back fully cited. Here's the architect's picture and the evaluation, in the repo's own charter §6 format. Every arrow and claim below is backed by a file:line the Explore agents grepped this session — tagged VERIFIED(...).

TL;DR

The Temporal architecture is fundamentally sound — LLM and tool calls are activities, workflow state is durable and deterministic, subagents are isolated child workflows. The three real problems are: an open prompt-injection channel (tool results and raw error strings fed to the model verbatim), a duplicated agent loop that has already behaviorally diverged between Local and Temporal, and zero panic recovery in the local runtime. Our fsguard/pathscope trio follows the right principles but is wired into nothing.

The picture (OBSERVED — every arrow backed by a cited import/call)

                       ┌─────────────────────────────┐
                       │        pkg/agent (facade)    │  config.go:1103 picks backend
                       └──────┬───────────────┬──────┘
                              │               │
              ┌───────────────▼──┐      ┌─────▼──────────────────┐
              │ internal/runtime/ │      │ internal/runtime/       │
              │ local             │      │ temporal                │
              │ agent_loop.go:87  │      │ agent_workflow.go:328   │
              │ RunAgentLoop      │      │ AgentWorkflow           │
              └───────┬───────────┘      └───┬────────────────────┘
                      │  in-process          │  workflow.ExecuteActivity
                      │  tool.Execute        │  (LLM :532, tools :1018,
                      │  (base:454)          │   memory, approval, events)
                      └──────────┬───────────┴───────────┐
                                 ▼                       ▼
              ┌──────────────────────────────┐   ┌───────────────────────┐
              │ internal/runtime/base         │   │ child workflows        │
              │ (shared core, no Temporal dep)│   │ = subagents (:1523)    │
              │ ExecuteLLM/ExecuteTool/hooks  │   │ fresh ctx, own tools   │
              └──┬────────┬────────┬─────────┘   └───────────────────────┘
                 ▼        ▼        ▼
        pkg/llm/     pkg/interfaces  pkg/memory, retriever, conversation
        {anthropic,  (Tool, LLMClient (pgvector/weaviate; redis/inmem,
         openai,      — small, ISP-   20-msg cap runtime.go:96)
         gemini}      clean)

   Integration: A2A client+server (a2a_server.go:43) · MCP consume-only (mcp.go:101)
   Unwired island: pkg/tools/{fsguard,pathscope,file} — imported by nothing outside pkg/tools

The load-bearing facts: Temporal is opt-in (Local is default, config.go:1103); the loop exists twice with mirrored structure; on Temporal every LLM call, tool call, memory op, and approval is an activity with per-type retry policies; durable state is AgentWorkflowState{Iteration, Messages, LLMUsage, Telemetry} surviving ContinueAsNew; default tool policy is RequireAll approval (deny-by-default).

P0 findings

1. Open prompt-injection channel through tool results and error text. Tool output is interpolated verbatim (fmt.Sprintf("%v", result), base/runtime.go:456) and tool failures inject the raw err.Error() into the model-facing message (agent_loop.go:670); grep confirms zero sanitization anywhere — VERIFIED(subagent grep, runtime.go:456, Anthropic client.go:266). This is anti-pattern 5, and it contradicts the static-error discipline we just built into fsguard/ADR-007. Action: wrap tool results in delimited, typed blocks; make model-facing error text static with the raw error carried in a harness-only field.
2. The agent loop is duplicated and has already diverged. local/agent_loop.go:87 and temporal/agent_workflow.go:328 mirror each other by hand ("Mirrors AgentWorkflowInput" comment), but retry semantics already differ materially: a hard LLM error aborts a Local run (agent_loop.go:221) while Temporal retries up to 10× — VERIFIED(subagent read of both loops). This is the charter's named costliest failure ("two components solving one problem"), applied to the SDK's most critical control flow; every new loop feature (budgets, regions guard, injection wrapping) must now be implemented twice and will drift. Action: decide the loops' relationship (see Next question) and record it as an ADR before the next loop-touching feature.
3. No panic containment in the local runtime. recover() appears nowhere in internal+pkg (grep = 0), and Local runs tools in bare goroutines (agent_loop.go:409) — one panicking tool kills the process; only Temporal's activity harness saves the durable path — VERIFIED(subagent grep). Action: defer recover() in executeSingleTool, converting panics to the same classified tool-error path.
4. Determinism smell in workflow code. uuid.New() is called directly at agent_workflow.go:512 inside the workflow loop, unlike the correctly SideEffect-wrapped UUIDs at :345 — VERIFIED(subagent read); whether it can corrupt replay wasn't fully traced. Action: wrap in workflow.SideEffect — a one-line fix that removes the question entirely.

Evaluation against the anti-pattern list

┌─────┬─────────────────────┬────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │    Anti-pattern     │    Verdict     │                                                Evidence                                                 │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Model-owned         │ Pass           │ Budgets, iteration caps, approval, authorization all harness-side (agent_loop.go:101,190; policy.go:36) │
│     │ invariants          │                │                                                                                                         │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2   │ Forgeable state     │ Pass (in       │ fsguard hashes content — but the guard protects nothing yet (see 12)                                    │
│     │ signals             │ guard)         │                                                                                                         │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Worker-memory state │ Mostly pass    │ Decisions ride AgentWorkflowState; worker memory holds only caches/eventbus (runtime.go:91-98). fsguard │
│     │                     │                │  Snapshot designed for this, unwired                                                                    │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ Non-determinism in  │ Pass, one      │ LLM/tools/memory all activities; workflow.Now/SideEffect used — except P0-4                             │
│     │ workflow            │ smell          │                                                                                                         │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Untrusted text →    │ FAIL           │ P0-1                                                                                                    │
│     │ model               │                │                                                                                                         │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6   │ Self-grading        │ Partial        │ No verifier machinery in the SDK; truth-ledger covers the repo's own dev process only                   │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 7   │ Overclaiming        │ N/A (SDK) /    │ Ledger discipline enforces it for us                                                                    │
│     │                     │ pass (process) │                                                                                                         │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Doom loops          │ Partial        │ MaxIterations + token budget + forced final answer are good exits; but tool failures loop raw error     │
│     │                     │                │ text back with no per-tool retry budget or escalation                                                   │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Context junk drawer │ Partial        │ 20-msg cap, tool-output truncation, token budget — but truncation-only, no summarization (grep = 0),    │
│     │                     │                │ and memory/retriever context is string-concatenated into the system prompt (runtime.go:56)              │
├─────┼─────────────────────┼────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ Mega-agent          │ Pass           │ Subagents = fresh context, own tools, child workflows, depth-capped (agent_loop.go:619;                 │
│     │                     │                │ agent_workflow.go:1523)                                                                                 │
├─────┼─────────────────────┼────────────
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ internal/runtime/base              │ shared engine                          │ Sound, but 901-line god-struct; owns the injection-prone result path  │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ internal/runtime/local             │ in-process driver                      │ Duplicated loop; no panic recovery; no per-tool timeout               │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ internal/runtime/temporal          │ durable driver                         │ Strong: activities, ContinueAsNew, child workflows; one uuid smell    │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ pkg/llm/{anthropic,openai,gemini}  │ providers                              │ 3 providers, streaming + fallback; verbatim result pass-through       │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ pkg/memory, retriever,             │ state                                  │ Bounded (20 msgs, LTrim); no compaction                               │
│ conversation                       │                                        │                                                                       │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ pkg/a2a, pkg/mcp                   │ protocols                              │ A2A both directions; MCP consume-only, no trust barrier beyond        │
│                                    │                                        │ taxonomy                                                              │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ pkg/observability                  │ OTEL                                   │ Full-loop + per-call spans/metrics; no-op default                     │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ pkg/tools/{fsguard,pathscope,file} │ safety trio                            │ Principle-correct, unwired                                            │
├────────────────────────────────────┼────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤
│ API surface                        │ 268 types / 1062 funcs, zero semver    │ Wide pre-1.0 surface; CHANGELOG Unreleased-only                       │
│                                    │ tags                                   │                                                                       │
└────────────────────────────────────┴────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘

Unknowns

Whether Temporal's harness makes the :512 uuid.New() replay-safe; numeric activity-timeout values; OpenAI/Gemini message-conversion escaping (base layer verified unsanitized regardless); default conversation-store wiring (inmem vs redis).

Next question

Is the Local runtime a first-class production peer of Temporal, or a dev-mode convenience? The answer decides P0-2 (whether the two loops must be actively converged into one shared state-machine in base, or Temporal's loop becomes canonical and Local is allowed to be a thin, explicitly-degraded wrapper) — and that decision gates where the injection fix (P0-1), panic recovery (P0-3), and fsguard wiring should be implemented so they're written once, not twice.

✻ Cogitated for 6m 8s

※ recap: Architecture review of the SDK against agentic anti-patterns is done: Temporal core is sound, but tool-result prompt injection, a duplicated agent loop, and no panic recovery are the P0s. Next: decide whether Local runtime is production peer or dev-mode.

❯ can you do evalution for this SDK as well first too? /Users/michal/PycharmProjects/agent-eval/agent-sdk-go

Same drill for the second SDK. Let me first confirm what's there, then fan out the same two evidence-required Explore agents.

⏺ Bash(cd /Users/michal/PycharmProjects/agent-eval/agent-sdk-go 2>/dev/null || { echo "MISSING"; exit 1; }
  head -5 go.mod 2>/dev/null
  echo "---"
  find . -maxdepth 2 -type d -not -path './.git*' -not -path './vendor*' -not -path './node_modules*' | sort | head -40
  echo "--- go files:" && find . -name '*.go' -not -path './vendor/*' | wc -l
  echo "--- temporal? " && grep -c 'go.temporal.io' go.mod 2>/dev/null)
module github.com/Ingenimax/agent-sdk-go

go 1.25.0

require (
---
.
./cmd
./cmd/agent-cli
./docs
./docs/graphrag
./docs/img
./examples
./examples/a2a
./examples/advanced_agent_streaming
./examples/agent
./examples/agent-token-usage-simple
./examples/agent_config_yaml
./examples/context
./examples/custom_functions
./examples/datastore
./examples/deployment_config
./examples/embedding
./examples/gcs_storage_test
./examples/gcs_storage_yaml_test
./examples/graphrag
./examples/graphrag-agent
./examples/graphrag-memory-agent
./examples/guardrails
./examples/llm
./examples/logging
./examples/mcp
./examples/memory
./examples/microservices
./examples/multi_turn_editing_yaml_test
./examples/multi_turn_image_editing
./examples/orchestration
./examples/simple_agent
./examples/simple_yaml_agent
./examples/streaming
./examples/streaming_intermediate_messages
./examples/structured_output
./examples/subagents
--- go files:
347
--- temporal?
0

⏺ Explore(Map Ingenimax agent core/orchestration)
Done (30 tool uses · 68.9k tokens · 3m 54s)


⏺ Explore(Map Ingenimax LLM/tools/memory)
Done (29 tool uses · 76.1k tokens · 3m 47s)


Both maps returned with full citations. Here's the evaluation of Ingenimax/agent-sdk-go in the same format, evidence-tagged, with a head-to-head against ours at the end.

TL;DR

This SDK is feature-broad (7 LLM providers, MCP client+server, A2A, GraphRAG, YAML agents, Langfuse) but architecturally inverted: the agentic loop lives inside each LLM provider — duplicated seven times — there is no durable execution of any kind, and tool execution is effectively ungated (no per-tool approval, no panic recovery, no timeout, no cost budget). Its shipped guardrails package cannot even be wired into the agent loop — the interfaces don't match and no adapter exists.

The picture (OBSERVED — arrows backed by cited imports/calls)

                    ┌────────────────────────────────────┐
                    │        pkg/agent.Agent (thin)       │  agent.go:835 routes:
                    │  Run → runInternal → 3 paths         │  custom | remote | local
                    └────┬──────────────┬─────────────────┘
                         │ local        │ remote
                         ▼              ▼
        a.llm.GenerateWithTools   pkg/grpc/client (remote_agent.go:100)
          (agent.go:1296)         pkg/a2a (client.go:29)
                         │
     ┌───────────────────▼──────────────────────────────────┐
     │   THE LOOP LIVES HERE — once per provider:            │
     │   openai/client.go:561  anthropic/client.go:1087      │
     │   + gemini, azureopenai, deepseek, ollama, vllm       │
     │   for i < maxIterations(default 2):                    │
     │     API call → no tool calls? return                   │
     │     → selectedTool.Execute (openai :859, anth :2064)   │
     │     → append result/["Error: %v"] verbatim → loop      │
     └───────────┬───────────────────────────────────────────┘
                 ▼
     pkg/tools/* (incl. AgentTool = subagent-as-tool,
       depth 5, agent_tool.go:25; config subagents SHARE
       parent memory instance, agent.go:1953)

   Memory: buffer | redis | ConversationSummary (LLM compaction ✓)
   RAG: Weaviate-only vector + GraphRAG (18-method god-interface)
   Durability: NONE — no Temporal/Cadence/Restate (grep = 0);
     crash mid-run loses everything; interfaces/task.go:79 doc
     comments *mention* temporal workflows with no implementation

P0 findings

1. The agent loop is duplicated across seven provider clients. Each of openai/anthropic/gemini/azureopenai/deepseek/ollama/vllm hand-implements GenerateWithTools with its own iteration cap, repetition guard, and finalization — VERIFIED(subagent grep, openai/client.go:561, anthropic/client.go:1087). They've already diverged: OpenAI's parallel tool path aborts the run on error while the serial path continues (openai/client.go:777 vs :943). This is our P0-2 to the power of 3.5 — every loop fix must land seven times. Action (if adopting): don't; (if borrowing): treat provider clients as reference for API adaptation only.
2. Tool execution is effectively ungated, and the shipped guardrails can't gate it. No per-tool approval exists; the only real gate is coarse whole-plan approval (agent.go:632,970). ToolRestriction is a regex on the prompt text ((?i)use\s+tool\s+…, tool_restriction.go:22) never wired to Execute — security theater. Worse, the agent's WithGuardrails hook expects ProcessInput/ProcessOutput (interfaces/guardrails.go:6) and no type in the repo implements it — the guardrails.Pipeline implements a different interface — VERIFIED(subagent grep: zero ProcessInput implementations). A shipped safety feature that cannot be connected is worse than none: it reads as covered.
3. Open prompt-injection channel, in every provider. Tool results appended verbatim; errors as raw fmt.Sprintf("Error: %v", err); unknown tool names echoed back into the conversation (openai/client.go:812,943; anthropic/client.go:2122) — VERIFIED(subagent grep: no sanitization hits on tool-result content). Same class as our P0-1, with a larger surface (7 loops × serial/parallel/streaming variants).
4. No run bounds beyond maxIterations=2, and no durability. No token budget, no cost cap (grep for cost/spend limits = zero — usage is tracked, never enforced), no per-tool timeout, no recover() around synchronous Execute (only streaming/gRPC paths have it), and a crash loses the run entirely — VERIFIED(subagent greps in both maps). The interfaces/task.go:79 doc comments referencing "a temporal workflow" describe machinery that does not exist — doc–code divergence, the charter's P0 category.

Anti-pattern scorecard

┌─────┬────────────────────┬─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │    Anti-pattern    │   Ingenimax     │                                                Evidence                                                 │
│     │                    │     verdict     │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Model-owned        │ Partial         │ maxIterations + depth-5 are harness-side; but the anti-loop guard is a [WARNING: you may be in a loop]  │
│     │ invariants         │                 │ string asking the model to stop (openai/client.go:871) — the invariant is delegated to the model        │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Worker-memory      │ Fail by absence │ all loop state is function-local; nothing survives a crash                                              │
│     │ state              │                 │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ Non-determinism    │ Moot            │ no replay exists to break; time.Now only in traces                                                      │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Untrusted text →   │ Fail            │ P0-3                                                                                                    │
│     │ model              │                 │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Doom loops         │ Partial         │ 2-iteration default is a blunt but real bound; no error-classified retry, parallel/serial abort         │
│     │                    │                 │ semantics inconsistent                                                                                  │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Context junk       │ Pass — better   │ ConversationSummary does real LLM compaction (conversation_summary.go:161); 1 MB message caps           │
│     │ drawer             │ than ours       │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ Mega-agent         │ Partial         │ subagents-as-tools with depth cap, but config-built subagents share the parent's memory instance        │
│     │                    │                 │ (agent.go:1953-1955) — cross-contamination by default                                                   │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Orchestration in   │ Mixed           │ loop is code; but LLMOrchestrator has the LLM author the plan, with a steps×3 cap                       │
│     │ model              │                 │ (llm_orchestrator.go:238)                                                                               │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Unbounded          │ Fail            │ P0-2 + no cost caps                                                                                     │
│     │ authority          │                 │                                                                                                         │
└─────┴────────────────────┴─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Component matrix

┌────────────────────────────┬───────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────┐
│         Component          │                 Role                  │                                     Health                                     │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/agent                  │ thin router (no loop)                 │ OK as facade; plan-approval default-on is a good instinct, coarse-grained      │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/llm/* (7)              │ providers + the loop, each            │ The core defect; broad matrix incl. Bedrock/Vertex-as-backends, prompt caching │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/tools, agent_tool      │ tools + subagents                     │ depth-capped; memory-sharing default is a leak                                 │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/guardrails             │ filters                               │ genuine filters, unwireable into the loop (interface mismatch)                 │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/memory                 │ buffer/redis/summary                  │ Strong: LLM summarization-compaction — ahead of ours                           │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/graphrag, vectorstore  │ RAG                                   │ Weaviate-only; 18- and 12-method god-interfaces                                │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/mcp, pkg/a2a, pkg/grpc │ integration                           │ MCP client and server; A2A both; gRPC remote agents — broader than ours        │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ pkg/tracing                │ OTEL + Langfuse                       │ good decorator pattern (TracedLLM)                                             │
├────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────┤
│ Versioning                 │ 36 tags, latest v0.0.36, no CHANGELOG │ tags ✓ / changelog ✗ (mirror image of ours)                                    │
└────────────────────────────┴───────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────┘

Head-to-head (the short version)

┌───────────────────┬───────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│     Dimension     │                   ours (temporal-go-agent-sdk)                    │                          Ingenimax                          │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Loop ownership    │ runtime layer, 2 copies (P0)                                      │ inside providers, 7 copies (worse)                          │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Durability        │ Temporal activities, ContinueAsNew, child workflows               │ none; crash = lost run                                      │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Tool gating       │ RequireAll approval default, per-call authorize+approve           │ plan-level only; per-tool gate absent; guardrail seam       │
│                   │ activities                                                        │ broken                                                      │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Injection surface │ fail (verbatim results/errors)                                    │ fail (same, ×7 loops)                                       │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Context           │ truncation only                                                   │ LLM summarization ✓                                         │
│ management        │                                                                   │                                                             │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Subagent          │ fresh context, child workflows ✓                                  │ shared parent memory by default ✗                           │
│ isolation         │                                                                   │                                                             │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Budgets           │ token budget + iterations + depth ✓                               │ iterations(2) + depth only; no cost/token cap               │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Release           │ CHANGELOG ✓ / 0 tags ✗                                            │ 36 tags ✓ / no CHANGELOG ✗                                  │
│ discipline        │                                                                   │                                                             │
├───────────────────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Breadth           │ 3 providers, MCP consume-only                                     │ 7 providers, MCP server, GraphRAG, YAML, Langfuse           │
└───────────────────┴───────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘

Bottom line: their breadth, our bones. The two things genuinely worth borrowing from Ingenimax are the memory summarization/compaction design and the traced-decorator observability pattern (plus MCP-server exposure as a roadmap item). Nothing about their execution core should be imported. Conversely, they independently confirm our two ecosystem-wide findings — verbatim tool-result injection and loop duplication are apparently how everyone ships Go agent SDKs right now, which makes fixing both in ours a real differentiator.

Unknowns

Whether requirePlanApproval=true survives all construction paths (struct default verified, YAML overrides not exhaustively traced); the post-approval resume wiring end-to-end; streaming-path append semantics read only partially.

Next question

What is this evaluation for — adopting Ingenimax, borrowing specific subsystems, or competitive positioning of our SDK? The answer changes what happens next: adoption is hard to justify against P0-1/2/4; borrowing points at their memory-compaction design; positioning says fix our injection P0 first, since it's the one defect we share with them and the cheapest to be demonstrably better on.

✻ Cooked for 5m 52s

※ recap: Architecture review of both agent SDKs is done: ours has solid Temporal bones but a prompt-injection gap and duplicated loop; Ingenimax is broader but weaker. Next: tell me the evaluation's goal (adopt, borrow, or compete) so I can act on findings.


❯ Please use same drill for this SDK and look for code evidenece do not rely on comments in code or docs!!!  https://github.com/google/adk-go

Same drill for Google's ADK Go — clone it next to your other evaluation target, then two evidence-required maps with an explicit "code only, no comments/docs" rule.

⏺ Bash(cd /Users/michal/PycharmProjects/agent-eval
  [ -d adk-go ] && echo "already present" || git clone --depth 1 https://github.com/google/adk-go.git 2>&1 | tail -2
  cd adk-go
  head -4 go.mod
  echo "--- top dirs ---" && find . -maxdepth 1 -type d -not -path './.git*' -not -name '.' | sort
  echo "--- go files:" && find . -name '*.go' -not -path './.git/*' | wc -l
  echo "--- temporal/durable?" && grep -rc 'go.temporal.io\|restate\|inngest' go.mod | head -1
  echo "--- latest commit ---" && git log --oneline -1)
Cloning into 'adk-go'...
module google.golang.org/adk/v2

go 1.25.0

--- top dirs ---
./agent
./agentregistry
./artifact
./cmd
./examples
./internal
./memory
./model
./platform
./plugin
./runner
./scripts
./server
./session
./telemetry
./tool
./util
./workflow
--- go files:
489
--- temporal/durable?
go.mod:0
--- latest commit ---
0c88126 chore(deps): bump google.golang.org/genai from 1.57.0 to 1.63.0 (#1021)
Shell cwd was reset to /Users/michal/PycharmProjects/temporal-go-agent-sdk

⏺ Explore(Map ADK-Go core/orchestration)
Done (31 tool uses · 141.9k tokens · 3m 49s)


⏺ Explore(Map ADK-Go model/tools/integrations)
Done (37 tool uses · 71.6k tokens · 4m 18s)


Both maps returned — and this one's genuinely interesting: ADK-Go is the only one of the three with an event-sourced resume design. Here's the evaluation, same format, code-evidence only.

TL;DR

ADK-Go has the best execution skeleton of the three evaluated SDKs — a single provider-agnostic loop, iter.Seq2 event streams end-to-end, injectable time/UUID for replay, and resume-from-event-log at human-in-the-loop pauses — but the core LLM loop is unbounded (no iteration, token, or cost cap; the model alone decides when to stop), and it leaks aggressively into the prompt: session-state and artifact values are interpolated verbatim into system instructions, and tool panics send full debug.Stack() traces to the model. It's also Gemini-only by construction, with no tags and no CHANGELOG.

The picture (OBSERVED — arrows backed by cited code)

            ┌───────────────────────────────────────────────┐
            │ runner.Runner (runner.go:181) — iter.Seq2 pull │
            │  LlmAgent root → graph node path (run_node.go)  │
            │  else → agent.Run(ctx) direct (:316)            │
            │  every non-partial event → session.AppendEvent  │
            └──────┬──────────────────────────┬──────────────┘
                   ▼                          ▼
   ┌──────────────────────────┐   ┌──────────────────────────────┐
   │ workflow/ graph engine    │   │ agent/workflowagents/         │
   │ scheduler.go:74 —          │   │ Sequential (no cap) ·         │
   │ goroutine/node, retry 5×,  │   │ Parallel (errgroup, branches) │
   │ per-node Timeout, MaxConc, │   │ Loop (MaxIterations, 0=∞)     │
   │ resume = ReconstructRun-   │   └──────────────────────────────┘
   │ State from EVENT LOG       │
   │ (persistence.go:80 — no    │
   │  run blob; scheduler state │
   │  dies with the process)    │
   └──────────┬────────────────┘
              ▼
   ┌────────────────────────────────────────────────────────────┐
   │ internal/llminternal.Flow — THE loop (base_flow.go:103)     │
   │ for { preprocess pipeline → callLLM → handleFunctionCalls } │
   │ NO max-iterations / token / cost cap (grep = none)          │
   │ ends only on IsFinalResponse (model stops calling tools)    │
   │ tool result → typed genai.FunctionResponse (:1179)          │
   │ tool error  → {"error": err.Error()} (:1275)                │
   │ tool PANIC  → err string incl. debug.Stack() (function.go:  │
   │   187) → to the model                                       │
   │ transfer_to_agent → next agent inline on SHARED ctx (:676)  │
   └──────────┬─────────────────────────────────────────────────┘
              ▼
   model/ — Gemini ONLY (registry.go:74; anthropic/openai grep=0;
     Vertex = genai backend variant, apigee = delegating proxy)
   tool/ — 3-method public Tool; execution on internal interface;
     functiontool generics+jsonschema; HITL confirmation EXPERIMENTAL,
     default-allow (tool.go:126,136)
   session/ — in-mem | GORM/SQLite | VertexAI; FULL history into
     req.Contents, no windowing/summarization (grep = none)

P0 findings

1. The core loop is unbounded. No max-iteration, token, or cost enforcement exists anywhere in Flow.Run — termination is solely IsFinalResponse (the model stops emitting tool calls), and LoopAgent.MaxIterations=0 means infinite — VERIFIED(subagent code-read, base_flow.go:103-131, loopagent/agent.go:33,97; greps for budget/maxIter enforcement = none). Combined with unbounded history (P0-3), a model stuck in a tool loop burns cost until the process dies. This is anti-pattern 8 shipped as the default.
2. Three distinct injection surfaces, one of them into the system prompt. (a) Session-state and artifact values are template-expanded verbatim into system instructions — only the variable name is validated, never the value (instruction_processor.go:143,163); anything a tool wrote to state last turn becomes system-prompt text this turn. (b) Tool errors reach the model as raw err.Error(), and recovered tool panics fold the full stack trace into that string (function.go:187-191 → base_flow.go:1275). (c) Telemetry serializes the complete tool response into span attributes unconditionally (telemetry.go:158-182) — an exfiltration path into the observability backend. All VERIFIED(subagent code-read). The typed FunctionResponse structure is better than string concatenation, but the content is still unsanitized.
3. No history bounding and no per-tool timeout. The full branch-filtered event log is assembled into every request (contents_processor.go:63; summarize/truncate/window greps = none), and nothing wraps tool execution in a deadline (only plugin-shutdown CloseTimeout exists) — VERIFIED(subagent greps). Long sessions grow cost superlinearly per turn; one hung tool hangs the run.
4. Sub-agent transfer shares the full session and context. transfer_to_agent runs the target inline on the same ctx/session (base_flow.go:676-678); Parallel gives fresh branches but shared Session/Artifacts/Memory (parallelagent/agent.go:83-92) — VERIFIED(subagent code-read). With default-allow, experimental HITL confirmation (tool/tool.go:126,136), a prompt-injected sub-agent inherits everything the parent could see and do.

Anti-pattern scorecard

┌─────┬────────────────────┬─────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  #  │    Anti-pattern    │ ADK-Go verdict  │                                                Evidence                                                 │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Model-owned        │ Fail            │ loop termination is entirely the model's decision (P0-1)                                                │
│     │ invariants         │                 │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Worker-memory      │ Best-in-eval    │ events + scoped state (app:/user:/session:/temp:) persisted; run progress re-derived from the event log │
│     │ state              │                 │  at pause boundaries (persistence.go:80) — though mid-step crash still loses the step                   │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ Non-determinism    │ Pass by design  │ injectable platform.Now/NewUUID (session.go:226); only retry jitter uses global rand                    │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Untrusted text →   │ Fail, worst     │ P0-2 — system-instruction injection beats tool-result injection in severity                             │
│     │ model              │ variant         │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Doom loops         │ Fail            │ P0-1; graph-node retry (5×, jittered) exists but only on the graph path                                 │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Context junk       │ Fail            │ full history every call, no compaction (P0-3)                                                           │
│     │ drawer             │                 │                                                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ Mega-agent         │ Partial         │ rich topology (tree, transfer, Sequential/Parallel/Loop, graph DAG) but shared-session transfer (P0-4)  │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Orchestration in   │ Pass            │ graph engine with Join barriers, routing, MaxConcurrency, per-node Timeout/Retry — the strongest        │
│     │ model              │                 │ orchestration code of the three                                                                         │
├─────┼────────────────────┼─────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Unbounded          │ Partial         │ HITL confirmation + BeforeToolCallback gating exist, but default-allow and EXPERIMENTAL; no tool auth   │
│     │ authority          │                 │ framework (TODO comments only)                                                                          │
└─────┴────────────────────┴─────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Component matrix

┌───────────────────────────┬────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│         Component         │                            Role                            │                           Health                            │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ internal/llminternal.Flow │ the one loop (1,422 lines)                                 │ single, provider-agnostic ✓; unbounded ✗; hidden in         │
│                           │                                                            │ internal/ (not extensible)                                  │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ runner/ + workflow/       │ execution + durable-ish graph                              │ genuinely good: retries, timeouts, concurrency caps,        │
│                           │                                                            │ event-log resume                                            │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ agent/workflowagents      │ Sequential/Parallel/Loop                                   │ clean; Loop 0=∞ footgun; resume participation unverified    │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ model/                    │ Gemini-only (registry is multi-provider-shaped, nothing    │ strategic lock-in                                           │
│                           │ else registered)                                           │                                                             │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ tool/                     │ 3-method public contract, generics functiontool, MCP       │ good shape; default-allow, no timeouts, no auth             │
│                           │ client, confirmation                                       │                                                             │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ session/memory/artifact   │ in-mem/SQLite/VertexAI + GCS                               │ solid services; no history bounding                         │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ server/, cmd/             │ A2A both ways, REST, Agent Engine deploy, HITL console     │ broadest deployment story of the three                      │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ telemetry/                │ OTEL, GenAI semconv                                        │ thorough; unconditional content capture ✗                   │
├───────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ Versioning                │ no tags, no CHANGELOG, sealed Agent interface              │ pre-release posture despite /v2 module path                 │
└───────────────────────────┴────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘

Three-way comparison (updated)

┌────────────────────┬──────────────────────────────┬───────────────────────┬─────────────────────────────────────────────────────┐
│     Dimension      │       ours (temporal)        │       Ingenimax       │                       ADK-Go                        │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Loop copies        │ 2                            │ 7                     │ 1 (+live/graph variants)                            │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Loop bounds        │ iterations+tokens+depth ✓    │ iterations(2)+depth   │ none ✗                                              │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Durability         │ Temporal activities ✓✓       │ none                  │ event-log resume at HITL pauses ✓                   │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Injection surface  │ tool results verbatim        │ same, ×7              │ worst: system-prompt state injection + panic stacks │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Tool gating        │ RequireAll default-deny ✓✓   │ plan-level only       │ confirmation exists, default-allow, experimental    │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Subagent isolation │ fresh ctx, child workflows ✓ │ shared memory ✗       │ shared session on transfer ✗                        │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Context mgmt       │ truncation                   │ summarization ✓       │ none                                                │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Determinism hooks  │ Temporal replay              │ n/a                   │ injectable time/UUID ✓                              │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Providers          │ 3                            │ 7                     │ 1 (Gemini)                                          │
├────────────────────┼──────────────────────────────┼───────────────────────┼─────────────────────────────────────────────────────┤
│ Release discipline │ CHANGELOG, 0 tags            │ 36 tags, no CHANGELOG │ neither                                             │
└────────────────────┴──────────────────────────────┴───────────────────────┴─────────────────────────────────────────────────────┘

The composite verdict across the eval set: nobody ships bounded, injection-safe tool loops — every SDK feeds raw error text to the model, and only ours has default-deny tool gating. ADK-Go's genuinely borrowable ideas are the iter.Seq2 event-stream spine, the request-processor pipeline, injectable time/UUID, event-log-derived HITL resume (a lighter-weight cousin of what Temporal gives us for free), and the typed-FunctionResponse discipline. Its unbounded loop and system-prompt injection mean it's a design reference, not an adoption candidate — unless you're all-in on GCP/Gemini, which is clearly its intended home.

Unknowns

Whether platform.RunTasks recovers goroutine panics from non-functiontool tools (crash-safety of that path unverified); whether classic Sequential/Parallel/Loop roots participate in resume at all; whether span content-capture can be filtered downstream; every WithConfirmation call-site default.

Next question

Is Gemini-only acceptable for whatever this evaluation feeds? It's the one property of ADK-Go that can't be layered around (the registry is multi-provider-shaped, but the loop's live/bidi path, caching, and telemetry all assume genai types) — everything else on the defect list is fixable by a wrapper or a fork, this one is architectural. If the answer is no, ADK-Go drops to "borrow ideas" and the real contest is your SDK vs. Ingenimax's breadth; if yes, ADK-Go's runner/workflow layer is the strongest baseline of the three despite its P0s.

✻ Crunched for 6m 40s

※ recap: Evaluating agent SDK architectures: finished evidence-backed reviews of our temporal-go-agent-sdk, Ingenimax, and Google ADK-Go. Next action: tell me the evaluation's goal (adopt, borrow, or position ours) so I can turn findings into decisions.

❯ One thing befor we jump into P0 findings and antipattern fixes. Please tell  what agent type we are building? is our SDK only a core? If agent the please analzye how do we have to project our efforts # Agentic Architectures — Visual Dissection

  Eight production-proven agentic architectures, each drawn to expose its defining
  feature: **where the control plane lives** and **which edge is load-bearing**.

  **Visual conventions used throughout:**

  | Notation | Meaning |
  |---|---|
  | `==>` thick edge | Load-bearing contract (the edge that makes or breaks the pattern) |
  | `-.->` dashed edge | Trust / failure / escalation edge |
  | `-->` solid edge | Ordinary data flow |
  | Subgraph box | A plane or isolation boundary |

  ---

  ## 1. Single-Agent Tool Loop

  *Control plane inside the model; the context window is the only data bus; one
  contract (the tool schema); no checkpoint layer.*

  ```mermaid
  flowchart TD
      U["User request"] --> C

      subgraph LOOP["Agentic loop — control plane = the model itself"]
          C["Context window<br/>(the only data bus)"] --> M["Model<br/>(implicit planner in weights)"]
          M ==>|"tool call — the ONE contract<br/>(JSON schema)"| P{"Permission gate<br/>(trust edge)"}
          T["Tool layer"] -->|"result appended"| C
      end

      P -->|approved| T
      P -.->|denied| C
      T --> W["External world<br/>(files, shell, APIs)"]
      M -->|"final answer"| OUT["Response"]

      C -.->|"failure edge: context exhaustion —<br/>no checkpoint, crash loses the run"| DEAD["Run lost ☠"]

      style LOOP fill:#eef4ff,stroke:#3b6fd4
      style DEAD fill:#ffe5e5,stroke:#c33
  ```

  **What to notice:** the deterministic membrane around the model is one gate
  thick. Everything else — planning, memory, sequencing — is emergent inside
  `LOOP`, which is why it's powerful and why it's unauditable.

  ---

  ## 2. Workflow-First Pipeline

  *Control plane in code; the LLM is demoted to the data plane — a fuzzy pure
  function inside a step. Every step boundary is a schema contract and an eval site.*

  ```mermaid
  flowchart LR
      IN["Typed input"] --> S1

      subgraph S1["Step 1 — Extract"]
          L1["LLM call<br/>(pure function)"]
      end
      subgraph S2["Step 2 — Classify"]
          L2["LLM call"]
      end
      subgraph S3["Step 3 — Draft"]
          L3["LLM call"]
      end

      S1 ==>|"schema contract<br/>+ eval site"| V1{"validate"}
      V1 -->|pass| S2
      V1 -.->|"fail → retry / fallback"| S1

      S2 ==> V2{"validate"}
      V2 -->|pass| S3
      V2 -.-> S2

      S3 ==> V3{"validate"}
  ──── (382 lines hidden) ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  - **Indirect prompt injection via retrieved content:** the corpus is an attack surface (poisoned documents instructing the agent).
  - **Sufficiency misjudgment:** stops retrieving too early (shallow answer) or loops (cost blowout).
  - **Evaluation difficulty:** no single ground truth; grounded-ness metrics are proxies.

  ## 8. Sandboxed Code Execution

  **Best-fit use cases**
  - Data analysis / BI copilots (every major BI vendor); quantitative research; spreadsheet and report automation.
  - Scientific computing assistants; one-off ETL; and as the universal escape-hatch tool inside coding agents.

  **Fit signal:** the action space is unbounded but computable — bespoke tools
  can't be enumerated in advance.

  **Challenges / limitations / risks**
  - **Egress exfiltration:** allowed network paths (even package registries) are covert channels — lock egress before anything else.
  - **Supply-chain risk:** the model pip-installing a typosquatted package is a real, observed attack vector.
  - **Sandbox escape:** container isolation is not a security boundary against a determined payload — microVM/gVisor for untrusted workloads.
  - **Resource abuse:** fork bombs, runaway loops, cryptomining — hard limits are mandatory.
  - **Correctness illusion:** code that runs without error is mistaken for analysis that's right; silent dataframe errors (wrong join, dropped rows) are the classic failure.
  - **State divergence:** the sandbox filesystem evolves off-context; the model's mental model of what files exist goes stale.
  - **Environment mismatch:** works-in-sandbox, fails-in-prod for any code intended to leave the sandbox.

  ---

  ## Cross-Cutting Risk Register

  Risks that apply to *all eight* and belong in every design review:

  1. **Prompt injection** — any content the agent reads is an instruction channel (tool results, retrieved docs, emails). Mitigate at the tool/privilege layer, not the prompt.
  2. **Excessive agency** — tools whose blast radius exceeds the task's needs. Least-privilege per agent/step; human gates before irreversible actions.
  3. **Eval debt** — shipping without a regression harness; every prompt/model change is then a blind deploy.
  4. **Cost observability** — token spend is the new cloud bill; per-run budgets and kill-switches are table stakes.
  5. **Accountability** — the deploying organization owns the agent's outputs (legal precedent exists). Log everything; make the audit trail a first-class artifact — which is, not coincidentally, what pattern #6 gives you for free.


Excellent framing document — and the honest answer drops straight out of the evidence we already gathered. No new exploration needed; everything below cites what we verified this session.

What we are building

We are building pattern #6 as a product, with pattern #1 as its payload. Precisely: a durable-execution-backed single-agent tool loop, with #3-lite (subagents as child workflows) and #7 building blocks (retriever prefetch/agentic/hybrid modes) attached.

The evidence maps one-to-one onto diagram #6: our AgentWorkflow is the deterministic workflow lane (VERIFIED earlier: agent_workflow.go:328, state in AgentWorkflowState, ContinueAsNew, workflow.Now/SideEffect); LLM and tool calls are quarantined in activities (agent_workflow.go:532, :1018) — the determinism frontier is physically where diagram #6 draws it. And inside each activity iteration, what executes is diagram #1: context window as bus, tool schema as the one contract, approval gate as the trust edge (RequireAll default — the one gate we ship stronger than anyone in the eval set).

That's also the honest reading of the Local runtime: it's pattern #1 without the membrane — the ☠ Run lost failure edge in diagram #1 is literally what Local has and Temporal doesn't. Which reframes my earlier P0-2 "next question": the dual loop isn't just duplication, it's two different architectures sharing a codebase — #1-bare and #1-inside-#6. That's why they've diverged (retry semantics) and why they'll keep diverging.

Is our SDK "only a core"?

No — but it's lopsided. Three layers exist in any commercial agent SDK, and we have exactly one and a half:

1. Runtime/membrane (the loop, the frontier, gates, budgets) — we have this, and it's our best layer. Nobody in the eval set matches Temporal-backed durability + default-deny gating.
2. Pattern layer (primitives for #2/#3/#4/#5 composition) — we have half: subagents and retriever modes, but no pipeline/step API, no evaluator-gate primitive, no router/handoff helper. ADK's graph engine and Ingenimax's orchestrator both beat us here.
3. Platform layer (deploy story, eval harness, workflow versioning, cost ops) — we have essentially none. ADK ships cmd/adkgo deploy; we ship examples.

So: a framework with a strong core, not a platform. The strategic question is which gaps to fill, and the taxonomy answers it.

Effort projection against the eight patterns

┌─────┬──────────────────────┬────────────────────────────────────────────────────┬────────────────────────────────────┬───────────────────────────────┐
│  #  │       Pattern        │                 Our coverage today                 │  Market validation (per your doc)  │            Verdict            │
├─────┼──────────────────────┼───────────
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 2   │ Workflow pipeline    │ ❌ no step/schema/eval primitives                  │ most widely deployed enterprise    │ Invest — cheapest big win     │
│     │                      │                                                    │ pattern                            │ (see below)                   │
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 3   │ Orchestrator–workers │ 🟡 child workflows give isolation; no              │ validated (deep research,          │ Polish, don't build — helpers │
│     │                      │ brief/summary contracts                            │ migration sweeps)                  │  + docs                       │
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 4   │ Router/handoff       │ 🟡 A2A + subagents can express it; no              │ most economically validated        │ Recipe, not machinery         │
│     │                      │ privilege-transition helper                        │ (support)                          │                               │
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 5   │ Evaluator–optimizer  │ ❌ nothing                                         │ validated where grounding exists   │ Small primitive — gate +      │
│     │                      │                                                    │                                    │ grounding seam                │
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 7   │ Agentic RAG          │ 🟡 retriever modes; no provenance/citation edges   │ validated, but a product category  │ Building blocks only — don't  │
│     │                      │                                                    │ of its own                         │ chase Glean                   │
├─────┼──────────────────────┼────────────────────────────────────────────────────┼────────────────────────────────────┼───────────────────────────────┤
│ 8   │ Sandbox              │ ❌ nothing                                         │ validated                          │ Skip — integrate via MCP; not │
│     │                      │                                                    │                                    │  our fight                    │
└─────┴──────────────────────┴───────────model). For us it's a thin layer: expose agent-step-as-activity with typed input/output schemas and validation edges, and users compose diagram #2 in ordinary Temporal workflow code, inheriting checkpointing, retries, and signals for free. We'd be the only SDK in the eval set where #2 and #6 are the same API rather than two engines.

Why the membrane P0s come first anyway: your document independently confirms the priority order. "Prompt injection through tool results" is named the top security issue for the whole category (pattern #1 challenges) and item 1 of the cross-cutting register — that's our P0-1 verbatim. "Mitigate at the tool/privilege layer, not the prompt" is exactly the fsguard/pathscope philosophy, and those are built and unwired (VERIFIED: zero imports outside pkg/tools). Hardening the membrane isn't competing with pattern work — it's the precondition for every pattern, because all eight run through the same tool-result edge.

Where #6's own challenge list points our roadmap: your doc names the three production killers of the durable pattern, and they map to concrete gaps we verified:
- Payload limits ("store references, not transcripts") — our AgentWorkflowState.Messages carries full conversation through event history. ContinueAsNew postpones the problem; a reference-based message store (IDs in workflow state, bodies in the conversation service we already have) removes it. Real work, clearly scoped.
- Versioning in-flight workflows — "the hardest operational problem in the pattern," and nobody in our eval set has any story for it. A documented + tooled versioning discipline for month-long agent workflows (prompt/model/code changes mid-flight) would be a differentiator no feature checkbox can match.
- Durable ≠ correct — the doc says correctness comes from gates (#5) and human signals. We have approval activities (signals ✓); we lack the #5 gate primitive — which is the second reason #5 makes the invest list despite being small.

The sequenced plan (how I'd project the effort)

Phase 1 — Membrane (fix what carries every pattern): injection-safe tool-result envelope + static error text (P0-1); panic recovery + per-tool timeout in Local (P0-3); wire fsguard/pathscope + Snapshot into AgentWorkflowState; the uuid.New() SideEffect one-liner (P0-4).

Phase 2 — Resolve the architecture split (P0-2, now properly framed): decide Local's identity — my recommendation, given the taxonomy: declare Local the dev-mode of pattern #1 and Temporal the production architecture, converge the loop into one state machine in base that both drivers execute, and stop maintaining two architectures.

Phase 3 — Own the frontier (differentiators): reference-based payloads; workflow-versioning story; evaluator-gate primitive (#5) and pipeline-step API (#2) as thin layers over activities; brief/summary contracts for subagents (#3 polish).

Phase 4 — Platform hygiene (the cross-cutting register): per-run cost budget with kill-switch (we have token budget — extend to spend), an eval-harness seam (register 3: "eval debt" — nobody in the eval set has this either), and lean into the audit story: Temporal event history is register item 5's "audit trail as first-class artifact," for free — we should market it as such, not just possess it.

One honest caution from your own document, as the closing note: "durable ≠ correct." Our moat guarantees the agent's decisions execute exactly once and replay faithfully — it does not make them right. That's why Phase 1 (gates on the tool edge) and the #5 primitive (grounding gate) rank above every feature in Phase 3: the substrate we're selling amplifies whatever passes through it, wrong decisions included.

If you want, next step I'd take: record this as ADR-011 (architecture identity: pattern #6 with #1 payload; Local = dev-mode; the four-phase investment sequence) so the decision survives this context window — then start Phase 1 with the tool-result envelope, which is the single highest-leverage change in the entire analysis.