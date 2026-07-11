# Agentic design-review checklist (AP/PR catalog)

> Reader: anyone writing an ADR, feature spec, or reviewing agent-runtime changes | Enables: citing anti-patterns and principles by stable id (AP-NN / PR-NN) in ADRs, specs, and reviews instead of re-arguing them | Update-trigger: a new ADR contradicts an entry, or a new anti-pattern is observed in the field

Derived from the 2026-07 cross-SDK evaluation (`docs/evaluations/`) and this
repo's own findings (ledger tr- ids). RFC 2119 keywords. Cite entries by id.

## Anti-patterns (AP)

- **AP-01 Model-owned invariants.** A correctness property enforced only by
  prompt text WILL fail at scale; the failure it guards against is a model
  failure. Guards MUST live in harness code and MUST NOT be configurable off.
  (Field example: ADK@0c88126 loop termination is solely model-decided.)
- **AP-02 Forgeable state signals.** mtime, "the model said so", and
  last-write-wins are not integrity signals. Use content hashes / typed state.
  (ADR-007.)
- **AP-03 Worker-memory state in a durable world.** State that gates decisions
  MUST live in workflow state, serialized and replay-safe — never in worker
  process memory. (fsguard Snapshot, ADR-007/011.)
- **AP-04 Non-determinism in workflow code.** No wall-clock, rand, map-order,
  or LLM calls in workflow code; all I/O in activities. (Finding tr-166b071c.)
- **AP-05 Untrusted text interpolated into model-facing content.** Tool
  results, error strings, and state values are instruction channels. Errors to
  the model MUST be static; results MUST be enveloped/typed. (Findings
  tr-42e5b4c3, tr-6cb4d1a2; worst-in-class: ADK@0c88126
  instruction_processor.go:163 injects state values into system instructions,
  functiontool/function.go:187 sends panic stack traces to the model.)
- **AP-06 Self-grading.** The author of a claim/change MUST NOT be its
  verifier; verification needs an independent context with a refute mandate.
- **AP-07 Overclaiming completion.** Claims MUST be scoped to their evidence
  ("narrowed, not closed"); residual risk MUST be named and, where possible,
  pinned by an executable test. (ADR-010 residual-risk section.)
- **AP-08 Doom loops without exits.** Every corrective error path MUST have a
  bounded retry budget and a distinct escalation path. Iteration, token, and
  spend caps are harness invariants (see AP-01). (ADK@0c88126: no
  iteration/token/cost cap in Flow.Run; LoopAgent MaxIterations=0 means
  infinite.)
- **AP-09 Context junk drawer.** Unbounded history re-sent every turn.
  History MUST be bounded; compaction/summarization SHOULD exist.
  (Ingenimax@71a421c ConversationSummary is the positive example.)
- **AP-10 Mega-agent.** Decompose along trust and perspective boundaries;
  sub-agents SHOULD get fresh context and their own least-privilege toolset.
  (Negative: ADK transfer shares full session (base_flow.go:676); Ingenimax
  config subagents share the parent memory instance (agent.go:1953).)
- **AP-11 Orchestration in the model.** Loops, fan-out, joins, and retries
  belong in deterministic code that calls the model per-step — never in prompt
  instructions. (Negative: Ingenimax LLMOrchestrator has the LLM author the
  plan.)
- **AP-12 Unbounded authority.** Blast radius equals permission set. Per-tool
  default-deny gating, path scoping, and spend caps are separate layered
  controls and MUST NOT be merged. (Our RequireAll default is the positive
  example; ADK confirmation is default-allow and experimental.)
- **AP-13 Duplicated control loop.** The agent loop implemented more than once
  (per backend or per provider) WILL diverge behaviorally. One state machine,
  N drivers. (Findings tr-e1d73540; Ingenimax has seven copies.)

## Principles (PR)

- **PR-01 Deterministic harness, probabilistic core.** Everything around the
  model is ordinary verifiable code; the model supplies judgment inside
  guardrails it cannot remove.
- **PR-02 Errors are instructions.** A blocked tool call returns static text
  naming the one correct next action; variable data rides harness-only fields.
- **PR-03 State placement follows the execution model.** Decisions in workflow
  code; I/O and LLM calls in activities; observed values returned into
  workflow state.
- **PR-04 Check-and-act is one operation where it matters.** Otherwise
  document the residual TOCTOU window and pin it with a test. (ADR-010.)
- **PR-05 Independent, adversarial verification** with diverse lenses beats
  redundant identical checkers.
- **PR-06 Evidence-scoped claims.** VERIFIED/INFERRED/UNVERIFIED tags;
  unknowns listed, never silently filled. External code cited as
  `repo@SHA:file:line`, never floating.
- **PR-07 Least authority, layered.** Freshness guard ≠ path scope ≠
  permission mode ≠ budget; each has a different failure mode and owner.
- **PR-08 Decisions outlive contexts.** ADRs, ledger claims, and commit
  messages are the only memory that survives; append-only where history
  matters.
- **PR-09 TDD is the agent-native loop.** A failing test is the one spec a
  coding agent cannot argue with; red must fail for the right reason.
- **PR-10 Sequential where state is shared, parallel where it isn't.** The
  scheduling decision belongs to the orchestrator, not the agents.
- **PR-11 The determinism frontier is a design input.** Decide where the task
  tolerates nondeterminism, draw that edge, and the architecture falls out;
  make the frontier physical (checkpointed) where money, audit, or long waits
  are involved. (ADR-011.)
- **PR-12 Durable ≠ correct.** The substrate guarantees a decision executes
  exactly once — gates and humans make it right; wrong decisions replay too.
