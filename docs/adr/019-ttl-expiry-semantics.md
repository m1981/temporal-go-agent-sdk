# ADR-019: TTL expiry is scan-materialized, counted from the claim ts, strict boundary (H2)

Status: Accepted (2026-07-18, operator) — source: independent review
finding H2 (High), a spec-precision defect confirmed against the shipped
CLI. Ratifies the existing v0.2 implementation as normative; no behavior
change. Canary FAULT D (fold-clock-free arm); core tests
`test_ttl_boundary_is_strict_from_claim_ts`,
`test_fold_never_synthesizes_ttl_expiry`.
Amended by: note (2026-07-19, wk-8c4a6b9d) — an independent review
(finding B-Maj2) demonstrated in a sandbox the workflow consequence this
ADR's Non-goals imply but never spelled out: a TTL-expired claim that is
re-verified `agree` goes `live` and is then re-staled by the immediately
following scan, forever, because the TTL clock counts from the claim `ts`
and no verdict restarts it (by design, per Non-goals). The operational
rule is therefore: **an expired TTL claim is re-filed, not re-verified**
— re-verification is the recovery path for *path-anchored* stales only
(F2's effective anchor advances; no TTL analogue exists, deliberately).
The paper's INV-J row is scoped to path-anchored claims accordingly, and
Reference 7's DNS annotation now states the divergence (a DNS re-fetch
restarts the TTL; here only re-filing does).
Date: 2026-07-18
Supersedes: — (pins prose underspecified in paper §1 / §4, the fold
table, and INV-E; leaves the code path unchanged)

## Context

`ttl_days` demotes a claim about a fact git cannot watch (an external
API, a vendor doc — G10) once the fact is old enough to distrust. H2
observed that the normative prose left three things undecidable, so two
conforming implementations would produce different `truth ready`/`stale`
output on the same ledger:

1. **The reference instant.** TTL counts from *what* — the claim's `ts`,
   the anchor commit's time, or the `agree` verdict that made it live?
2. **The boundary.** Expired at `now > ts + ttl_days`, or `>=`?
3. **The clock during a fold.** §4 called the core "a pure function of
   time [that] touches no I/O," yet expiry needs the current wall-clock —
   ambient input. Read literally the two cannot both hold, and the fold
   table lists `invalidation → stale` as the *only* stale path, implying
   "no record ⇒ never stale." So: is TTL a fold-time computation or a
   scan-emitted record? The prose supported both.

## Decision

Ratify the shipped implementation (`_ttl_expired`, `cmd_invalidate_scan`)
as the normative specification:

- **Reference instant — the claim's own `ts`.** TTL encodes "distrust
  this assertion N days after it was made," so it counts from the instant
  the claim was asserted, *not* from any later verdict or from the anchor
  commit. An `agree` re-verification does not restart the TTL clock (it
  updates readiness `since`, a different field). For an INFERRED/UNVERIFIED
  claim there is no verdict anyway, so `ts` is the only coherent anchor.
- **Boundary — strict `>`.** A claim expires when *more than* `ttl_days`
  have elapsed: `(now - ts) > ttl_days * 86400` seconds. At exactly
  `ts + ttl_days` it is **not yet** expired; expiry begins one unit past.
- **The fold is clock-free; expiry is scan-materialized.** The fold is a
  pure function *of the log* — it reads no clock and never synthesizes
  expiry. The **invalidation scan** (`truth invalidate-scan`, the
  post-merge hook) is the sole clock reader: it evaluates `_ttl_expired`
  against `now`, and on a hit **appends an invalidation record** naming
  the claim. Only then does the fold demote the claim to `stale`, via the
  ordinary `invalidation → stale` edge. So the fold table is both
  correct and complete: a TTL'd claim with no invalidation record in the
  log is *not* stale, however old — the clock enters the system only
  through the durable record the scan writes, never through fold-time
  I/O. "Implementer 2" in the H2 write-up is the intended reading;
  "implementer 1" (fold reads the system clock) is ruled out here.

## Consequences

- The fold retains its two load-bearing properties — purity and
  confluence (INV-I): replaying the same log yields the same statuses on
  any machine at any wall-clock, because the clock's effect is frozen
  into a record at scan time, not recomputed on read. This is exactly why
  unit attacks on the core stay cheap (§4).
- The one misleading phrase is corrected: §4 now says the core is a pure
  function *of the log* (as §1 and §9 already do), and §1 / INV-E state
  the reference instant, the strict boundary, and the scan-materialization.
- Locked mechanically: core `test_ttl_boundary_is_strict_from_claim_ts`
  (exact boundary survives, one second past expires, counted from `ts`);
  core `test_fold_never_synthesizes_ttl_expiry` (a TTL'd claim folds
  non-stale with no invalidation record present); canary FAULT D gains a
  fold-clock-free arm (a long-past TTL'd claim is *not* stale until a scan
  runs).
- No behavior change and no version bump on its own account — the CLI has
  behaved exactly this way since v0.2. Documentation catching up to code,
  plus the conformance locks.

## Non-goals

Not adding fold-time expiry (would destroy purity and confluence — a
claim's status would depend on *when* you read it, not on the log). Not
restarting the TTL clock on re-verification. Not changing the scan
cadence or making expiry continuous — it is realized only when a scan
runs, which is the intended cache-invalidation trigger (a stale fact that
no scan has visited yet is simply not-yet-detected, the ordinary
cache-miss latency ADR-003 accepts).
