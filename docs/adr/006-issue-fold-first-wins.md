# ADR-006: Issue-fold duplicate ids are first-wins, not last-wins

Status: Accepted (2026-07-09, Michal)
Date: 2026-07-09
Supersedes: — (narrows ADR-002's "update-by-refile" rationale for
`fold_issues`; does not change ADR-002's status semantics, its refusal
list, or its verbs)

## Context

`fold()` derives claim status FIRST-WINS on a duplicate id (v0.4, finding
F6): appending a second `claim` record bearing an existing id cannot
alter status or content, closing a "tombstone resurrection by pure
append" attack demonstrated against a retracted P0 claim. ADR-002's
`fold_issues` deliberately chose the opposite rule for issues — LAST-WINS
— on the stated rationale that "an issue's payload is mutable intent, not
a first-wins assertion," describing an update-by-refile verb: a caller
re-filing an existing `wk-` id to correct its title, deps, or premises.

Auditing that rationale against the shipped CLI (2026-07-09) found it
false. `truth issue` (the only command that appends an `issue` record)
mints its id via `make_id`, a hash of `(payload, ts, actor)`; every
invocation runs at a fresh microsecond timestamp, so no CLI call can ever
intentionally produce a duplicate `wk-` id. No verb reads an existing
issue's payload and re-files it. `test_last_issue_payload_wins`, the only
test exercising this path, constructed both records directly in the test
harness — bypassing the CLI, because there was no other way to reach the
code. Last-wins protected a feature nothing implements.

What it left reachable is a raw append: an actor with only file-write
capability (every agent session, by the paper's own threat model) can
write a second `issue` line bearing an existing `wk-` id, any later
timestamp, and `"premises": []`. Demonstrated in a sandbox: an issue
correctly HELD by `truth ready` on a stale premise flips to READY, with
no warning, immediately after such an append. `truth validate` still
passes (schema checks record shape, not fold-level id uniqueness); the
INV-A line-prefix commit gate does not fire (this is an append, not an
edit — the same structural blind spot F6 exploited). No canary fault or
unit test covered it; the existing canary fault for this class, FAULT K,
covers only claims.

Unlike the accepted, deferred claims-side gap (paper §8 item 6, "Fold
semantics, precisely"), this needed no backdated timestamp — last-wins
means an ordinary "now" timestamp already wins — and no terminal-state
coincidence (F6 required resurrecting specifically a *retracted* id; this
works on any *open* issue at any time). It is a strictly easier attack
against a stronger property: ADR-001's premise-validity gate is the
mechanism `truth ready` exists to enforce.

Options considered: (a) leave last-wins, document the gap as accepted
alongside §8 item 6 — rejected, because §8 item 6's mitigating argument
(forged timestamps are attributable in git, and the hard part is
backdating) does not hold here; there is no hard part. (b) Make only the
`premises` field grow-only (a G-Set merge) while leaving title/text/deps
last-wins — rejected as unnecessary complexity: since no verb legitimately
re-files an existing id at all, there is nothing for last-wins to protect
on *any* field, so a field-by-field CRDT is solving a problem that does
not exist. (c) First-wins on the whole issue record, identical to claims
— chosen.

## Decision

`fold_issues` treats a duplicate `issue` record id exactly as `fold`
treats a duplicate `claim` record id: the first record (in canonical
`(ts, id)` order) fixes the issue's title, text, deps, and premises for
good; any later record bearing the same id is ignored for content. Status
continues to move only through `issue_event` records, unchanged.

This removes the "update-by-refile" capability ADR-002 described, but
that capability was never implemented, so nothing that exists today loses
function. If a genuine need for editing an issue's payload after creation
emerges, it requires its own verb and its own ADR — consistent with
ADR-002's refusal list, which already requires a superseding ADR for any
kernel growth.

## Consequences

Easier: the issue-fold and claim-fold now share one mental model and one
proof obligation — "duplicate ids are inert" — instead of two, which is
one less asymmetry for a future session to reason about incorrectly.
ADR-001's premise-validity guarantee now holds against the same threat
model INV-A already defends the rest of the ledger against.

Harder: none identified. No shipped verb depended on last-wins; the one
unit test asserting it (`test_last_issue_payload_wins`) tested a scenario
no real caller could produce, and is inverted to `test_first_issue_payload_wins`
rather than removed, so the property (whichever way it's decided) stays
under regression coverage.

This finding and fix followed the paper's own audit method (instrument 7:
independent reproduction — demonstrated in a fresh sandbox against the
real CLI, not reasoned about abstractly) and were reviewed independently
before being accepted, per project practice for judgment calls of this
kind.
