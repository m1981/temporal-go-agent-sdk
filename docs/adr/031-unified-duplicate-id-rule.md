# ADR-031: One duplicate-id rule — any content-distinct duplicate is refused

Status: Accepted (2026-07-20, operator) — roadmap-v3 R6 (batch 3,
self-consistency), adopting a simplification from the TLR-013 external
review line (see docs/roadmap-v3.md R6). Implemented in CLI v0.9.13.
Core tests TestOrderCheck (later-ts refusal, byte-identical pass,
fold-unchanged); canary FAULTS B1/B3/B4/B5 now expect the unified
message, new FAULT K2 pins the flipped later-ts expectation.
Date: 2026-07-20
Supersedes: the DETECTION halves of ADR-008 (rule (a), the
strictly-earlier backdated-duplicate refusal) and ADR-016 (decision
(b), the equal-ts substitution gate). Explicitly UNTOUCHED: the fold's
`(ts, id, canon)` total order (ADR-016 decision (a)), first-wins dedup,
the ADR-015 clock-push, and ADR-008's clock-regression warning (b) —
this ADR changes only which duplicate-id shapes `order_check` refuses.

## Context

`order_check` (run by `validate`, hence the commit gate) held two
duplicate-id detections accreted across two attacks: refuse a duplicate
id whose raw `ts` string sorts strictly before the first-seen line's
(the backdated substitution, ADR-008/F2), and refuse a duplicate id
with an equal `ts` but different `canon()` (the copied-timestamp
substitution, ADR-016/C1). Two shapes deliberately passed: the
byte-identical line (git's union-merge duplicate — the one legitimate
producer of a duplicate id) and the *later-ts content-distinct*
duplicate, accepted because it is harmless to the first-wins fold: it
sorts after the genuine record and loses.

"Harmless to the fold" is not "serves anything." Corrections in this
regime file under **fresh ids** by design — a re-file (`--duplicate-ok`
matches on text, not id), a verdict, a supersede, an invalidation all
mint new `tr-`/`wk-` ids. No workflow, tool path, or merge shape ever
produces a content-distinct record under an existing id. What the
accepted shape did provide: a confusion surface — a second, different
"body" for an id that greps, log readers, and any consumer folding a
*partial* stream (where the genuine record may be absent and the
duplicate is no longer "later") could pick up, and a free slot for an
attacker to park content under a trusted id with `validate` green. Two
ts-relation-dependent rules also cost more to state, test, and review
than the property they jointly approximate.

## Decision

One rule. Any record whose envelope id duplicates an earlier line's id
and whose `canon()` (the canonical `json.dumps(sort_keys=True)`
serialization) differs from the first-seen line's is refused —
regardless of the ts relation: earlier, equal, or later. The unified
message names this ADR and states the only legal shape:

    line N: duplicate id <id> with content differing from line M's --
    duplicate-id substitution (ADR-031): corrections file under fresh
    ids, so only a byte-identical union-merge duplicate may share an id

Byte-identical duplicates (union-merge shape) still pass. The
comparison never parses a timestamp, so no forged-ts encoding (tz-naive,
junk, copied, future) can route around it — the F2 lesson, kept by
construction rather than by case analysis.

## Consequences

- Easier: `order_check`'s duplicate logic is one content-equality test;
  the ADR-008/ADR-016 case split survives only as history. The gate is
  strictly tighter: everything refused before is refused now (the old
  cases are subsets), plus the later-ts distinct duplicate.
- Behavior flip (the only one): a later-ts content-distinct duplicate,
  previously `validate`-green, now fails validate and therefore the
  commit gate (canary FAULT K2). The fold result for such a ledger is
  IDENTICAL before and after — first-wins keeps the genuine record —
  so no derived status changes; only admissibility does.
- Unchanged, explicitly: the fold's `(ts, id, canon)` total order and
  its confluence (ADR-016 (a), canary B6); the ADR-015 clock-push in
  `append_record`; the clock-regression warning (ADR-008 (b), 300 s
  tolerance — union merges legitimately interleave old records and must
  keep passing).
- The paper's §1 "Fold semantics, precisely" and Appendix A INV-G/INV-N
  rows still describe the two-case detection; re-stating them for the
  unified rule is a Batch 4 (R7) paper task, noted on the roadmap.

## Non-goals

ADR-008's stand: not tamper-proofing a rewritten history, not identity
(`actor` stays self-attested). Fresh-id ts forgery on a *non-duplicate*
id remains the accepted §8 item 6 residual; signed/hash-linked records
(the TLR growth-gate successor, §10) remain the only closure for a
history the local gate never saw.

Falsifier: a demonstrated content substitution under a duplicated id
reaching a *committed* ledger with `validate` green — same falsifier as
ADR-008/ADR-016, now covering every ts relation.
