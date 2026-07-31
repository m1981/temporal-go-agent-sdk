# ADR-029: the evidence screen is a gate on execution, not a peer refusal (M4)

Status: Accepted (2026-07-19, operator) — spec-precision from batch-M review
finding M4, re-verified against v0.9.8 by code trace and an adversarial
reviewer (which confirmed the code is unambiguous and correct — document-only).
No behavior change. Implemented in the next release (CLI v0.9.9). Canary FAULT
SD locks the precedence.
Date: 2026-07-19
Supersedes: —
Amends: ADR-009 (states that the screen gates whether a command runs at all, so
it is not a flat peer of the determinism double-run in the refusal list).

## Context

Finding M4 noted a tension: the paper lists the intake refusals in a flat order
— dead-tripwire paths, VERIFIED checks, "commands failing the read-only safety
screen," then "commands whose two intake runs hash differently" — which reads
as a sequence of independent peer refusals. But ADR-009 says the screen runs
"before the determinism double-run touches anything," and it is not stated
whether a command that fails the screen is **also** double-run. Observable
question: does an unscreened *nondeterministic* command report the screen
refusal or the determinism refusal first?

Code trace and empirical runs (VERIFIED intake, `cmd_claim`) settle it
unambiguously — the code is correct; only the spec's presentation is imprecise:

- The screen (`screen_evidence_command`) runs **before** the first
  `run_evidence`. A screen failure `sys.exit`s **before** any execution, so a
  screen-failed command is **not** run — hence never double-run, never
  determinism-checked. There is no earlier execution anywhere in the intake
  path (the duplicate/quantifier/paths checks are pure; `head_commit` runs only
  git).
- The one exception is the author's explicit escape hatch: with
  `--evidence-unsafe-ok` **and** an allowlist present, the screen refusal is
  suppressed, the command **is** run twice, determinism applies, and the record
  is stored `screened: false`. (A missing allowlist fails closed even under the
  override — `allow is None` always implies a screen failure.)

So the screen is not a peer in a flat list: it is a **gate on execution**. The
double-run only ever judges a command the screen (or an explicit override) let
run.

The adversary also confirmed one caveat worth stating: `--evidence-unsafe-ok`
bypasses the **whole** screen, including the ADR-022 deny baseline. A
deny-listed program (e.g. `sh`) therefore executes at intake under the override
(twice, for the determinism double-run, unless `--single-run`), though the deny
message says it is "never valid evidence, even if
allowlisted." This is not a hole: the command runs in the **author's own
session** (they typed it — no new capability), is stored `screened: false`, and
`verdict --recheck` refuses to execute a `screened: false` command — so the
deny baseline's actual security purpose (stop a *verifier* from executing an
accidentally-allowlisted shell across the trust boundary) is fully served. The
deny message is shown only when the refusal is **not** overridden.

## Decision

**1. The spec presents the screen as an execution gate.** Paper §1's intake
description and this ADR state: the safety screen decides **whether** an
evidence command runs at all; the determinism double-run judges only a command
that ran. A screen-failed command is refused **without running** (so it reports
the screen refusal, never determinism) unless `--evidence-unsafe-ok` promotes
it to run-twice-and-be-determinism-checked, stored `screened: false`.

**2. The override's scope is stated.** `--evidence-unsafe-ok` bypasses the
entire screen (allowlist and the ADR-022 deny baseline), runs the command at
intake in the author's own session (twice, for the determinism double-run,
unless `--single-run`), and records `screened: false`; the
deferred-execution protection is `recheck`'s refusal of a `screened: false`
command, not the intake screen. ADR-009 and `.truth/README` say so; the deny
baseline is not weakened (its purpose is the recheck/verifier boundary).

## Consequences

- The refusal list is no longer read as flat peers: a screen-failed command
  never reaches the determinism check without the explicit override.
- The `screened: false` semantics are pinned end-to-end: unsafe at intake (runs
  in the author's session), refused at recheck.
- Canary FAULT SD locks it: the same nondeterministic non-allowlisted command
  reports the SCREEN refusal without the override, and the G6 determinism
  refusal with it — the contrast is the ordering proof.

## Non-goals

Not making the deny baseline outrank `--evidence-unsafe-ok`: the override runs
in the author's own session (no capability the author lacks), stores
`screened: false`, and the recheck refusal is the real boundary — a special
case here would add code with no security gain. Not changing the intake
execution model. The screen remains a sound over-approximation of the executor
(ADR-021), not a proof of safety.
