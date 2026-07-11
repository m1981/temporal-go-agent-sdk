# ADR-010: Atomic commit primitives for fsguard's TOCTOU window

> Status: Accepted
> Date: 2026-07-11
> Supersedes: —

## Context

ADR-007 shipped `CommitWrite` with an explicitly acknowledged gap: the
out-of-process time-of-check/time-of-use window is "narrowed but **not**
closed — an external writer between `CommitWrite`'s verify and write is still
possible (would need OS atomic primitives)". `writeMu` serializes guarded
writes against each other, but between the freshness re-read and the
`WriteFile` call another *process* can create or modify the file, and the
plain truncate-and-write then clobbers it. A concurrent reader can also
observe a torn (partially written) file mid-`WriteFile`. This ADR spends the
OS atomic primitives that ADR-007 deferred.

Duplication scan per charter §4 — VERIFIED(`grep -rniE 'O_EXCL|os\.Rename|
atomic.?write|CreateTemp|flock|O_CREATE' pkg internal --include='*.go'`): no
existing atomic-write, exclusive-create, rename, or file-locking code in the
repo outside test fixtures' plain `os.WriteFile`. Nothing to reuse; no overlap.

Options considered:

1. **Advisory file locking (`flock`) around check+write.** Rejected: advisory
   locks only constrain cooperating processes — the external writers this
   guards against (formatters, users, other agents) do not take the lock —
   and they are unreliable on NFS. It would add a platform-specific
   dependency for no guarantee against exactly the writers that matter.
2. **Accept ADR-007's status quo.** Rejected: two concrete sub-races ARE
   closable with standard POSIX primitives (lost create race via `O_EXCL`;
   torn reads via rename atomicity), and leaving them open makes every
   guarded create a silent-clobber hazard.
3. **Kernel compare-and-swap on content.** Does not exist in POSIX. A
   userspace emulation (read-verify inside a lock the adversary ignores)
   collapses to option 1. Ruled out by the platform, not by us.
4. **`O_EXCL` creates + write-temp-then-rename overwrites, with the freshness
   re-read moved as late as the seam allows.** Chosen: it is the strongest
   guarantee POSIX offers a content-hash guard, and the residual is small,
   precisely describable, and documented below.

## Decision

We will replace the `Filesystem` seam's `WriteFile` with two purpose-built
atomic primitives and rebuild `CommitWrite` on them:

- `CreateExclusive(path, data, perm)` — `O_CREATE|O_EXCL`; fails with
  `fs.ErrExist` if the path exists. `CommitWrite` uses it whenever its
  freshness re-read said "no file": a create raced in by another process
  makes the commit fail closed with the new static sentinel
  **`ErrConcurrentCreate`**, and the external file survives untouched.
  `ErrConcurrentCreate` is distinct from `ErrStale` because `ErrStale`
  presumes a prior read ("read it *again*"); a raced create was never read,
  and the model's corrective action is a first read. Its message is static
  and path-free per the ADR-007 prompt-injection rule.
- `WriteFileAtomic(path, data, perm)` — stages a temp file in the target's
  own directory (rename is atomic only within one filesystem), fsyncs, and
  `os.Rename`s it over the target. A concurrent reader observes the complete
  old bytes or the complete new bytes, never a torn intermediate, and the
  path never transiently disappears. An existing file keeps its permission
  bits; a fresh target gets `perm`.

`CommitWrite` now performs its freshness re-read immediately before the write
call, under `writeMu`, so the unavoidable gap is a single seam call rather
than check → canonicalize → write. `WriteFile` is removed from the seam
(VERIFIED: its only caller was `CommitWrite`; `pkg/tools/file` holds the seam
but calls only `ReadFile`), keeping the interface minimal instead of carrying
a dead method every implementor must still write. The test fake gained a
`writeHook` that fires between the guard's check and the fake's mutation, so
the race is simulated deterministically in unit tests.

## Residual risk

**The TOCTOU window for existing files is narrowed, not closed.** An external
modification that lands after `CommitWrite`'s final freshness re-read but
before the rename inside `WriteFileAtomic` is still silently overwritten.
This is a POSIX limit, not an implementation shortfall: there is no atomic
"rename-if-content-still-hashes-to-X" primitive, and any userspace emulation
relies on locks an uncooperative writer ignores (option 1). What IS now
guaranteed: a raced **create** is always refused (`O_EXCL` is kernel-
enforced), readers never see torn content, and the modify window shrank to
one stat+temp-write+rename sequence. The residual is pinned as executable
documentation by
`TestCommitWrite_ExistingFile_RaceAfterFinalVerify_ResidualOverwrite` —
if that test ever fails, the window changed and this
paragraph must be updated with it. Additionally, `CreateExclusive` publishes
a *new* file non-atomically (a reader may glimpse a partially written new
file); accepted because there is no prior content to tear.

## Consequences

- Easier: guarded creates are clobber-proof against racing processes;
  guarded overwrites are torn-read-proof; the failure surface is explicit
  (`ErrConcurrentCreate`) instead of silent. Covered by the fsguard suite —
  VERIFIED(`go test -race -cover ./pkg/tools/fsguard/`: ok, 97.1% coverage).
- Harder / trade-offs: temp+rename allocates a **new inode**, so hardlinks to
  the target are silently detached and tools watching the old inode (some
  editors, `tail -f`) lose track; the temp file must live in the target's
  directory (same-filesystem requirement), so the directory needs write
  permission even for an in-place edit; each overwrite costs extra syscalls
  (stat, create, chmod, fsync, rename) versus one `write`. Removing
  `WriteFile` is a breaking change for external `Filesystem` implementors
  (pre-1.0; CHANGELOG'd in the same commit per the Type A guardrail).
- Lifespan: permanent, same as ADR-007 — this completes the guard's write
  path rather than extending it sideways.
