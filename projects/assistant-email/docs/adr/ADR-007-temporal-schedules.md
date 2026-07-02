# ADR-007: Temporal Schedules for the Periodic Digest

## Status

**Accepted** - 2026-07-02 — supersedes the Phase-2 sketch in ADR-005

## Context

ADR-005 planned "Phase 2: Temporal cron" via
`StartWorkflowOptions.CronSchedule`. Since then Temporal has deprecated
workflow cron in favor of **Schedules**, which add overlap policies,
pause/resume, backfill, and a first-class management API. ADR-005 also
left two gaps: it never specified *what* the scheduled workflow contains
(the digest has a deterministic pipeline *and* an LLM narrative), and it
did not address the quiet-hours requirement from brief.md (22:00-07:00).

## Decision

Use a **Temporal Schedule** (`email-digest`, interval `DIGEST_INTERVAL`,
default 2h, overlap policy **skip**) that triggers `EmailDigestWorkflow`
(`projects/assistant-email-go/digestwf`).

The workflow is pure orchestration over three activities:

1. `InQuietHours` — gate; when true the run completes as `Skipped`, so
   quiet-hour suppressions are visible in workflow history.
2. `RunDigestPipeline` — deterministic pass (fetch → classify → memory
   diff → render → persist), 3 retry attempts.
3. `RunAgentNarrative` — the SDK agent runs in-process *inside the
   activity*; the agent's own budgets (ADR-004) bound the call, the
   activity timeout is the outer hard stop, 2 retry attempts.

`cmd/worker` hosts the workflow+activities; `cmd/schedule` creates or
replaces the Schedule. `cmd/digest` remains for one-shot/cron use
(ADR-005 Phase 1 stays valid for machines without a Temporal server).

## Rationale

- **Schedules over cron**: overlap `skip` is the correct policy — digest
  runs are idempotent via thread memory, so a skipped tick loses nothing,
  while queued overlaps could double-call the LLM.
- **Agent-in-activity over SDK Temporal runtime**: the digest needs the
  deterministic pipeline and the narrative in one durable unit with
  per-step retries; wrapping both as activities of one workflow gives
  that without depending on the SDK's internal workflow registration.
- **Quiet hours as an activity, not schedule calendar exclusions**: the
  window lives in one place (`config.QuietHours`, validated at load) and
  changing it does not require touching the server-side Schedule.

## Consequences

### Positive
- Crash recovery, per-step retries, full run history in Temporal UI.
- Missed/overlapping ticks handled by policy, not ad-hoc locking.
- Workflow logic is unit-tested with the Temporal test suite (no server).

### Negative
- Requires a running Temporal server and a worker process.
- Quiet-hour skips still consume a (cheap) workflow execution.

## Related Decisions

- ADR-004 (budgets bound the narrative activity)
- ADR-005 (Phase 1 cron remains the no-server fallback)
- ADR-006 (Go port this builds on)
