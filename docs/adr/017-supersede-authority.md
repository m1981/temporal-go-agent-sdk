# ADR-017: Supersede authority — a retracted premise needs the human gate (C3)

Status: Accepted (2026-07-18, operator) — source: independent review
finding C3 (Critical), confirmed live against the shipped CLI. Amends
ADR-013's intake rule. Implemented in CLI v0.9.3. Canary FAULT R11;
core test.
Date: 2026-07-18
Supersedes: — (narrows ADR-013's dead-state supersede eligibility for the
`retracted` state only; leaves ADR-001's matrix and ADR-013's fold
untouched)

## Context

Two surfaces disagreed on the system's headline property. Paper §1: "a
human decision to kill a claim cannot be undone by any later event."
ADR-013 intake: a premise may be superseded out of an issue when it is
in a dead state, and it lists `retracted` among them. Both were true as
written, and together they left a hole.

Retraction terminality was defended only at the **status** layer (the
retracted claim stays `retracted` in the fold, forever — real, and
unchanged here). Its **operational** purpose lives at the readiness
layer: ADR-001 makes a `retracted` premise block its issue
unconditionally (HELD). ADR-013 let that premise be redirected to a
fresh live claim, releasing the work — and `truth premise --supersedes`
carried **no human gate**. So the promise was spent at the layer it
existed to protect, by anyone.

**Confirmed attack (reproduced against the real CLI):** a human retracts
a P0 claim ("the database is safe to drop") under the full ADR-011 gate;
its issue goes HELD. An agent session — no `TRUTH_HUMAN`, a normal CLI
verb, no forgery — files a corrected claim and runs `truth premise <wk>
<new> --supersedes <retracted>`. It is accepted; the issue is released.
The retraction still reads terminal, but the P0 block it imposed is
gone. This is strictly worse than the accepted §8 item 6 forgery
residual: it needs no forged append, only a verb the CLI hands every
actor.

## Decision

**Superseding a `retracted` premise requires the ADR-011 human gate** —
`TRUTH_HUMAN=1` plus an interactive typed-id confirmation, or
`TRUTH_HUMAN_ACK=<retracted-id>` for headless human use — reusing
`human_ack_error` unchanged. The other dead states qualify **exactly as
before, ungated**: `stale`, `diverged`, `cannot_verify`, and `missing`
are *mechanical* deaths (evidence rotted, a recipe changed, a record is
absent) that no human decided, so a low-friction redirect to the
corrected claim stays the intended flow. Only `retracted` is a human
terminal veto, and releasing the work it blocks is the same class of act
as imposing it — the authority-symmetry principle ADR-002/ADR-011
already apply to issue cancellation ("killing an intention is the same
class of act as killing a fact").

The gate lives in intake (`cmd_premise`), not the fold: the fold stays
permissive and confluent (a recorded redirect always applies, ADR-013),
and intake stays strict, identical to how ADR-013 already splits the two.

## Consequences

- The paper's promise is now true at **both** layers. Precise statement:
  a retracted claim's *status* is terminal under any event, and the
  *work-block* it imposes can be released only by the same human
  authority that imposed it — never mechanically, never by an agent.
  §1 is updated to say this.
- The legitimate corrected-fact flow is preserved, not removed: the
  human who retracted may still redirect the premise to the correction
  — as a human. This was the C3 finding's undecided question; resolved
  in favor of "the veto is releasable only by its own authority," which
  keeps the headline property literal rather than softening it.
- Identity remains self-attested (F4/§8 item 5 class): the gate is the
  same env-var-plus-ack ADR-011 uses, not an identity check. It closes
  the *no-authority* path, not the determined-human-impersonation one —
  the same boundary every human gate in this system draws.

## Non-goals

Not gating the mechanical dead states (would punish the exact
low-friction redirect ADR-013 was built for). Not making `retracted`
premises un-redirectable entirely (that would remove the human's own
legitimate correction path and over-read "terminal" as "the work is
dead too," which it is not — only the claim is).
