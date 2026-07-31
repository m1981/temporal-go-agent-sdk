# ADR-035: the positive-claim exit gate

Status: Accepted (2026-07-31, operator) — R1 of the 2026-07 gates
adoption (provenance: docs/reviews/gates-2026-07/, proposal 07's
exit-gate record). Implemented in CLI v0.9.21, schema `$id` v0.12.
Core tests TestExitGate; canary FAULT X (8 arms incl. negative
control and the validate-mirror pair).
Date: 2026-07-31
Amends: — . Hardens: the v0.9.11 hollow-VERIFIED warning (paper §4)
from queue to gate for the decidable slice. Extends: ADR-034 (first
post-execution row of the gate table), ADR-007 (the override-carries-
a-basis discipline), ADR-033 (the override row is the single home of
the overridden count, CC-2). Cites: ADR-026 (`$id` bump — record
shape changed), ADR-032 (decay decision below, in its exclusions
form).
Supersedes: —

## Context

The VERIFIED double-run checks *stability*, not *success*: a
deterministically failing command files VERIFIED and rechecks green
forever (paper §4, "hollow VERIFIED"). v0.9.11 shipped a loud
non-blocking warning — queue, not gate — because a legitimately
failing probe exists: `grep` proving *absence* exits 1, and that
exit IS the demonstration. The field then produced the case the
warning under-serves: a pilot P1 claim whose `&&`-chained evidence
exited 1 at filing (a stash-pop conflict resolution had dropped the
documented section one chain leg greped for) filed VERIFIED anyway;
the warning was swallowed by a `tail -1` capture, an independent
verifier caught it, and the incident was banked as the pilot's
QB-011. The cheap layer passed a decidable defect to the expensive
layer.

Decidable — with machinery this ADR builds: the CLI had one
undivided `QUANTIFIER_TOKENS` set and no negation constant. The
adoption review simulated this gate over the 244 real VERIFIED
filings in the meta and pilot ledgers: 5 refusals — both motivating
defects plus three further exit-1 positive claims — and 6 warnings,
each a genuine absence proof; zero false refusals (`tr-166c4616`).

## Decision

**`NEGATION_TOKENS`** — a frozenset beside the lexicons: *not,
neither, nor, without, absent, lacks, lacking, missing, unused,
unreferenced* plus **copies** of the five negation-shaped quantifier
tokens (*no, none, never, nowhere, zero*). Copies, not a shared
reference: widening one lexicon must never silently widen the other
gate. Core test X6 pins the subset relation — a one-directional
tripwire (it catches removals here, not negation-shaped additions to
ADR-007's set; stated, not hidden). Changed only with the X faults.

**The gate** — the first `post-execution` row of the ADR-034 table,
on `truth claim --class VERIFIED` and `done --claim` alike (the
paper's two real hollow instances were completion claims; X7 pins
parity):

- text carries a `NEGATION_TOKENS` token → the v0.9.11 advisory
  path, exit-code free;
- text carries none AND the recorded first-run exit ≠ 0 →
  **refusal** citing this ADR (doctrine, never a foreign ledger id);
- `--evidence-exit-ok "<sentence>"` files it, stores
  `evidence_exit_basis` (attackable at review), silences the
  advisory (the basis IS the acknowledgment), and is counted in the
  ADR-033 override report — the single home of the overridden count
  (CC-2); `stats` adds only the warned population (recorded exit ≠ 0,
  no basis) with a pointer at that row. The refused class leaves no
  record, so it deliberately has no counter.
- a basis beside a recorded exit of 0 is refused at intake and by
  `validate` ("nothing to excuse", X5); an empty basis is refused;
  a legacy capsule lacking `returncode` is tolerated (recheck
  already tolerates it via `.get`).

**Decay: declined, with reason** (the ADR-032 exclusions form). A
legitimately-failing proof's non-zero exit is a permanent property
of the recipe, and re-verification re-runs the command anyway — a
decayed basis would re-ask a question whose answer cannot change.

`recheck` and `reaffirm` are untouched: they compare stability
against the *recorded* exit exactly as before. This gates filing,
not re-verification.

## Explicit non-goals — residuals owned

Mixed sentences (a positive fact AND an absence in one breath) carry
a negation token and ride the advisory path even though their
positive half is undemonstrated — splitting compound sentences is
semantic work this gate must not attempt; "one fact per claim" stays
the hygiene rule. The token test proxies the *sentence's* polarity,
not the recipe's: an inverted recipe (`! grep`) exits 0 and passes
silently; a differential proof (`diff` exiting 1) is falsely refused
and pays one basis, whose frequency the override row turns into a
fact. INFERRED/UNVERIFIED are untouched: they promise no
demonstration.

## Consequences

The exactly-decidable slice of the hollow class dies at intake,
where the pilot's QB-011 claim would have cost zero instead of a
verifier dispatch, a retraction ceremony, and a successor. The
undecidable slices keep the advisory, and their sizes are now
counted. Record shape changed (`evidence_exit_basis`) → schema `$id`
v0.12, validate mirror rules, and the shape-fingerprint pin updated
in the same diff (ADR-026).

**Canary faults.** X1: positive text + exit 1 refused naming this
ADR, nothing appended. X2: negation text + exit 1 files with only
the advisory. X3: `--evidence-exit-ok` files, stores the basis,
silences the advisory; X3b: a basis beside exit 0 refused at intake.
X4 (negative control): positive text + exit 0 files silently. X5:
`validate` refuses a basis beside a recorded exit of 0; X5b:
tolerates a basis on a legacy capsule lacking `returncode`. X7:
`done --claim` refused identically (both-or-neither held). X6 lives
in core tests (lexicon subset + distinct-constant identity).
