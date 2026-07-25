# ADR-032: `--scope-ok` overrides carry a default expiry

Status: Accepted (2026-07-20, operator) — roadmap-v3 R12 (batch 5,
override decay), adopting candidate C4 from the 2026-07-20 clean-room
convergence analysis. Implemented in CLI v0.9.14. Core tests
TestOverrideDecay + TestScopeDecayCLI; canary FAULT SD-decay (4 arms
incl. negative control).
Date: 2026-07-20
Amends: ADR-007 (the quantifier-scope override gains decay; its adoption
gate gains an instrument — see ADR-033). Leans on: ADR-019 (TTL
semantics UNCHANGED — counted from the claim ts, strict boundary,
scan-materialized, never reset by re-verification); ADR-030 (arm 1
routes an expired override to re-file).
Supersedes: —

## Context

ADR-007 refuses a universally quantified claim over a scoped evidence
command unless the author files `--scope-ok "<sentence>"`, storing the
sentence as `scope_basis`: the scope judgment becomes attackable ledger
content instead of an invisible mismatch. ADR-007's own adoption gate
asks whether that override is being *used well* — but an override, once
filed, is permanent. A `scope_basis` judgment made once (correctly or
not) sits live forever unless a watched path happens to stale the claim
or a verifier happens to attack the sentence. The dominant real failure
mode ADR-007 addresses is *scope drift*: a claim whose scope was fine
when filed but whose sentence silently stopped covering the quantifier
as the code moved. Nothing re-asks the question.

## Decision

A `scope_basis` claim filed **without** an explicit `--ttl-days` is
stamped a default `ttl_days = DEFAULT_OVERRIDE_TTL_DAYS` (30) and
`ttl_default: true`; the CLI prints a one-line stderr notice and files
normally. It **never refuses**.

**Pure core.** `override_decay(scope_basis, ttl_days)` returns
`(ttl_days, ttl_default_flag, notice_or_None)`:

- `scope_basis` present AND `ttl_days is None` → `(30, True, notice)`;
- an explicit `ttl_days` → `(ttl_days, False, None)` — the visible
  opt-out, unchanged even when a `scope_basis` is present;
- no `scope_basis` → `(ttl_days, False, None)`, unchanged.

No clock is read in the core. `build_claim_payload` applies the decay
before the VERIFIED intake check reads `ttl_days`, so the effective TTL
rides the ordinary machinery; `cmd_claim` and the `done --claim` path
print the notice after a successful append.

**Expiry is the ADR-019 path, untouched.** `_ttl_expired` and the fold
are NOT modified. The default TTL is counted from the claim's own `ts`
with the strict boundary, materialized only when a scan runs. When it
lapses, ADR-030 arm 1 reads the scan-stamped `reason_code: "ttl"` and
routes the stale claim to **re-file** (a TTL claim is never re-verified —
ADR-019). Re-filing re-fires the ADR-007 gate. **That loop is the
mechanism's point:** expiry mechanically re-asks whether the scope
judgment was ever real, rather than trusting a one-time sentence forever.

**Schema and mirror.** The claim payload gains an optional boolean
`ttl_default`, added independently to the JSON Schema and the stdlib
mirror (`validate_events`) and held in lockstep by the FS-2 conformance
corpus and its generated-mutant test. The field addition bumped the
schema `$id` (v0.9 → v0.10).

## Consequences

Easier: a scope override cannot rot silently for longer than a month; a
drifted `scope_basis` surfaces for re-examination on a schedule, not by
luck. The `ttl_default` flag lets ADR-033 and any auditor distinguish a
decay expiry from a genuine diverge. Harder: nothing mechanical — no
fold change, no new status; a defaulted TTL is an ordinary `ttl_days`
any fold since v0.2 handles, and `ttl_default` rides the open payload.
Friction: a scope-ok claim about a genuinely stable fact now re-files
monthly unless the author passes a large `--ttl-days` — accepted, and
bounded by the adoption gate below.

**Boundary on the FS-1 half-life (red-team fix).** The default TTL is
administratively caused (this ADR's `ttl_days` value, not a drift the
world exposed), so counting a default-TTL expiry as a live→stale
half-life observation would make `ttl_suggestion` circular — it would
suggest back the very default that produced the observations, which
would then cluster at that default. So `half_life_observations` now
**excludes TTL-reason invalidations** (structured `reason_code == "ttl"`,
with the `is_ttl_reason` prefix as the pre-stamp fallback — the same
two-arm test as `ttl_staleness`, reused): the half-life medians now
measure **observed drift only** (path/anchor invalidations). The claim
still transitions to stale — fold stays authoritative on status; only
the observation is withheld. TTL expiries are not lost to the audit:
they are counted in ADR-033's `decay_expiries` instead, which is exactly
where that section reads them.

## Explicit exclusions (deliberate)

- **No decay for `screened:false` claims.** A `--evidence-unsafe-ok`
  capsule is a different admission (the command is never re-executed);
  auto-expiring it would queue re-files nobody can mechanically satisfy.
  Reopened only if a stale-in-fact unscreened claim is found unquestioned
  in the field (roadmap Backlog).
- **No `--no-ttl` flag.** An explicit large `--ttl-days` is the visible,
  auditable opt-out. A dedicated "never expire" flag would be an
  invisible one — the exact silent-permanence this ADR removes.

## Adoption gate

Instrument: `truth stats` overrides section (ADR-033). Widen the default
(shorter, or apply to more shapes) OR drop to opt-in if **override-decay
invalidations exceed genuine-diverge counts** across two consecutive
rot-free reviews (an override that only ever expires and re-files
unchanged was never catching drift — it was noise). Fold into the R11
monthly hand-audit; no threshold trips automatically until two windows
of data exist (ADR-033's calibration debt).

## Non-goals

Not verifying that the scope still covers the quantifier — that remains
the verifier's job (ADR-007). Not a new expiry mechanism: ADR-019 is
unchanged, and the deliberate re-file-not-renew loop is ADR-030's, not a
new code path. Not tamper-proofing: a raw-appended claim omitting
`ttl_default`, or carrying a forged large `ttl_days`, is the same
accepted forged-record residual as everywhere (paper §8 item 6).

Falsifier: a scope override whose scope demonstrably drifted, filed with
a default expiry, that lapses and is re-filed *without* the re-fired
ADR-007 gate re-examining it — i.e. the re-file loop failing to re-ask
the question this ADR exists to re-ask.
