# ADR-011: Architecture identity — durable-execution SDK with a tool-loop payload — and the investment sequence

> Status: Accepted
> Date: 2026-07-11
> Supersedes: —

## Context

A cross-SDK evaluation (2026-07-10/11) mapped this SDK and two competitors with
file:line evidence — `github.com/Ingenimax/agent-sdk-go@71a421c` and
`github.com/google/adk-go@0c88126`; full dossiers in `docs/evaluations/`. The
findings about our own runtime are filed as path-tripwired ledger claims:
tr-42e5b4c3 (verbatim tool results), tr-6cb4d1a2 (raw error interpolation),
tr-e1d73540 (dual agent loop, already diverged), tr-09eeed62 (no panic
recovery), tr-166b071c (naked uuid in workflow loop), tr-9737e935 (safety trio
unwired).

Against the eight-pattern agentic-architecture taxonomy (control-plane
placement / determinism frontier), the evidence shows what we actually are:
pattern #6 (durable execution) as the product, with pattern #1 (single-agent
tool loop) as its payload, plus #3-lite subagents (child workflows) and #7
building blocks (retriever modes). The Local runtime is pattern #1 *without*
the durability membrane — meaning the repo currently maintains two different
architectures sharing one codebase, which is why their retry semantics have
already diverged (tr-e1d73540).

Options considered for identity: (a) general-purpose multi-pattern framework
competing on breadth (Ingenimax's position: 7 providers, 7 hand-copied loops,
no durability); (b) Gemini-style vertically-integrated platform (ADK's
position: one loop, unbounded, single provider); (c) own the determinism
frontier — the durable membrane — and ship other patterns as thin layers over
it. Evidence from both competitors shows breadth without a sound core produces
loop duplication and unbounded/injectable execution; nobody in the evaluated
set ships bounded, injection-safe tool loops or an in-flight
workflow-versioning story.

## Decision

We will define this SDK as a **durable-execution-backed agent runtime**
(pattern #6) whose primary payload is a hardened single-agent tool loop
(pattern #1). The Temporal path is the production architecture; the Local
runtime is its dev-mode, not a first-class peer. Investment follows four
phases, tracked as ledger work items:

1. **Membrane hardening** (wk-dcc7a92d): typed tool-result envelope + static
   model-facing errors, panic recovery + per-tool timeout, wire the
   fsguard/pathscope trio and its Snapshot into runtime state, SideEffect the
   remaining uuid.
2. **Loop convergence** (wk-39850a5b): one iteration state machine in
   `internal/runtime/base`, executed by both drivers.
3. **Frontier differentiators** (wk-0bdbd4e4): reference-based payloads in
   workflow state, an in-flight workflow-versioning discipline, an
   evaluator-gate primitive (#5) and a typed pipeline-step API (#2) as thin
   layers over activities.
4. **Platform hygiene** (wk-7baee278): spend budgets with kill-switch, an
   eval-harness seam, the audit-trail story.

Patterns #8 (sandbox) and #7-as-product (RAG platform) are explicitly out of
scope; #4 (router/handoff) is documentation over existing A2A/subagents, not
new machinery. Borrowed designs are adopted only via `PAT-NNN` entries in
`docs/evaluations/patterns-to-adopt.md`.

## Consequences

- Easier: every membrane fix is written once (phase 2 makes phase 1 land in
  one loop, not two); the #2/#5 pattern layers inherit checkpointing, retries,
  and signals from the substrate instead of needing engines (contrast ADK's
  scheduler and Ingenimax's LLM-authored plans); positioning is falsifiable —
  "the SDK where the determinism frontier is physical and the tool edge is
  gated."
- Harder / ruled out: the Local runtime loses feature parity as a goal — it is
  allowed to be an explicitly degraded dev-mode (documented, not silent);
  provider breadth (Bedrock, Azure, Ollama...) is deprioritized behind
  frontier work, conceding a checkbox war Ingenimax wins today; durable ≠
  correct — the substrate amplifies wrong decisions too, which is why phase 1
  gates and the phase 3 evaluator primitive outrank all feature work.
- Lifespan: identity decision, permanent until superseded; phase contents may
  be re-scoped by later ADRs without superseding the identity.
