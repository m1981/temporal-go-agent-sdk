# ADR-007: Quantifier–scope intake gate

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md` (external review, Claude),
implemented in CLI v0.6.0 the same day. Canary faults Q1–Q4.
Amended by: note (2026-07-12, F3) — an independent Fable review found
the shipped scope-signal narrower than this ADR's proposal: it missed
ripgrep's `-t` type filter and glob-metacharacter positionals, and the
quantifier lexicon lacked everywhere/always/each. v0.6.2 adds these
(canary Q5, Q6). Residual, documented in code: a bare tracked-subdir
positional with no slash or glob still evades, because resolving it
needs a git oracle the pure core deliberately cannot reach.
Date: 2026-07-11
Supersedes: — (mechanizes the paper's §9 operating convention 1)

## Context

Both genuine divergences in the pilot shared one shape: a *correct*,
*scoped* evidence command backing a *universal* claim sentence — a
repo-wide clause ("the only occurrences in the repo are…") over a
package-scoped grep whose `--include` filter did invisible work (paper
§2). The paper names this the dominant real failure mode; its only
defense was an operating convention. §10 sketched the countermeasure;
this ADR is that countermeasure, specified to intake-gate precision.

## Decision

`truth claim` and `done --claim` gain one more intake refusal, placed
after the near-duplicate gate and before the INV-M path checks.

**Detection rule.** The gate fires iff the claim text contains a
universal-quantifier signal (token lexicon: only, no, none, never,
nowhere, anywhere, all, every, any, entire, whole, zero; phrase lexicon
with word boundaries: repo-wide, "the repo", "the codebase", "the
project") AND the evidence command contains a scoping signal (option
tokens `--include`/`--exclude`/`-g`/`--glob`/`--path`/`--type` etc., a
positional argument containing `/`, or a `cd ` prefix). Lexicons live as
constants beside `DUPLICATE_THRESHOLD` and change only together with the
Q-canary faults.

**The override carries a basis, not a boolean.** `--scope-ok
"<sentence>"` is required to file through the gate; the sentence is
stored in the payload as `scope_basis` (schema: minLength 1). This is
the G8 refuse-with-override pattern upgraded with verdict-style basis
discipline: the author's scope judgment becomes auditable ledger content
— and the verifier prompt now explicitly instructs attacking it.

**False-positive posture.** A correctly scoped universal ("no calls to
X in `services/`" over a `services/`-scoped grep) fires the gate and
costs one honest sentence. Accepted friction, inside the one-command
budget; the adoption gate below bounds it.

## Explicit non-goals

No NLP beyond token/phrase matching — an LLM judging claim scope would
put a judgment in a mechanical trigger path (rejected for the same
reason ADR-005 rejected agent calls in hooks). No attempt to verify the
scope actually covers the quantifier — that remains the verifier's job;
the gate only forces the mismatch to be *stated* rather than invisible.

## Consequences

Easier: the single empirically dominant failure shape cannot enter the
ledger silently; every entry is either narrowed or carries an attackable
`scope_basis`. Harder: one more lexicon to maintain; one more refusal to
learn.

Falsifier: a third genuine divergence of the quantifier/domain-mismatch
shape filed *through* this gate — un-fired (lexicon gap) or overridden
with a `scope_basis` that did not cover the quantifier (the gate working
as designed; the verifier seam caught it, which is the system working).

## Adoption gate

Review after ~30 days of pilot use (due ~2026-08-11, instrument:
`truth stats`): override rate above ~50% of firings → narrow the
quantifier lexicon before abandoning; a Q4-shaped miss producing a
genuine divergence → widen the scope signals.
