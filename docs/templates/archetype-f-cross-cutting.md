<!--
TEMPLATE — Archetype F: Cross-cutting / Infra
Source: spec-archetypes.md (Field Guide) · Lineage: arc42 cross-cutting
concepts + ATAM quality-attribute scenarios. Copy to
<component>/docs/specs/<kebab-case>.md, fill every bracket, delete
guidance comments, delete this banner.
-->
# Spec: <Concern name> — <one-line role, e.g. "the truth ledger / spec-health gate">

> Reader: <who reads this> | Enables: <understanding what this concern
> guarantees system-wide, and how that guarantee is actually enforced> |
> Update-trigger: <the guarantee changes, a new component opts in/out,
> the enforcement mechanism changes>

Serves: <UC-N (hook), or "all use cases indirectly — this is a system-wide
guarantee, not a feature">

## Intent

<What system-wide guarantee this provides, in one sentence. Why it needs
to be its own concern rather than duplicated inside every component.>

**Non-goals**: <what this concern does NOT guarantee — the edge of its
authority>

### Concern & scope

<Restate the guarantee as a boundary: which components/layers are
inside it, which are explicitly out (and why they're allowed to be).>

### Quality-attribute scenario(s)

<ATAM form: under [condition], the system shall [response], measured by
[metric]. One row per scenario — vague NFR prose ("should be fast") does
not survive contact with this table.>

| Stimulus | Response | Measure |
|---|---|---|
| <condition> | <required system behavior> | <the number that proves it> |

### Enforcement surface

<Which components/layers this touches. Can any of them opt out, and
under what circumstance is that actually allowed?>

### Failure / degradation behavior

<What happens when this concern fails — hard stop, or graceful
degradation? Name the actual behavior, not an aspiration.>

### Verification mechanism

<The gate itself — usually a script. "Spec health" for this concern
literally means: does this gate pass. Name the exact command.>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

- `tr-XXXXXXXX` — <one-line hook>

## Work

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text — for a cross-cutting concern, usually: the gate script
  exists, runs at the named point (CI / session-close), and fails
  correctly on a known-bad fixture>" (`wk-XXXXXXXX`)

## Verification & Validation

<!-- Pairing fixed by the Field Guide (spec-archetypes.md § Appendix —
oracle recipes). "The gate passes" is enforced by
`bash scripts/session-close.sh` running the drops in
`scripts/session-gates.d/` (or CI), NOT by a ledger oracle — never
imply one. Ledger ids here carry facts ABOUT the gate (it exists, it
fails the known-bad fixture); when they do, cite the id that CARRIES
the command — a wk- with --accept-cmd, or a standing sentinel tr- —
never the command text itself. -->

Verification: the gate script itself, per quality-attribute scenario,
enforced at session-close / CI (`scripts/session-gates.d/`); facts
about the gate carried by `wk-XXXXXXXX` (`--accept-cmd`) or standing
sentinel `tr-XXXXXXXX`.

Validation: SLO monitoring + error budgets + game days; incident review feeding
new rows into the scenario table — <who, cadence> — attestation
`tr-XXXXXXXX` (UNVERIFIED, `--ttl-days N`; expiry means
re-walkthrough + re-file + edit this line).
<!-- The attestation vehicle: an UNVERIFIED claim with an explicit
--ttl-days — no evidence command, a human event on the record. When it
expires (ADR-019), redo the review, file a fresh claim, and edit this
line to cite it. -->

Residual (accepted, not closable): <by TITLE only, e.g.
"unknown-unknowns — incidents are the universe's pull requests against
the scenario table">
<!-- Titles only in this subsection. An id written here is a live
tripwire that fails this spec when it dies — the opposite of
"accepted, not closable". -->

