# ADR-020: Verdict precedence is one total function; cannot_verify/diverged/stale are recoverable, retracted is not (H3)

Status: Accepted (2026-07-18, operator) — source: independent review
finding H3 (High), a spec-precision defect; its escalation to "a
verdict-path analogue of C1" was investigated (live sandbox +
independent adversarial review, 600-trial confluence fuzz) and REJECTED.
Ratifies the shipped v0.4/v0.9.1 fold as normative; no behavior change.
Core tests test_verdict_precedence_is_confluent,
test_negative_verdicts_are_recoverable, test_retracted_absorbs_any_order;
canary FAULT RV (recoverability arm).
Date: 2026-07-18
Supersedes: — (pins the fold-status precedence stated only by example in
paper §6.3 / F3 / the fold table)

## Context

H3 observed that the paper describes claim status by three seemingly
separate rules and never states their composition as a single total
function: `retracted` is "terminal — later events ignored" (an absorbing
rule), agree/diverge are "last-writer-wins in (ts, id) order" (§6.3), and
the `stale → agree` recovery runs through the effective-anchor mechanism
(F2). It also noted the spec never says whether `cannot_verify` and
`diverged` are recoverable, and worked one example (cannot_verify@ts=5
then a backdated agree@ts=3) whose result the prose does not fix.

H3 further escalated this to a security claim: because two verdicts on
one claim have DISTINCT `tr-` ids, the ADR-008/ADR-016 duplicate-id gates
never fire, so an appender controlling `ts` (§8 item 6) could backdate a
verdict to flip terminal status with `validate` green — "the verdict-path
analogue of C1."

## Decision — the total function

Status is a single total function of the log, computed by folding all
events in the ADR-016 total order `(ts, id, canon)`:

1. A claim is born `unverified`.
2. Each `verdict` or `invalidation` for the claim, in fold order, sets
   the status: `agree → live`, `diverge → diverged`,
   `cannot_verify → cannot_verify`, `retracted → retracted`,
   `invalidation → stale` — **last-writer-wins by `(ts, id, canon)`**,
   EXCEPT that once the folded status is `retracted` every later setter
   is ignored (`retracted` is **absorbing**, checked on the folded status
   in `set_status`, not on `ts`).
3. The DISPUTED post-pass then flips any two claims joined by a live
   `contradicts` edge to `disputed`, judged against the statuses from
   step 2 (never against statuses this pass writes), so it too is
   order-independent.

Consequently: **`cannot_verify`, `diverged`, and `stale` are recoverable**
— a later (higher-key) `agree` returns the claim to `live` (a `stale`
claim re-anchors via the effective anchor). **`retracted` is the sole
terminal verdict**; intake also refuses any verdict on a retracted claim,
so it is terminal at both the intake and fold layers. The worked example
resolves by rule 2: cannot_verify@5 then agree@3 folds to
`cannot_verify` (5 is the higher key). This is one function, not three
rules; the "effective anchor" is a re-staling detail, not a fourth status
rule.

## The security claim is rejected (not a C1 analogue)

C1 was real because the fold's order was NOT total: a duplicate id with a
copied equal `ts` let *file position* decide the winner, so two
union-merge directions produced different content — a confluence break
needing no forgery. The verdict path has no such seam:

- **Confluence holds.** Two verdicts carry distinct ids, and the fold
  sorts by the total order `(ts, id, canon)`; physical file position is
  never load-bearing. Reordering ledger lines never changes a folded
  status (independent adversarial review: 600-trial randomized fuzz over
  up to 720 permutations each, zero violations; live sandbox: swapping
  the two verdict lines left the status unchanged).
- **Backdating gives no advantage.** LWW means the *highest-key* setter
  wins, so backdating can only LOWER an attacker record's key — strictly
  dominated by filing at `ts = now`. Resurrecting a `diverged`/`cannot_verify`
  claim to `live` requires being the latest event, i.e. the honest path,
  which is governed by the ADR-010 self-verification gate on manual
  agree — not unlocked by backdating.
- **The residual is the accepted §8 item 6 forgery**, and it is not even
  silent: a backdated append trips the ADR-008 clock-regression warning
  at `validate` time (green-with-warning, never a hard error). The
  distinct-id premise is factually correct — the duplicate-id gates do
  not fire on two verdicts — but that gate is unnecessary, because
  confluence + LWW + the absorbing `retracted` already neutralize the
  threat.

The real, pre-existing, accepted property here is that any *cross-session*
verifier can `agree`-to-`live` with a basis (the designed ADR-010 trust
seam), which is orthogonal to verdict ordering. No runtime verdict-ordering
gate is added: it would be theater against a non-threat.

## Consequences

- Paper §6.3, the F3 row, and the fold table now state the single total
  function and the recoverable-vs-terminal split; README's fold section
  matches.
- Locked mechanically: `test_verdict_precedence_is_confluent` (every
  permutation of a mixed verdict set folds to one status),
  `test_negative_verdicts_are_recoverable` (agree after
  diverge/cannot_verify/stale → live), `test_retracted_absorbs_any_order`
  (retracted wins before or after any other verdict, including a
  later-ts agree), and canary FAULT RV (a diverged claim recovers to live
  at the CLI).
- No behavior change, no version bump on its own account.

## Non-goals

No verdict-ordering runtime gate (rejected above). Not making
`cannot_verify`/`diverged` terminal (they are correctable states, and
forcing a re-file would lose the claim's identity and history). Not
changing the ADR-010 trust seam for manual agree.
