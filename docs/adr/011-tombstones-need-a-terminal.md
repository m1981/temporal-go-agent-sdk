# ADR-011: Tombstones require a terminal — hardening TRUTH_HUMAN against compliant agents

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md`, implemented in CLI v0.6.0.
Canary faults H1–H3 (+ updated FAULT M and R6).
Date: 2026-07-11
Supersedes: amends F4's fix (v0.4)

## Context

F4 converted "retraction is humans-only" into the self-attested
`TRUTH_HUMAN=1` convention. In an LLM-agent regime that convention has a
weakness the paper's §8 item 5 undersells: **the refusal message named
the bypass.** "A human confirms by running with TRUTH_HUMAN=1" is, to a
compliant-but-confused agent, an instruction — one tool call from
compliance theater. The realistic solo-regime threat is not a forger; it
is an agent that sets the variable because the error told it how, then
reports the retraction as completed work.

## Decision

Tombstone operations (`verdict … retracted`, `done --cancel`) require,
in addition to `TRUTH_HUMAN=1`, one of:

- **a TTY plus an interactive confirmation** — the operator types the
  target id back; agent-harness shells have no TTY, so the structural
  fact does the enforcing; or
- **`TRUTH_HUMAN_ACK=<exact-id>`** for genuinely headless human use
  (CI cleanup, scripts, the canary) — it must name the *specific*
  record being killed, so a lingering exported variable cannot
  authorize arbitrary future tombstones.

**Refusal messages stop teaching the ritual.** Agent-facing refusals
now say: file `diverge` (or close) with a basis saying it should die,
and stop — the human queue decides; humans are told to re-run in their
own terminal. The acknowledgment mechanism is documented in `--help`
and `.truth/README.md` — surfaces humans read — not in the error paths
agents hit.

## Explicit non-goals

Still not identity — a human at a TTY is asserted by the TTY, and a
determined process can allocate a pty. The claim is narrower and honest:
the *one-export bypass an error message can teach* is closed; the cost
of agent tombstoning rises from one env var to deliberate pty allocation
plus an id-specific acknowledgment, which no plausible drift produces by
accident.

## Consequences

Easier: the strongest promise in the system (terminality, G12) stops
resting on agents declining an invitation the CLI itself used to extend.
Harder: a human can no longer tombstone *through* an agent session's
shell tool — they drop to their own terminal, which is exactly the
ceremony a kill decision deserves. TTY-positive interactive paths are
untestable in the sandboxed canary and are covered by H1–H3's negative
space plus documentation — stated, not hidden.
