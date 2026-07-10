# ADR-001: Premise validity semantics for epistemic readiness

Status: Accepted
Date: 2026-07-04
Supersedes: —

## Context

`truth ready` intersects Beads' unblocked work with the validity of each
issue's `premised-on` claims. v0.1 passed only `live` premises, which in
practice blocks nearly all work: most claims are `unverified` for most of
their life, and requiring independent verification of every premise before
any work contradicts the one-command friction budget (edge E4). The gap
register (G15) demanded a decided matrix rather than code-by-default.
Options considered: (a) only live passes — epistemically strictest,
operationally unusable for a solo dev; (b) everything except
diverged/stale passes — too loose, `cannot_verify` on a critical premise
would never stop anything; (c) a tier-sensitive matrix.

## Decision

We will apply the following matrix in `truth ready`: `live` passes;
`unverified` passes with a warning annotation; `cannot_verify` blocks the
issue only when the premise claim is tier P0, and passes with a warning
otherwise; `stale`, `diverged`, `retracted`, and missing claim ids always
block.

## Consequences

Work flows without mandatory verification ceremony, and warnings keep the
unverified debt visible instead of hidden — but the trade-off is real:
an issue can proceed on an unverified premise that later proves false,
and the cost of that late discovery is the price paid for low friction.
P0 premises get the strict treatment because their cost-of-error tier says
late discovery is unaffordable there. Blocking on `retracted` and missing
ids makes premise hygiene an agent-visible failure rather than silent
drift. Revisit via a superseding ADR if warning fatigue appears — if
agents learn to ignore the unverified-premise warning, option (a) with a
cheap bulk-verification path becomes the fallback.
