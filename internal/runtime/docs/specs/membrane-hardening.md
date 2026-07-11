# Membrane hardening — Phase 1 feature spec

> Reader: the session implementing wk-0eaee8d9 | Enables: starting implementation without re-deriving the design from ADR-011, the dossiers, or chat history | Update-trigger: a cited id changes status, wk-0eaee8d9 closes, or ADR-011 phase 1 is re-scoped

Facts are authoritative only as ledger ids; prose is courtesy. Judge with
`bash scripts/spec-health.sh`. Run `scripts/truth impact <file>` before
editing — every target file below carries claim tripwires that WILL stale on
your commit; that is expected and correct (re-dispatch after shipping).

## Work item

- **wk-0eaee8d9** — Phase 1: membrane hardening. Premises (live): tr-42e5b4c3,
  tr-466f3e3e, tr-799b362d, tr-166b071c, tr-9737e935. Decision: ADR-011
  (phase 1). Design sources: PAT-003, PAT-004, PAT-006
  (`docs/evaluations/patterns-to-adopt.md`); violations being fixed: AP-05,
  AP-04, AP-08 (`docs/design-review-checklist.md`).

## Scope (courtesy prose)

Five changes, one work item, sequenced so each lands independently:

1. **Typed tool-result envelope** (fixes tr-42e5b4c3; adopts PAT-003 with the
   PAT-003 caution: typing alone is insufficient without static error text).
   Replace the verbatim `fmt.Sprintf("%v", result)` path with a structured
   envelope (tool name, status, delimited content) built in ONE place in
   `internal/runtime/base`, consumed by both loops.
2. **Static model-facing error text** (fixes tr-6cb4d1a2; PR-02). The model
   sees a fixed corrective sentence per error class; the raw `err.Error()`
   moves to a harness-only field (logs/telemetry), never into message content.
3. **Panic recovery + per-tool timeout** (fixes tr-09eeed62; AP-08). A
   `defer recover()` in the local tool-execution goroutine converting panics
   to the classified tool-error path (never forwarding stack traces to the
   model — the ADK@0c88126 mistake), plus a configurable per-tool deadline.
4. **SideEffect the messageID uuid** (fixes tr-166b071c; AP-04). One-liner in
   `internal/runtime/temporal/agent_workflow.go`, matching its two wrapped
   siblings.
5. **Wire the guard trio** (fixes tr-9737e935; ADR-007/008). Register
   fsguard-backed file tools + pathscope in the runtime tool path; thread
   `fsguard.Snapshot` through workflow state per AP-03.

Item 1 SHOULD land via a request-assembly seam (PAT-006 processor shape) so
per-source trust labeling has a home later; do not build the full pipeline —
just the seam the envelope needs.

## Acceptance (pre-written `done --claim` texts — file AFTER the shipping commit)

- Envelope: "tool results enter model-facing messages only through a typed
  envelope constructed in internal/runtime/base; no fmt.Sprintf('%v', result)
  path remains — covered by tests in both runtimes."
- Errors: "model-facing tool-error text is static per error class; raw
  err.Error() reaches only logs/telemetry — covered by tests."
- Panics/timeout: "a panicking or hung tool on the local path yields a
  classified tool-error message within its deadline; the process survives —
  covered by tests."
- UUID: "no uuid.New() call in workflow code outside workflow.SideEffect —
  covered by grep-based test or replay test."
- Wiring: "fsguard/pathscope-backed file tools are registrable through the
  standard agent config and exercised by an example — covered by an
  integration test."

## Out of scope

Loop convergence (wk-39850a5b, phase 2) — implement fixes in both loops via
shared base helpers, but do NOT merge the loops here. History compaction
(PAT-001) and cost budgets are phase 4 (wk-7baee278).
