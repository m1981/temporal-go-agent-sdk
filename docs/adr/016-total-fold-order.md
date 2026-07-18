# ADR-016: Total fold order — the equal-ts substitution gap (C1)

Status: Accepted (2026-07-18, operator) — source: independent spec
review, finding C1 (Critical), confirmed live against the shipped CLI
in a fresh sandbox (the audit method's instrument 7). Implemented in
CLI v0.9.1. Canary faults B5–B6; permutation core test
(`test_duplicate_id_equal_ts_folds_to_one_content`). Amends INV-I and
INV-G/INV-N; extends ADR-008.
Date: 2026-07-18
Supersedes: — (closes the residual ADR-008's strictly-earlier rule left
open)

## Context

Paper §1 states the fold replays events in "the canonical total order
`(timestamp, id)`" and that replay is "order-independent" — the
property union merge depends on (INV-I confluence). It is not total.
Two *distinct* records can share both keys: a duplicate `id` (the log
is append-only, not append-unique — ADR-006's own threat statement
grants every session raw-append capability) carrying a **copied**
(byte-equal) `ts`. On such a tie Python's `sorted` is stable, so the
winner is decided by **file position** — precisely what the fold is
promised to ignore.

ADR-008 closed the *backdated* duplicate (strictly-earlier `ts`) but
keyed its rule on strictly-less, explicitly letting an equal `ts` pass
for the git union-merge shape (a byte-identical line). That aside
conflated two different equal-ts cases: identical lines (legitimate)
and non-identical lines under one id (the forgery).

**Confirmed attack (run against the shipped CLI, not derived):**

1. Genuine claim `tr-de4e5f1a`, text *"the database is safe to drop"*,
   `ts = T`.
2. Forge a duplicate-id claim: same `id`, `ts` copied byte-for-byte
   (no backdating), payload text *"DROP DATABASE prod"*. On a branch
   forked before the genuine claim existed, this is a *fresh* id there
   — `validate` green.
3. Union-merge the two branches. The tied pair can land in either file
   order depending on merge direction (F3's original mechanism). Under
   the stable sort, first-wins content resolves to the genuine text in
   one order and the forged text in the other. `validate` passed both.

Observed: `fold(genuine, forged) → "the database is safe to drop"` but
`fold(forged, genuine) → "DROP DATABASE prod"` — two repositories, two
states, one schema-admissible event multiset, `validate` green
everywhere. INV-I falsified, and ADR-008's own named falsifier
("content-substitution via duplicate id reaching a committed ledger
with validate green") reached with **no backdated timestamp**.

## Decision

Two complementary fixes; each is insufficient alone (see Consequences).

**(a) Total, content-derived fold order.** `fold_key()` appends a third
sort key — `canon(ev)`, the record's canonical JSON serialization
(`json.dumps(sort_keys=True)`, the same bytes the CLI appends) — after
`(ts, id)`. Distinct records differ in some field, so they never tie;
every permutation, including both union-merge file orders, folds to one
state. Byte-identical records (the union-merge duplicate) tie on all
three keys and coincide, so which "wins" is immaterial. Applied at all
four fold/replay sort sites. This restores INV-I as a property of the
fold itself, independent of any gate.

**(b) Equal-ts substitution gate.** `order_check` (run by `validate`,
hence the commit gate) now refuses a duplicate `id` whose `ts` equals
the first-seen line's but whose `canon()` differs. The byte-identical
union-merge shape (canary B2) still passes; the copied-ts forgery
(canary B5) fails at commit — within one repository's post-merge
history, both lines are present and the check fires.

## Consequences

- **Neither fix alone suffices, and the demonstration proves it.** With
  only (a), the fold is confluent but the *attacker's* content can win
  deterministically on both sides: `canon()` of the forged record
  (`"actor": "agent-evil"`) happens to sort before the genuine
  (`"actor": "michal"`), so both orders fold to *"DROP DATABASE prod"* —
  confluent substitution, `validate` green. (a) fixes non-confluence
  but would harden a silent substitution. (b) is what refuses the pair
  at the gate. With only (b), the gate blocks committed ledgers, but
  §1's "order-independent fold" stays literally false for any consumer
  that folds an uncommitted or externally-supplied stream. Together:
  the gate blocks substitution at commit, and the fold is provably
  total everywhere.
- The tie-break is content, never file position or wall-clock — so it
  cannot reintroduce a `ts`-forgery sensitivity (the F2 lesson: order
  on what a string-diffing gate can also see).
- Unchanged: fresh-id `ts` forgery on a non-duplicate id stays the
  accepted §8 item 6 residual; signed/hash-linked records (§10) remain
  the only closure for a history the local gate never saw.

## Non-goals

Not identity: `actor` remains self-attested. Not tamper-proofing a
rewritten history (ADR-008's non-goal stands). This closes a
confluence/validation gap, not the authorship gap.
