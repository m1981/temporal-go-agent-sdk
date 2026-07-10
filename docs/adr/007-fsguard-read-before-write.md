# ADR-007: Read-before-write guard for file-mutating tools (fsguard)

> Status: Accepted
> Date: 2026-07-10
> Supersedes: —

## Context

The SDK will grow file-mutating agent tools (a `Write`/`Edit` surface). An LLM
driving such a tool can edit a file from a stale or hallucinated view of its
contents, or overwrite a change made underneath it by a formatter, the user, or
another agent. Claude Code mitigates this with a session-scoped read-before-write
precondition; we want the same guarantee, but built for this codebase's two
distinguishing constraints: durable execution (Temporal replays and cross-worker
handoffs) and a test discipline that forbids real-disk coupling in unit tests.

Duplication scan per charter §4 — VERIFIED(grep -rniE 'read.?before.?write|
CheckWritable|WriteFile|EvalSymlinks|not been read' pkg internal): no existing
read-before-write, file-guard, or `Write`/`Edit` tool code exists. There is no
file-mutation layer for an existing component to absorb this into; it is new
surface, not overlap.

Options considered:
1. **Trust the model** to read before writing. Rejected: the failure it guards
   against is precisely a model failure, so this reintroduces the failure class.
2. **Port Claude Code's mtime-based freshness check.** Rejected as the integrity
   signal: mtime is attacker-/tool-controllable (`touch -t`, `os.Chtimes`), so it
   does not detect a hostile or same-second rewrite.
3. **Content-hash guard behind a `Filesystem` seam, with serializable state.**
   Chosen.

## Decision

We will add `pkg/tools/fsguard`: a session-scoped `Guard` that records the
content **hash** observed for each file at read time and refuses a write when the
file was never read (`ErrNotRead`) or its on-disk content changed since
(`ErrStale`), keyed by a canonical path. All filesystem access goes through a
`Filesystem` interface so the logic is unit-tested against an in-memory fake.
State is exposed as a JSON-serializable `Snapshot` (for durable Temporal workflow
state and replay), and `CommitWrite` performs verify-and-write atomically against
other guarded writes. It enforces *freshness only*; path-scoping/sandboxing is a
separate concern (a future sibling), not folded in here.

## Consequences

- Easier: agent write tools get a deterministic, corrective precondition; the
  guard survives replay/compaction via `Snapshot`/`Restore`; the seam keeps the
  logic disk-free and fast to test — VERIFIED(go test -race ./pkg/tools/fsguard:
  ok, 28 tests, 95.3% coverage).
- Harder / ruled out: the out-of-process time-of-check/time-of-use window is
  narrowed but **not** closed — an external writer between `CommitWrite`'s verify
  and write is still possible (would need OS atomic primitives). `CommitWrite`
  serializes guarded writes under one lock (fine for sequential tool calls,
  coarse under heavy concurrency). Freshness hashes the whole file per check
  (O(size)). The guard is **not** a sandbox — it does not bound write
  destinations, so a path-scope component is still required alongside it.
- Lifespan: permanent. This is foundational infrastructure for the tool layer,
  not a spike; it is expected to gain siblings (path-scope, edit-region
  coverage) rather than be discarded.
