# ADR-015: Canonical timestamp profile — string order must equal time order

Status: Accepted (2026-07-18, operator) — source: independent spec-only
review (pi agent, 2026-07-17), findings HIGH-1 (offset heterogeneity
breaks INV-I) and MEDIUM-4 (draft-07 `format` is annotative; nothing
enforced ts form). Implemented in CLI v0.8.1. Canary faults TS1–TS3;
four conformance fixtures; the FS-2 mutant generator exercises the
constraint on every valid seed. Discharges ADR-008's deferred F5 check.
Date: 2026-07-18

## Context

The fold's total order `(ts, id)` compares the raw `ts` STRING — a
deliberate v0.6.2 decision (ADR-008/F2: parse-then-compare abstained on
naive and junk timestamps, and a forged ts slipped past the parsed
comparison; the string is what actually orders the fold, so the string
is what must be checked). But nothing constrained the string's *form*.
The schema's `format: "date-time"` is annotative in JSON Schema
draft-07 — `Draft7Validator` without an armed format checker enforces
nothing (the F1 fail-open lesson, hiding inside a keyword) — and
`validate`'s stdlib mirror never looked at `ts` at all.

Lexicographic order equals temporal order only on a fixed-width,
single-offset, fixed-precision form. ISO 8601 admits many others, and
each breaks the equality a different way:

- **Offset variance**: `2026-07-17T10:00:00.000000+05:00` string-sorts
  before `...T10:00:00.000000+00:00` yet denotes an instant five hours
  *earlier* — same-instant events written in different offsets order
  arbitrarily.
- **`Z` vs `+00:00`**: both mean UTC, but ASCII `Z` (90) > `+` (43), so
  the two spellings of one instant interleave wrongly.
- **Variable precision**: `...T10:00:00.5` sorts after
  `...T10:00:00.123456` but is temporally earlier.

No adversary is needed: an honest second writer — another
implementation, a raw-append script, a port — using any of these forms
silently misorders events and falsifies INV-I (confluence), the
property CRDT replay depends on. This is a different threat class from
the accepted fresh-id ts *forgery* residual (§8 item 6 of the paper):
forgery needs an adversary; this needed only a second tool.

## Decision

Three moves, smallest change that makes string order equal time order:

**(a) The profile.** `ts` must match
`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$` — fixed-width
(32 chars) UTC microseconds, exactly what `now_iso()` has emitted since
the v0.4 F3 repair. Enforced in **both** contract surfaces in lockstep:
a `pattern` on the schema's `ts` (patterns are assertive in every
draft-07 validator, unlike `format`) and a `TS_RE` check in
`validate_events`. The FS-2 mutant generator already mutates every
string envelope field on every valid seed, so the corpus holds the two
surfaces together mechanically; four fixtures pin the named bad forms
(Z-suffix, non-UTC offset, missing microseconds, tz-naive). Because the
commit gate runs `validate`, a nonconforming record is refused at
commit with no new gate — the same delivery ADR-008 used.

**(b) TRUTH_NOW normalization.** The test hook is the one path that
could mint a nonconforming record through the CLI itself: `now_dt()`
now normalizes the override — `Z` accepted and rewritten, naive assumed
UTC, aware converted to UTC — so `now_iso()` renders the profile from
any reasonable override.

**(c) Clock-push at append** — the "physical clock catch-up" half of a
Hybrid Logical Clock (Kulkarni et al. 2014; CockroachDB's design), and
nothing more. A record appended by the CLI must not sort before the
ledger tail it causally follows. If the real clock reads at-or-before
the tail's (canonical) ts, the new record's ts becomes tail + 1 µs —
absorbing same-machine append races and small clock steps. Bounded by
ADR-008's `SKEW_TOLERANCE_SECONDS` (300 s): beyond it the honest clock
is kept and `order_check`'s existing regression warning fires, so a
forged far-future tail cannot drag every subsequent record's ts with
it. `TRUTH_NOW` disables the push — seeded backdating is the hook's
purpose (canary FAULT D). The push compares against the file *tail*,
not the max ts: within one history file order is append order (INV-A),
and the tail is the event the new append causally follows.

## Explicit non-goals

Not timestamp *trust*: `ts` remains self-attested; fresh-id backdating
stays the accepted §8 item 6 residual, and signed records stay behind
their growth gate (§10). Not leap-second correctness: `23:59:60` fails
the pattern; a smeared or stepped clock is accepted (the TAI64N
alternative below handles it, at an unacceptable readability cost). Not
retroactive repair: a legacy nonconforming line in an adopter's ledger
makes `validate` fail permanently, and the append-only invariant means
it cannot be edited away — **check before upgrading** (one grep:
every `ts` against the profile); a repo with nonconforming history
should stay on v0.8.0 until a migration story exists. All three
template deployment sites were swept (2026-07-18): every record
conforms, because every record was CLI-minted.

## Alternatives considered

- **TAI64N labels** (djb, daemontools): fixed-width, sortable,
  leap-second-proof — the append-only-log ancestor of this problem.
  Rejected: unreadable in a plain-files-first design.
- **Timestamp-encoding ids** (ULID / UUIDv7 / KSUID): fold order from
  the id alone, ties impossible. Rejected: `tr-`/`wk-` ids are
  content-derived (the id commits to the payload), and every existing
  citation would break.
- **Full HLC field**: a logical counter beside the wall clock.
  Rejected as a record-format change a 1 µs push achieves for this
  regime's write rates; the fold's `(ts, id)` tie-break already plays
  the counter's role.
- **Parse-and-normalize in the fold** (accept any ISO form, compare
  instants): re-opens exactly the F2 hole ADR-008 closed — the fold
  would order by something other than what a string-diffing gate can
  check. The fold stays dumb; the gate stays honest.
