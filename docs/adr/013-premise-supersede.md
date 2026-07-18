# ADR-013: Premise supersede — an auditable redirect for dead premises

Status: Accepted (2026-07-13, operator) — proposed 2026-07-12 as FS-5 in
`docs/field-notes-sdk-session.md` item 2 (second deployment), filed as
wk-8d966a5b, implemented in CLI v0.6.4. Canary FAULT R10.
Amended by: note (2026-07-18, wk-d6e00f93) — an independent spec review
(HIGH-2) found the Decision's "cycles stop at the first repeat"
under-specified: it named the halt condition but not *which value*
becomes the effective premise. Precise rule, matching the shipped
`apply_supersedes` and now pinned by core tests: the walk follows each
premise's redirect chain until it reaches either a claim with no
redirect (a clean chain — resolves to that terminal claim) or a claim
it has already visited (a cycle — resolves to that first-repeated
value). Concretely: a 2-cycle A→B→A entered at A resolves back to A
(the redirect is a deterministic no-op, never an escape to an arbitrary
node), and a chain-into-cycle P→Q→R→Q resolves to Q (the cycle's entry
point). The result is deterministic, independent of iteration count and
of event order, and still passes through ADR-001's matrix — a cyclic
redirect cannot bypass premise validity, it only fails to change it.
Date: 2026-07-13
Supersedes: — (extends ADR-002's kernel; leaves ADR-001's matrix intact)

## Context

Premises only accumulate: premise-at-birth links live in the immutable
issue payload (first-wins, ADR-006) and `truth premise` records only
add. `join_ready` blocks on ANY broken premise, and `premise_check`
blocks stale/diverged/retracted/missing unconditionally. So when a
premise dies *genuinely* — the fact was wrong, a corrected claim is
filed under a new id — the work item stays HELD forever: an honest
verifier cannot `agree` the dead claim live again, and retraction still
blocks. The second deployment hit exactly this; its only exit was
cancel-and-refile (`wk-dcc7a92d` → `wk-0eaee8d9`), which broke every
reference to the old id in specs, resume notes, and an ADR.

## Decision

`truth premise <issue> <new-tr> --supersedes <old-tr>` appends a
`premise` record whose payload carries `supersedes`. Two halves:

**Fold half — permissive and confluent.** `fold_supersedes` collects
redirects as `(issue, old) -> new`, last-wins in the same `(ts, id)`
total order every other fold uses. `apply_supersedes` rewrites each
issue's premise list AFTER `merge_premises`, so premise-at-birth links
in the immutable payload redirect too; chains follow to a fixed point,
cycles stop at the first repeat. Redirects are scoped to one issue —
superseding a claim for wk-A never touches wk-B's link to it.

**Intake half — strict.** Refused unless: `supersedes` is a tr- id and
differs from the replacement; the replacement claim exists in the
ledger; the old claim is currently a premise of that issue (after
redirects); and the old premise is NOT live or unverified — those pass
ready as-is, so a redirect could only launder protection away. Dead
states (stale, diverged, retracted, cannot_verify, missing) qualify.

**What this deliberately is not.** Not removal: the redirect points at
a replacement that is itself judged by the unchanged ADR-001 matrix —
an unverified replacement warns, a stale one still HOLDs. Not history
editing: the old premise link, the redirect, and the replacement are
three permanent records; `git log` shows who redirected what, when,
and to which claim.

## Explicit non-goals

No bare detach (a premise-ectomy with no replacement would be exactly
the ADR-001 stripping F7 closed). No redirect for external tracker
premise *targets* — `supersedes`/`claim` are tr- ids; the issue id may
be external. No fold-level cycle refusal — intake cannot see future
appends, so the fold degrades deterministically instead.

## Consequences

Easier: correcting a fact no longer costs the work item's identity;
references to wk- ids survive the death of the facts beneath them.
Harder: one more premise state to reason about when reading raw
records (the *effective* premise list is derived, like every status);
`ready`/`impact` now share one more derivation step, kept as two pure
functions with unit and permutation coverage.

Canary FAULT R10 (four arms): supersede refused while the old premise
passes ready; HELD observed on the stale premise; supersede accepted
once dead; ready releases the issue after the redirect. Conformance:
schema and stdlib mirror both accept a valid `supersedes` and reject a
malformed one (FS-2 corpus fixtures).

Falsifier: a HELD issue released by a redirect whose replacement claim
would not itself pass the ADR-001 matrix — that would mean the
redirect bypassed validity rather than re-targeting it.
