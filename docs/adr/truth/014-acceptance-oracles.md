# ADR-014: Acceptance oracles — an executable finish line gates `done`

Status: Accepted (2026-07-17, operator) — proposed 2026-07-12 as issue #1
(kuchnie consumer trial, v0.6.2 consumption round), extended 2026-07-15
by issue #2 (two-oracle shape + separate allowlist, from the kuchnie
two-ledger review §II.5 / I.4), filed as wk-eb59c649, implemented in CLI
v0.7.0. Canary FAULTS AC1–AC7.
Date: 2026-07-17
Supersedes: — (extends ADR-002's kernel; reuses ADR-009's screen and
ADR-011's tombstone semantics unchanged)

## Context

The work kernel (ADR-002) enforces *readiness* — deps satisfied,
premises live — but not *completion*: `truth done wk-x` accepts the
agent's word that the work is finished. Prose acceptance criteria are
something a model can rationalize past; an unenforced field filled in by
a model is noise with authority. This is the same gap ADR-010 closed for
verdicts (filer ≠ verifier) applied to "done" — the last norm on the
work seam that had not been made syntax.

Two design forces surfaced when the finish line is a *real* oracle
rather than a lint:

1. **12207 keeps two V's the single flag would conflate.** A suite/gate
   command checks "built right" (verification); a golden-diff command —
   an exercise runner in `--strict` mode whose golden encodes
   stakeholder intent — checks "built the right thing" (validation).
   If the record cannot say which, every conformance mapping back to
   12207/29148 has to guess.
2. **Acceptance commands execute repository code by nature.** ADR-009's
   evidence screen exists precisely to keep re-executable commands
   read-only, and test runners are deliberately NOT on that allowlist.
   Screening oracles against it would force `--evidence-unsafe-ok` on
   every real oracle — the gate would teach its own bypass (the
   confused-deputy lesson the paper already recorded).

## Decision

`truth issue --accept-cmd <cmd> [--accept-kind verification|validation]`
stores `accept: {command, kind, screened}` on the issue record at birth
— the author commits to the finish line *before* doing the work,
attackable at review time like `scope_basis` (ADR-007). `--accept-kind`
defaults to `verification`; giving it without `--accept-cmd` is refused
(a shape with no oracle).

**Own allowlist, same screen.** Acceptance commands are screened against
a separate committed list, `.truth/accept-allow`, whose entries execute
repository code at `done` time — that is their purpose. The screen
*implementation* is ADR-009's, reused verbatim with a different list and
list-naming messages (a second screen implementation is forbidden — the
F1/F5 drift lesson); so bare allowlisted names per pipeline segment, no
command substitution, no path-form programs, sinks only `/dev/null`/fd
dups. Missing list fails closed. The template ships the list EMPTY:
which programs a work item may cause a later session to run is a
per-repository policy decision, stated in the file's header.

**`done` runs the oracle.** On a plain close of an issue carrying
`accept`, the command is re-screened against the *current* allowlist
(the ADR-009 intake-AND-recheck posture), executed from the repo root,
and a non-zero exit refuses the close — the issue keeps its status, and
the both-or-neither guarantee of `done --claim` (ADR-002) extends over
the oracle: nothing is appended unless the oracle passes. The close
event records `accept: {command, kind, executed: true, returncode: 0}`;
`validate` (and the schema) refuse an executed acceptance with any other
returncode — a failing oracle never closes, by contract.

**The escape hatch covers inability, never failure.**
`--accept-unsafe-ok` at filing stores `screened: false` (`done` will
then refuse to *execute* the oracle, ever — mirror of recheck's refusal
to run unscreened evidence). At `done`, the same flag closes WITHOUT
running an oracle that *cannot* run — unscreened at birth, or no longer
passing the current allowlist — stamped `accept: {executed: false,
screened: false}` on the event, visibly. It never overrides an oracle
that ran and failed: there is no flag for that, deliberately.

**Tombstones skip the oracle.** `--cancel` and `--reopen` do not run it:
killing or reviving work must not require its finish line to pass
(cancel keeps its ADR-011 human gate).

**Fold impact: none.** Acceptance is a gate at close, never a stored
status — derive-never-store is preserved; existing ledgers validate
unchanged (the `accept` objects are optional in schema and mirror).

## Why the two kinds earn a field

`done --claim` + `--accept-cmd` closes the loop the kernel reaches for:
born on live facts (premise-at-birth), dies into a demonstrated fact
(claim-at-death) whose demonstration just ran. The `kind` keeps the
12207 mapping mechanical instead of guessed — a `verification` close
says the suite passed; a `validation` close says the golden that encodes
stakeholder intent matched. Downstream (the nd-/satisfies RFC, issue
#6), validation oracles are what let a need's SATISFIED state mean
"validated", not merely "built".

## Explicit non-goals

No NL semantics, no oracle discovery, no retry policy, no timeout
policy (a hanging oracle is a broken oracle; fixing it is work, not
configuration). No per-issue allowlist overrides: policy is one
committed file. No oracle on `cancel`/`reopen`, and no stored
"accepted" status anywhere.
