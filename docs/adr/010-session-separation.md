# ADR-010: Session separation on agree verdicts

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md`, implemented in CLI v0.6.0.
Canary faults V1–V3.
Amended by: field note (2026-07-13, second deployment,
`docs/field-notes-sdk-session.md` item 1) — the gate keys on the
*record's* `session`, so a single-writer/scribe coordination pattern
misfires in both directions: a courier who authored the claim gets a
genuinely independent `agree` refused, and a true self-verdict launders
cleanly through any other session's hands. Operating rule: verifiers
file their own verdicts (a read-only/plan-mode peer cannot be the
verifier of record); where a scribe is unavoidable, it must file under
the verifier's identity via `TRUTH_SESSION=<verifier-session>`, which
the CLI already honors — no new `--verifier-session` flag, since it
would duplicate the existing env override without adding trust
(identity stays self-attested either way, this ADR's own F4 class).
Date: 2026-07-11
Supersedes: — (extends F4's norm→syntax conversion to the verdict seam)

## Context

G11 scripts what a verifier *receives*; nothing scripted who may *file*.
The independence property the paper's §2 result rests on — verifiers
receiving dispatch-only context caught the author both times — was
enforced by operator procedure, not the CLI: the authoring session could
run `truth verdict <own-claim> agree` and mint its own `live` status in
one command. The realistic failure is a compliant agent completing the
verification ritual on its own work because the instruction file says
claims should be verified. F4 established the house pattern for exactly
this shape: convert the norm into a convention with a syntax, accepting
that identity is self-attested.

## Decision

`truth verdict <id> agree` refuses when the filing session equals the
claim record's envelope `session`. Escape: `TRUTH_SELF_VERDICT=1`
(self-attested, exactly F4's trust class, documented as such).

**Asymmetric by design:** `diverge` and `cannot_verify` from the
authoring session remain allowed — self-incrimination runs against
interest, matching the existing rule that corrections of dead claims
bypass the duplicate gate. The `--recheck` path needs no exemption
logic: its auto-filed outcomes are only the negative ones.

## Explicit non-goals

Not identity. `session` is env/ppid-derived and forgeable in one export.
The defense is against drift, not adversaries: an agent must now
*visibly perform* a bypass ritual (a settable env var, attributable in
context) rather than drift into self-verification through the front
door.

## Consequences

Easier: `live` regains its intended meaning — *independently* confirmed
— by construction rather than by hope; the canary itself now files its
agree verdicts from a distinct verifier session, which is the honest
protocol. Harder: a legitimate same-session re-check after a trivial fix
needs a fresh session or the env var — accepted; that friction is the
point.

Falsifier: a claim whose only `agree` verdict shares its session id,
present in a committed ledger, with no deliberate override story.
