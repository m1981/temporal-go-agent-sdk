# ADR-008: Workspace path-scoping for file tools (pathscope)

> Status: Accepted — with a KNOWN DEFECT (2026-07-12)
> Date: 2026-07-10
> Supersedes: —

> **KNOWN DEFECT (2026-07-12):** the Consequences/Context claim that pathscope
> "catches … symlinks inside the root pointing outside it" is FALSIFIED. A raw
> `<root>/link/../x` path (link→outside) is cleaned lexically by Check but
> written on the raw path by the OS, escaping root. Tracked as claim
> tr-8f969e5d (+ write-side tr-3ef6f8ff); fix wk-20a409b1. This banner is the
> one sanctioned amend (ADR_AMEND); the decision itself is not being revised.

## Context

ADR-007 shipped a read-before-write guard for file-mutating agent tools and
explicitly ruled destination bounds out of its scope: "The guard is **not** a
sandbox — it does not bound write destinations, so a path-scope component is
still required alongside it." Without that component, `write_file` can be
steered (by a hallucinating or prompt-injected model) to any path the process
can reach — `../../etc/passwd`, an absolute path outside the project, or a
path through a symlink that lives inside the workspace but points outside it.

Why ADR-007's component cannot absorb this: freshness and destination bounds
are different invariants with different lifecycles. Freshness is *session
state* (what has this session observed?), mutable on every read; a workspace
bound is *configuration*, immutable per deployment. Folding the bound into the
guard would also make the bound bypassable by anything that legitimately skips
the guard (fresh creates need no prior read, yet must still be bounded), and
would couple a pure predicate to the guard's locking and snapshot machinery.

Duplication scan per charter §4 — VERIFIED(grep -rniE
'workspace|path.?scope|outside|EvalSymlinks|contains.\*root' pkg internal
--include='\*.go'): the only canonicalization code is
`fsguard.OSFilesystem.Canonical` (identity keying for freshness, not a bound);
the remaining hits are unrelated prose ("outside the lock", "outside a managed
runtime"). No existing component bounds path destinations; this is new
surface, not overlap.

Options considered:
1. **Prefix-match the raw path string against the root.** Rejected: defeated
   by `..`, by relative spellings, by symlinks inside the root pointing
   outside it, and by siblings sharing a name prefix (`/w/app` vs
   `/w/app-evil`).
2. **chroot / OS-level sandboxing.** Rejected for now: not portable across the
   platforms the SDK targets, needs privileges, and constrains the whole
   process rather than one tool bundle.
3. **A leaf package with a `Scope.Check` over canonicalized paths, behind a
   canonicalization seam.** Chosen.

## Decision

We will add `pkg/tools/pathscope`: a `Scope` configured with a workspace root
whose `Check(path)` returns nil only when the path, canonicalized (absolute,
symlinks resolved — for a not-yet-existing target via its parent directory —
and `..` cleaned), is the root or strictly inside it; anything else gets the
static sentinel `ErrOutsideWorkspace`. Canonicalization goes through a minimal
`Canonicalizer` seam — the one-method slice of `fsguard.Filesystem` that
pathscope needs — so unit tests run against an in-memory fake while production
reuses `fsguard.OSFilesystem` (no duplicate resolution logic, and a Scope
cannot touch file contents by construction). `pkg/tools/file` gains
`NewOSInWorkspace(root)`, which checks the scope in both tools *before* any
filesystem access or guard call; `New`/`NewOS` stay unscoped and unchanged.

## Consequences

- Easier: agent file tools get a deployment-configurable sandbox boundary that
  catches the real escape vectors (`..` traversal, absolute paths, symlink
  escapes — including creates under a symlinked parent, via the parent-dir
  resolution inherited from ADR-007's `Canonical`); the error text is static,
  so refusals leak neither the path nor the root back into the model context —
  VERIFIED(go test -race -cover ./pkg/tools/pathscope ./pkg/tools/file: ok,
  31 tests, 100% / 95.3% coverage).
- Harder / ruled out: this is an in-process check, not an OS boundary — code
  that bypasses the tool layer (or a TOCTOU where a path component is swapped
  for a symlink *between* `Check` and the write) is out of scope; closing that
  needs OS primitives (the same boundary as wk-2f8c87bf). Every checked path
  costs symlink resolution (syscalls per component). Scoped tools also refuse
  *reads* outside the root, which is deliberate (exfiltration channel) but
  means legitimate out-of-tree reads need an unscoped bundle.
- Lifespan: permanent — like ADR-007, foundational tool-layer infrastructure,
  expected to gain consumers (every future file-touching tool), not to be
  discarded.
