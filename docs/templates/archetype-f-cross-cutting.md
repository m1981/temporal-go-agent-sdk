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
