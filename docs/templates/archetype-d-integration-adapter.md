<!--
TEMPLATE — Archetype D: Integration / Adapter (ACL)
Source: spec-archetypes.md (Field Guide) · Lineage: DDD Anti-Corruption
Layer + consumer-driven contract testing. Copy to
<component>/docs/specs/<kebab-case>.md, fill every bracket, delete
guidance comments, delete this banner.
-->
# Spec: <Component name> — <one-line role, e.g. "the scene extractor">

> Reader: <who reads this> | Enables: <understanding the translation
> boundary without re-deriving it from the code> | Update-trigger: <the
> external system's version changes, a mapping changes, a divergence is
> discovered>

Serves: <UC-N (hook), ...>

## Intent

<What external system this bridges to, and why it's a separate
component rather than inline code in its consumer — usually: because the
external system is not owned by this team.>

**Non-goals**: <what this adapter deliberately does not translate, or
does not write back — the boundary is the point of this spec>

### External dependency pin

<System name, version, licensing/ownership boundary. Who can change it
out from under you, and on what notice (if any).>

### Translation map

<One row per fact this component reads from the external system — where
it lives in their model, where it lands in yours. This table IS the
contract; keep it current before code, not after.>

| External field/concept | Internal field | Notes |
|---|---|---|
| `<their.path>` | `<YourModel.field>` | <caveats, unit conversions, etc.> |

### Boundary direction

<Read-only, write-back, or both — and why. If read-only today, name the
condition under which that would be revisited (don't leave it as an
unstated default).>

### Divergence handling

<What happens when the external system's shape doesn't match what this
table assumes — a field is missing, a type changed, a version is
incompatible. Name the actual failure mode, not "handled gracefully.">

### Compatibility watch

<How would you actually find out the external system changed shape —
today, concretely. A pinned version + manual changelog read counts; "we
would notice" does not.>

### Regression contract

<Golden-master fixture(s) this component is re-run against after any
change on either side of the boundary.>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

- `tr-XXXXXXXX` — <one-line hook, tie it to a row in the translation map>

## Work

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text — for an adapter, usually: a named field survives
  extraction from a real/fixture external scene into the internal model,
  proven without hand re-entry>" (`wk-XXXXXXXX`)
