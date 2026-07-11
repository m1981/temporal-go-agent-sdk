# fsguard — read-before-write guard (feature spec)

> Reader: any agent extending fsguard or building a file-mutating tool on it | Enables: knowing the guard's current guarantees, open work, and acceptance criteria without re-reading the source | Update-trigger: a cited claim goes stale/diverged, a cited wk- issue closes, or ADR-007 is superseded

Facts here are authoritative only as ledger ids (`tr-`/`wk-`); the prose beside
each id is courtesy, not truth. Judge the ids with `bash scripts/spec-health.sh`.

## Decision

Grounded in **ADR-007** (`docs/adr/007-*.md`): a session-scoped read-before-write
guard, freshness by content hash, all filesystem access behind a `Filesystem`
seam, serializable `Snapshot` state for Temporal replay, atomic `CommitWrite`.
Reference the decision by number, never by title.

## Current facts

- **tr-1726ec57** — the guard's behavior is covered by a green `-race` suite.
- **tr-dc6b174d** — freshness is a content hash of the *current on-disk bytes*
  (`hashBytes(current)`), not a timestamp; this is the security invariant that
  defeats mtime-forgery.
- **tr-00eded8e** — the `read_file`/`write_file` tools (`pkg/tools/file`) route
  mutations through `CommitWrite`; an unread overwrite is refused. First real
  consumer of the guard.
- **tr-16104518** — `pkg/tools/pathscope` (ADR-008) bounds where those tools
  may reach: paths resolving outside the workspace root (traversal, absolute,
  symlink escapes) are refused before any filesystem or guard access, via
  `file.NewOSInWorkspace`.
- **tr-d38998db** — edit-region coverage (ADR-009): a partial read no longer
  authorizes an edit outside its observed line span; `CheckEditable` refuses
  it with `ErrRegionNotRead`, additive to the freshness check.
- **tr-b9e3683f** — atomic commit primitives (ADR-010): `CommitWrite` refuses
  a raced external create (`ErrConcurrentCreate`, O_EXCL) and replaces
  existing files via temp+rename so readers never see a torn write; the
  existing-file TOCTOU window is narrowed, **not closed** — the residual is
  named in ADR-010.

## Scope and guarantees (courtesy prose)

The guard enforces **freshness only**: it refuses a write when the target was
never observed (`ErrNotRead`) or changed since it was observed (`ErrStale`),
keyed by a canonical path. It is deliberately **not** a sandbox — it does not
bound *where* a write lands (that is wk-93dc3566). The out-of-process
time-of-check/time-of-use window is hardened but not eliminated: a raced
create is refused and overwrites publish atomically (tr-b9e3683f), while an
external modification in the final re-read-to-rename gap is still overwritten
(ADR-010, Residual risk — a POSIX limit).

## Open work

- ~~wk-8d3834f9 — wire fsguard into a Write/Edit tool~~ — **shipped**, see
  tr-00eded8e.
- ~~wk-93dc3566 — workspace path-scoping sibling that bounds write
  destinations (the ADR-007 boundary: freshness ≠ sandbox)~~ — **shipped**,
  see tr-16104518.
- ~~wk-3c9b615d — edit-region / read-range coverage, so a partial read does
  not authorize an edit outside the observed span~~ — **shipped**, see
  tr-d38998db.
- ~~wk-2f8c87bf — close the out-of-process TOCTOU in `CommitWrite` via OS
  atomic primitives~~ — **shipped as a hardening, not a closure** (POSIX has
  no content compare-and-swap; residual window in ADR-010), see tr-b9e3683f.

## Acceptance (pre-written `done --claim` texts)

File each only *after* the shipping commit (a completion claim filed before its
commit trips its own path tripwire):

- wk-8d3834f9 → "A Write/Edit tool routes every mutation through
  fsguard.CommitWrite; an integration test proves an unread overwrite is refused."
- wk-93dc3566 → "Writes resolving outside the configured workspace root are
  refused before touching disk; covered by tests."
- wk-3c9b615d → "fsguard refuses an edit whose byte/line span was never observed
  by a Read; covered by tests."
- wk-2f8c87bf → filed as tr-b9e3683f, deliberately scoped **tighter** than the
  text pre-written here: "verify-and-write atomically against an out-of-process
  writer" overclaims what a content-hash guard on POSIX can guarantee. The
  filed claim names the guarantees added (O_EXCL create refusal, atomic
  replace, late re-verify) and that the existing-file residual window remains
  per ADR-010.
