<!--
TEMPLATE — Archetype E: Pipeline / Transformation / Batch
Source: spec-archetypes.md (Field Guide) · Lineage: Design by Contract +
golden-master testing. Copy to <component>/docs/specs/<kebab-case>.md,
fill every bracket, delete guidance comments, delete this banner.
-->
# Spec: <Component name> — <one-line role, e.g. "CAM enrichment">

> Reader: <who reads this> | Enables: <trusting the output without
> re-deriving the transformation rules from the code> | Update-trigger:
> <a transformation rule changes, the output format changes, a
> downstream consumer's tolerance changes>

Serves: <UC-N (hook), ...>

## Intent

<Input → output, one line. Why this is a separate pipeline stage rather
than folded into its producer or consumer.>

**Non-goals**: <what this stage explicitly does not do — e.g. "nesting
is a permanent non-goal, an external service owns it">

### Purpose & scope

<Restate input/output as a boundary: what this stage is trusted to
compute, what it explicitly passes through unchanged.>

### Transformation rules

<Per feature/operation: what triggers it, the formula/logic, and whether
it must survive a later change to the input (associativity) — does
moving a wall re-trigger this rule correctly, or does it go stale?>

| Rule | Trigger | Formula / logic | Survives later input change? |
|---|---|---|---|
| <name> | <condition> | <the actual formula, not "computed appropriately"> | <yes/no, and why> |

### Determinism guarantee

<Same input always yields the same output — stated as a requirement,
not assumed. If it's not deterministic, name the source of variance
explicitly.>

### Output contract

<Exact format: layers/columns/units. Downstream is often external and
paid (a CNC shop, a cutting service) — a format ambiguity here is a
money problem, not a style problem.>

### Validation / gating

<What blocks an output from being emitted. No partial or invalid output
should ever leave this stage silently.>

### Golden-master test contract

<Reference fixtures, diff strategy, where the harness lives.>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

- `tr-XXXXXXXX` — <one-line hook, tie it to a transformation rule above>

## Work

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text — for a pipeline, usually: a named rule produces a
  specific, hand-computed output for a specific fixture input, matching
  a reference to the unit>" (`wk-XXXXXXXX`)

## Verification & Validation

<!-- Pairing fixed by the Field Guide (spec-archetypes.md § Appendix —
oracle recipes). The oracle line cites the id that CARRIES the command
— here always a wk- with --accept-cmd — never the command text itself.
The determinism/golden-master check lives ONLY in the ADR-014
acceptance lane: a wrapper script, allow-listed in
`.truth/accept-allow`, run once at `done`. It is NEVER a standing
evidence claim — every inline form is refused by the screen, and there
is no standing "tests are green" claim to fake (that gap is
structural; disclose it, don't paper over it). -->

Verification: golden master + run-twice determinism, via a wrapper
script wired as the acceptance oracle — carried by `wk-XXXXXXXX`
(`--accept-cmd`, ADR-014).

Validation: expert sign-off on the golden fixtures + downstream
  consumer acceptance (the blessing IS
the validation event) + parallel/shadow run — <who, date> —
attestation `tr-XXXXXXXX` (UNVERIFIED, `--ttl-days N`; expiry means
re-walkthrough + re-file + edit this line).
<!-- The attestation vehicle: an UNVERIFIED claim with an explicit
--ttl-days — no evidence command, a human event on the record. When it
expires (ADR-019), redo the fixture review/shadow run, file a fresh
claim, and edit this line to cite it. -->

Residual (accepted, not closable): <by TITLE only, e.g. "inputs the
fixture corpus never sampled">
<!-- Titles only in this subsection. An id written here is a live
tripwire that fails this spec when it dies — the opposite of
"accepted, not closable". -->

