# ADR-027: the anchor_commit/commit floor is consistent across kinds, and the schema is a necessary-not-sufficient gate (M2)

Status: Accepted (2026-07-19, operator) — spec-precision from batch-2 review
finding M2, re-verified against v0.9.8 in a sandbox and by an adversarial
reviewer (which sharpened the anchor fix and corrected one factual claim)
before adoption. Behavior change: `validate` and the schema now refuse a
claim/verdict/invalidation whose anchor is a string shorter than 7 chars, and
a VERIFIED claim whose anchor is null. Zero effect on real data. Implemented in
the next release (CLI v0.9.9). Corpus fixtures (sub-7 / null anchor, all three kinds);
canary FAULT AN1–AN5.
Date: 2026-07-19
Supersedes: — (tightens a loose floor to match the value domain; documents a
division of labor the schema description previously overclaimed)
Amends: ADR-009 (states that the schema is deliberately silent on the evidence
screen's semantics, which ADR-009 enforces operationally).

## Context

Finding M2 raised two schema-vs-prose gaps, both confirmed on both contract
surfaces (the stdlib mirror and the JSON Schema):

1. **A loose anchor floor.** `claim.anchor_commit` was floored at `minLength 1`
   while `verdict.anchor_commit` and `invalidation.commit` were floored at 7 —
   the same value (a git SHA prefix, ≥7 everywhere the system emits one) with
   two different floors. A claim carrying `anchor_commit: "a"` passed both
   `truth validate` and jsonschema. Adversarial review found the fix as first
   scoped was **incomplete in two ways**: (a) a VERIFIED claim with
   `anchor_commit: null` was schema-*valid* (`required` is satisfied by null;
   `minLength` ignores null) but mirror-*invalid* (the INV-B truthiness check)
   — a standing FS-2 violation in the *opposite* direction (mirror stricter
   than schema), invisible to the FS-2 mutant generator because it emits no
   null; and (b) the mirror had **no** anchor length check anywhere, including
   on `verdict.anchor_commit`, where the schema already demanded 7 — a
   pre-existing mirror-weaker gap the mutant generator also missed (its junk
   literal `"__XXX__"` is exactly 7 chars).

2. **The schema does not structurally enforce the evidence screen.**
   `claim.evidence.screened` is a bare optional boolean with no `if/then`,
   though ADR-009 gives it semantics — yet the schema description called the
   CLI a "mirror of it," implying a parity that does not hold for `screened`.

## Decision

**1. One anchor floor, consistent across kinds, in schema+mirror lockstep.**
- Schema: `claim.anchor_commit`'s string branch is floored at 7 (the null
  branch stays, for unanchored non-VERIFIED claims); the VERIFIED `then`-branch
  additionally constrains `anchor_commit` to a non-null `string` ≥7, matching
  the mirror's INV-B truthiness rule and the CLI's G1 gate (which refuses
  `head=None`). `verdict.anchor_commit` and `invalidation.commit` were already
  7.
- Mirror: a **claim-wide** floor check (any claim, not just VERIFIED — a
  hand-appended UNVERIFIED claim with a short anchor is now refused too), plus
  `verdict.anchor_commit` and `invalidation.commit` floor checks that close the
  pre-existing mirror-weaker gaps. Probe-verified: schema and mirror agree on
  all 13 cases across the three kinds.
- Because the FS-2 mutant generator is blind here (no null, 7-char junk),
  explicit sub-7 / null corpus fixtures across the three kinds and canary
  FAULT AN1–AN5 carry the constraint. FAULT AN5 pins the floor at *exactly* 7
  (a 7-char anchor still validates — not over-tightened). Mutant-verified:
  neutering the three new mirror checks flips AN1/AN3/AN4 to MISSED.
- Zero effect on real data: the CLI only ever writes `head_commit()` (a full
  40-char SHA) into an anchor, and all three live ledgers (this repo and both
  deployments) carry zero sub-7 anchors.

**2. The schema is a necessary-not-sufficient gate, stated as such.** The
schema fixes *structure*; it is deliberately silent on the evidence screen's
*semantics*, which ADR-009 enforces **operationally**, not structurally:
- At filing, the command is screened; at recheck, the stored `screened` flag is
  trusted **only to refuse** (`screened=false` → refuse to execute) and
  **everything else is re-screened fresh** against the current allowlist and
  the ADR-022 denylist before execution. A lying `screened=true` on a command
  that was never actually screened therefore *cannot* cause unscreened
  execution — recheck re-screens it regardless. `done`/acceptance-oracle
  execution is gated the same way against `.truth/accept-allow`.
- The silence is a **backward-compatibility necessity**, not an oversight: 50
  live pre-ADR-009 evidence records across the three ledgers carry no
  `screened` key at all; an `if/then` requiring it would retroactively
  invalidate live ledgers. (The mirror *does* reject a non-bool `screened` —
  the silence is only about presence and truthfulness, never type.)
- `returncode` is likewise structurally optional. Unlike `screened` it is
  universally present in practice (all 162 evidence records carry it), so its
  silence is a defensible *choice* rather than a compat necessity. One
  disclosed residual follows from it: `recheck_verdict` defaults a missing
  stored `returncode` to the current run's code, so a hand-appended record for
  a returncode-sensitive, empty-output command could never returncode-diverge
  at recheck. It is not an execution/safety gap (no unscreened code runs);
  it is a verification-strength residual, tracked as a follow-up.

## Consequences

- A schema-valid record can no longer carry a nonsense sub-7 anchor, and the
  schema and mirror agree across all three anchor-bearing kinds — closing both
  the loose floor and the two FS-2 violations (VERIFIED-null; verdict/
  invalidation mirror-weaker) the adversary surfaced.
- The schema's role is documented: it is necessary, not sufficient; ADR-009's
  screen semantics live in the operational path (file + recheck), which does
  not trust the stored `screened` flag to *skip* screening. The description no
  longer overclaims full mirror parity.
- The `returncode` recheck residual is disclosed and tracked rather than hidden.

## Non-goals

Not adding structural `screened`/`returncode` enforcement to the schema (compat
necessity for `screened`; operational enforcement already covers the safety
property; a deliberate choice for `returncode`). Not changing recheck's
returncode default in this batch (tracked follow-up). The anchor floor is a
length floor, not a git-object-existence check — an anchor's reachability is
materialized operationally by `invalidate-scan` (FAULT E), not by `validate`.
