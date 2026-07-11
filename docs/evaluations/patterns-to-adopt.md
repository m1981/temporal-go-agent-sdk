# Patterns to adopt (PAT registry)

> Reader: SDK contributors implementing roadmap work items | Enables: adopting a borrowed design by stable id (PAT-NNN) in ADRs, specs, and wk- items, with the source pinned | Update-trigger: a PAT is adopted (mark Adopted-by), rejected (mark Rejected + ADR), or a new evaluation adds entries

Each entry: source pinned as `repo@SHA:file:line`, what it is, why we want it,
and where it lands in the ADR-011 phases. RFC 2119 language. Entries are
design references — we re-implement to our conventions; we do NOT vendor code.

| id | Source (pinned) | Status |
|---|---|---|
| PAT-001 | Ingenimax@71a421c `pkg/memory/conversation_summary.go:76-161` | Proposed |
| PAT-002 | Ingenimax@71a421c `pkg/tracing/traced_llm.go:19`, `langfuse.go:14` | Proposed |
| PAT-003 | ADK@0c88126 `internal/llminternal/base_flow.go:1179-1183` | Proposed |
| PAT-004 | ADK@0c88126 `platform/time.go:34`, `session/session.go:226-232` | Proposed |
| PAT-005 | ADK@0c88126 `workflow/persistence.go:80-116`, `runner/run_node.go:132-141` | Proposed |
| PAT-006 | ADK@0c88126 `internal/llminternal/{instruction,contents,tools}_processor.go` | Proposed |
| PAT-007 | ADK@0c88126 `agent/agent.go:46`, `workflow/config.go:81-110` | Proposed |
| PAT-008 | ADK@0c88126 `tool/functiontool/function.go:79,272` | Proposed |

## PAT-001 — LLM summarization-compaction of conversation history

Old messages beyond a threshold are summarized by the LLM into a rolling
summary instead of dropped. Why: our history bounding is truncation-only
(drop-oldest at ConversationSize=20); compaction preserves task-relevant
detail (counters AP-09). Target: phase 4 (wk-7baee278) or a dedicated item.
Caution: summarization is itself an LLM call — MUST run as an activity and
MUST be budgeted.

## PAT-002 — Traced-decorator observability wrappers

`TracedLLM(inner LLM)` / `TracedMemory(inner Memory)` decorate the interface
rather than instrumenting call sites. Why: our spans are wired inside
base.Runtime methods; decorators would let users add Langfuse-style exporters
without touching the runtime. Target: phase 4. Low priority — our OTEL
coverage is already full; adopt the *shape* if/when a second exporter demand
appears.

## PAT-003 — Typed tool-result envelopes (never string concatenation)

Tool results enter model contents as structured parts
(FunctionResponse-style), not `fmt.Sprintf("%v", result)`. Why: this is the
structural half of the AP-05 fix for tr-42e5b4c3/tr-6cb4d1a2 — typed
delimitation plus static error text. Target: **phase 1 (wk-dcc7a92d)** — the
single highest-leverage adoption. Note: ADK proves typing alone is
insufficient (they still inject raw error strings and stack traces INSIDE the
typed part); we MUST combine PAT-003 with PR-02 static errors.

## PAT-004 — Injectable time/UUID providers for replay-safe events

`platform.Now(ctx)` / `platform.NewUUID(ctx)` with test/replay overrides.
Why: generalizes our SideEffect discipline beyond Temporal — the Local
runtime and any event construction get deterministic, testable identity;
directly relevant to fixing tr-166b071c once, in base, for both drivers.
Target: phase 1–2 boundary (wk-dcc7a92d / wk-39850a5b).

## PAT-005 — Event-log-derived HITL resume

Interrupts persisted as events; paused run state re-derived by scanning
session history — no separate run blob to version. Why: informs our
approval/signal design and the phase 3 reference-payload work: the event log
as single source of truth is also our audit story (PR-08, register item 5).
We get stronger guarantees from Temporal replay; the borrowable idea is the
*schema* — interrupt/resolution event pairs. Target: phase 3 (wk-0bdbd4e4).

## PAT-006 — Request-processor pipeline for prompt assembly

Ordered, testable processors over a request struct (instructions → history →
tools) instead of inline concatenation. Why: our BuildLLMRequest
string-concatenates memory/retriever context into the system prompt; a
processor pipeline gives each contribution a seam for the AP-05 envelope and
for per-source trust labels. Target: phase 1 enabler (wk-dcc7a92d).

## PAT-007 — Pipeline-step API shape: iterator event spine + per-node caps

`iter.Seq2` event streams and per-node Timeout/Retry/MaxConcurrency as the
*API shape* for our typed pipeline-step layer over Temporal activities. Why:
phase 3's #2-pattern API should feel Go-native (range-over-events), while the
engine underneath is Temporal, not a bespoke scheduler. Target: phase 3
(wk-0bdbd4e4).

## PAT-008 — Generics function-tool with derived JSON schema

`functiontool.New[TArgs, TResults](handler)` deriving the parameter schema
from Go types. Why: removes hand-written Parameters() maps (our tools.Params
boilerplate), makes tool arg contracts compile-checked. Target: phase 3/4;
independent of the safety work. MUST keep panic recovery inside the wrapper
(ADK does) but MUST NOT forward stack traces to the model (ADK does — see
dossier P0-3).
