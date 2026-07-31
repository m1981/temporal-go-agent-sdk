# ADR-008: File-order/timestamp coherence — the backdating gap closed by detection

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md`, implemented in CLI v0.6.0.
Canary faults B1–B2; unit permutation tests. Amends INV-G / INV-N.
Amended by: note (2026-07-12, F2) — an independent Fable review found
the v0.6.0 check incomplete: `order_check` compared *parsed* timestamps
and abstained on a tz-naive or unparseable ts, while `fold()` sorts on
the raw ts STRING — so a backdated duplicate carrying a naive or junk
ts still substituted content with `validate` green (this ADR's own
falsifier). v0.6.2 makes `order_check` compare the same string `fold`
sorts on, closing it (canary B3, B4). A redundant validate-layer non-
ISO-ts reject (F5) is deferred: it needs the JSON-schema mirror's
format:date-time enforced in lockstep or FS-2 flags drift.
Amended by: ADR-015 (2026-07-18) — the deferred F5 check shipped, and
stricter than deferred: not merely ISO-vs-junk but a single canonical
profile (fixed-width UTC microseconds), as schema `pattern` + mirror
`TS_RE` in lockstep with FS-2 holding the two together — an
independent spec-only review (pi) found `format: date-time` annotative
in draft-07 and offset heterogeneity breaking raw-string order for
honest non-CLI writers (INV-I), which met exactly this note's
condition.
Superseded by: ADR-031 (2026-07-20, v0.9.13) — for the DETECTION rule
(a) only: `order_check` now refuses ANY content-distinct duplicate id
regardless of ts relation, subsuming the strictly-earlier case. The
clock-regression warning (b) and this ADR's non-goals stand unchanged.
Date: 2026-07-11
Supersedes: — (converts the paper's §8 item 6 composition gap from
accepted to detected-at-commit)

## Context

The one open, undefended gap the paper states plainly (§1 "Fold
semantics, precisely"): a backdated duplicate-id claim record sorts
before the genuine one in canonical `(ts, id)` order, becomes "first"
under first-wins dedup, and silently substitutes claim text and evidence
under an id that may carry a live verdict. The prescribed fix (signed
records) is deferred behind a growth gate. But a detection-grade defense
exists at zero cryptographic cost, from a property the INV-A prefix gate
already guarantees: **within one repository's history, file order is
append order** — so a backdated duplicate is *visible*: it appears later
in the file than the record it sorts before.

## Decision

`truth validate` gains two order-sensitive rules; because the commit
gate (`check-truth.sh`) runs `validate` on every staged ledger, rule (a)
blocks at commit time with no new gate.

**(a) FAIL — duplicate-id backdating.** A record whose envelope id
duplicates an earlier line's id with a *strictly earlier* `ts` fails
validation. Strictly-less only: git's union merge can duplicate an
*identical* line (equal ts), and the stable fold sort keeps the
genuine-first record winning — B2 pins that legitimate shape as passing.

**(b) WARN — clock regression beyond tolerance** (300 s,
`SKEW_TOLERANCE_SECONDS`). Warning, never failure: a branch ledger
union-merged into main legitimately places older records after newer
ones, and failing there would punish the exact merge path the confluent
fold was built for.

**Documented caveat:** unlike the fold, these checks are deliberately
order-SENSITIVE — validating a re-sorted stream is not equivalent to
validating the file, because file order is the evidence.

## Explicit non-goals

Not tamper-proofing: an actor who rewrites the file *and* the git
history showing the rewrite owns the repository and sits outside every
trust boundary this regime has. Not monotonicity enforcement (breaks
legitimate merges). Signed records remain the multi-writer answer and
remain deferred (§10) — this ADR removes the *silent* path meanwhile.

## Consequences

Easier: INV-G's and INV-N's open caveats tighten from "accepted,
undefended" to "detected at commit"; the attack now requires committing
a validate-failing ledger past the gate (visible) or rewriting history
(visible in reflog/remote). Harder: `validate` acquires its first
order-sensitive rules, with the caveat above.

Falsifier: a demonstrated content-substitution via backdated duplicate
id reaching a *committed* ledger with `validate` green.

## Adoption gate

None — shipped armed. A B1-class violation firing in a real ledger IS
the original signed-records growth-gate trigger ("build it when the
first forged timestamp is found in the wild"), now mechanically
observable instead of hoped-to-be-noticed.
