# ADR-028: the issue-event state machine is reproduced in the spec, and an event may not sort before its issue record (M3)

Status: Accepted (2026-07-19, operator) — spec-precision (the state machine
was in code but not the spec) plus a real coherence fix, from batch-M review
finding M3. The finding was filed as "undefined"; the machine is in fact fully
defined AND tested, so most of M3 is document-only — but adversarial review
CLI-reproduced a genuine hole (below), so this ADR also carries a behavior
change. Implemented in the next release (CLI v0.9.9). Core tests
test_issue_event_before_its_issue_is_an_error, test_future_dated_issue_refused_at_intake;
canary FAULT IF.
Date: 2026-07-19
Supersedes: — (documents the machine ADR-002 stated only narratively; closes an
intake↔fold composition hole)
Amends: ADR-002 (reproduces the issue-event state machine it described in prose).

## Context

Finding M3 observed that the issue-status fold is called "analogous" to the
claim fold and "described in §5," but §5 covers satellites, not the issue
machine; ADR-002 gives the transitions only narratively; and whether an illegal
transition is refused, ignored, or folds to an undefined state is not stated.

Re-verification against HEAD found the machine is in fact **fully defined and
tested** in code — which makes most of M3 a documentation gap, not a hole:

- **Intake is strict**: `issue_event_error` is a complete transition table —
  `claimed←open`, `released←claimed`, `closed←open|claimed`, `reopened←closed`,
  `cancelled←open|claimed|closed`, and any event from `cancelled` refused. Both
  CLI writers (`cmd_start`, `cmd_done`) call it before appending; no other code
  writes an `issue_event`. `test_transition_matrix` locks all 20 pairs.
- **The fold is permissive except for the terminal rule**: `fold_issues`
  applies any recorded event's status mapping, EXCEPT it ignores every event on
  an already-`cancelled` issue — so `cancelled` is the fold-terminal state, and
  the issue-side terminal rule **is** "later events ignored," matching the claim
  side (M3's open derivation, answered). Permissiveness is deliberate, for
  confluence across union-merged branches, with intake as the strict gate.
- Two clarifications the docs owe: `closed←open` is a legal skip-claim close
  (ADR-002's graph didn't show it); and issue first-wins is enforced **jointly
  with `order_check`**, not by the fold alone (a backdated duplicate `wk-` id
  wins the fold but `order_check` makes it a commit-gate error) — the
  `fold_issues` docstring overstated first-wins standing alone.

**But adversarial review CLI-reproduced a real hole.** A schema-valid
**future-dated** issue record (e.g. `ts` in 2027, raw-appended — no CLI path
creates one) passes `validate` (it is `max_ts`, so no later line to warn on)
and folds as `open`. Then `truth done`/`--cancel` validate the transition
against the **folded** status (legal) and print `-> closed` / `-> cancelled`
at exit 0 — but `append_record` keeps the honest clock (skew > 300s is not
absorbed), so the event sorts **before** the issue record, and `fold_issues`
drops it (`ref in issues` is false at the event's fold position). The issue
stays **open, un-closable, un-cancellable**, and every attempt lies. Intake
validates the transition but never checks that the event it appends will
actually land after its referent in fold order.

## Decision

**1. The spec reproduces the state machine.** ADR-002's status section, paper
§1's fold description, and `.truth/README` now carry: the intake transition
table; the fold rule (permissive, except `cancelled` is terminal = later
events ignored); the intake-strict / fold-permissive division of labor and why
(merge confluence, mirroring the claim fold); the legal `closed←open` skip;
and that issue first-wins holds jointly with `order_check`.

**2. An issue_event must sort after the issue record it references.** Enforced
at both layers, mirroring the claim-side pattern:
- **Intake** (`issue_event_ts_error`, called in `cmd_start`/`cmd_done`):
  refuses acting on an issue whose record is dated beyond skew in the future —
  any event filed now would sort before it and be dropped. Clock-based, so it
  lives at intake, not the clock-free fold. Nothing is filed; no lie.
- **Commit gate** (`order_check`): an `issue_event` whose `fold_key` sorts
  before its referent issue record's is a hard error — catching a
  forward-reference record that bypassed intake. Clock-free (pure `fold_key`),
  so it composes with the confluent fold.

## Consequences

- `done`/`cancel` on a future-dated issue is refused honestly instead of
  reporting a transition the fold silently voids; a raw forward-reference event
  cannot be committed.
- The issue state machine now lives in the spec, not only the code.
- No effect on normal use: an issue is always created before events on it, so
  events always sort after their issue (verified: 1201-record real ledger and
  every canary lifecycle pass unchanged).

## Non-goals

Not rejecting a future-dated record in `validate` — that needs a wall-clock and
`validate` is clock-free by design (ADR-019). A lone future-dated issue record
(no events) therefore still commits, but is inert-and-visibly-so: every event on
it is refused at intake and at the gate. Disclosed residual. Not changing the
permissive fold (deliberate for confluence; intake is the strict gate).
