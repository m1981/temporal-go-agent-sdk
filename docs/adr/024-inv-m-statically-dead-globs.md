# ADR-024: INV-M refuses statically-unreachable globs at intake (H5 follow-up; amends ADR-023)

Status: Accepted (2026-07-19, operator) — from an adversarial verifier pass
on ADR-023. Amends ADR-023, whose completion claim (tr-fe1169f4)
**diverged** for overclaiming. Adds a real intake refusal (behavior
change: some previously-accepted globs are now refused). Implemented in
CLI v0.9.8. Core tests test_dead_glob_paths_refuses_unreachable,
test_dead_glob_paths_keeps_reachable; canary FAULT T gains a
degenerate-glob-refused arm.
Date: 2026-07-19
Supersedes: — (closes a class ADR-023 wrongly asserted was empty)

## Context

ADR-023 restated INV-M and asserted, to refute finding H5's "an empty glob
can never fire," that "over the `*`/`?`/`**` glob language no glob is
permanently unmatchable — so a glob is never a dead tripwire, only a
dormant one." An independent adversarial verifier (Fable, session
`s-verifier-h5-adr023`) reproduced the dormant-glob result but **refuted
that universal sentence** and correctly `diverge`d the completion claim.

H5 had two readings. The **universal** reading — *every* empty glob can
never fire — is false: a glob over a *reachable* namespace is dormant and
fires when the namespace fills (ADR-023, still correct). The
**existential** reading — *there exists* an accepted glob-exempt tripwire
that can never fire — is **true**. `dead_literal_paths` exempts any path
containing `*` or `?`, but several glob shapes match no path
`git diff --name-only` could ever emit, because diff paths are
repo-relative, `/`-separated and normalized:

- absolute: `/etc/*.conf` (a diff path never starts with `/`)
- trailing slash: `zone/*/`, `a*/` (a diff path never ends in `/`)
- parent/dot components: `../*.txt`, `./src/*.py`, `a/./b*.py`
- empty component: `dbl//*.txt` (git normalizes `//` away)
- under the git dir: `.git/*`, `.git/**` (git never tracks under `.git`)

Each was accepted at intake and produced **0 stale** after every adjacent
namespace was populated (verified twice, in the author's and the
verifier's sandboxes). These are dead tripwires — exactly what INV-M
exists to catch — and, crucially, unlike the tracked-**symlink** residual
(whose deadness needs link resolution), they are **statically decidable
from the pattern string alone**. A residual you can decide cheaply should
be closed, not documented.

## Decision

**Refuse a statically-unreachable glob at intake** (`dead_glob_paths`,
checked immediately after the zero-match-literal check, on any claim
carrying `evidence_paths`). Splitting the pattern on `/`, a glob (a path
containing `*` or `?`) is refused when: its leading component is exactly
`.git`; or any component is empty (absolute path, trailing slash, or
`//`), `.`, or `..`. The message points the author at a reachable
repo-relative pattern (`dir/**`, `dir/*.py`).

This is **sound**: every pattern it refuses is provably unreachable, so
there are **no false refusals** — a wildcard component still matches real
names, so `*`, `a*`, `.git*` (matches `.gitignore`), and `.github/**` all
pass. It is **not complete** (cf. ADR-021's lesson): exotic dead globs —
e.g. a nested-submodule `.git` deeper in the path — may still slip, and
the tracked-symlink literal remains the residual that is *not* statically
decidable. INV-M therefore refuses the *decidable* dead tripwires
(comma-typo literals, zero-match literals, unreachable globs) and names
the *undecidable* residual (symlink) as guidance ("watch real, reachable
paths"). No completeness claim is made or implied.

The check is intake-only. It never retroactively invalidates an existing
claim, so no deployed ledger breaks; a claim already carrying a dead glob
stays as-is (already a dead tripwire), and only *new* ones are refused.

## Consequences

- The completion of H5 (wk-dc763341) is honest only with this ADR: the
  meta-restatement and the dormant-glob lock from ADR-023 stand, but "the
  symlink is the lone residual" / "no glob is permanently unmatchable" are
  corrected here and in the paper/README/tutorial. ADR-023 carries an
  `Amended by: ADR-024` note.
- Behavior change (first in this batch): previously-accepted unreachable
  globs are now refused. The shipped allowlists and every fixture use
  reachable patterns, so nothing in-tree is affected.
- Locked mechanically: core `test_dead_glob_paths_refuses_unreachable`
  (the shapes above are flagged) and `test_dead_glob_paths_keeps_reachable`
  (reachable globs, incl. `.git*` and `.github/**`, are not); canary
  `FAULT T` gains an arm that files a `.git/*` glob and asserts intake
  refuses it.

## Non-goals

Not claiming completeness (some exotic dead globs and the symlink residual
remain — guidance covers them). Not resolving symlink targets at intake
(undecidable at the path level; unchanged). Not refusing reachable globs
over empty-for-now namespaces (those are dormant, not dead — ADR-023).
