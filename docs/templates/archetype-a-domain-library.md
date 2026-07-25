<!--
TEMPLATE — Archetype A: Domain / Core Library
Source: spec-archetypes.md (Field Guide) · Lineage: DDD + Design by Contract
Copy this file to <component>/docs/specs/<kebab-case>.md, fill every
bracket, delete every guidance comment, delete this banner.
Section contract is fixed by this template set — do not rename or remove
Intent / Decisions / Ground truths / Work / Acceptance (id-citing rule:
`.truth/README.md` § Feature specs).
Only tr-/wk- ids that already exist and are live may be cited (verify
with `scripts/truth list --live` / `scripts/truth issues` before citing —
never invent one). Zero-id specs get a WARN from spec-health.sh, not a
failure — better an honest empty section than a fabricated id.
-->
# Spec: <Component name> — <one-line role, e.g. "the decomposition domain hub">

> Reader: <who reads this before touching the component> | Enables:
> <what this spec lets that reader do that they couldn't do from code
> alone> | Update-trigger: <what change to the world means this spec
> must be revisited>

Serves: <UC-N (hook), ...> <!-- or: "no use case directly — this is Layer-0
domain vocabulary consumed by UC-N's implementation," if that's honestly
the case; don't force a trace that isn't real -->

## Intent

<One paragraph: what this component is, why it exists, what it is NOT
(the component it's most often confused with, if any).>

**Non-goals**: <explicit refusals — no I/O, no persistence, no UI,
whatever this component deliberately does not do>

### Bounded context & ubiquitous language

<The 3–5 core nouns of this domain. One plain-language sentence each —
the concept, not the class name. This is the vocabulary every other
section below must use consistently.>

| Term | Meaning |
|---|---|
| `<Term>` | <plain-language definition> |

### Invariants

<What must NEVER be true. One violation example per invariant — a
concrete case, not an abstract description.>

1. <Invariant> — violated by: <concrete example>

### Entity / value-object model

<Entities and value objects, and the ownership/composition relationship
between them. A diagram or a short list is fine — this is not UML for
its own sake.>

### Operation contracts

<For each public operation: precondition, postcondition, invariant it
upholds. Table or prose, whichever reads better for this component.>

| Operation | Precondition | Postcondition | Invariant upheld |
|---|---|---|---|
| `<fn()>` | <what must be true to call it> | <what's true after> | <which invariant above> |

### Extension points

<How does someone add a new variant/type next year without touching
existing code? Name the exact mechanism (registry dict, ABC subclass,
whatever it really is) — not "it should be extensible.">

### Traceability

<Which ADR backs each invariant above — link, don't summarize (see
Decisions section).>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

<!-- tr- ids this spec stands on. Verify each is `live` before citing —
`scripts/truth list --live` — never file a bag of UNVERIFIED claims just
to fill this section. -->

- `tr-XXXXXXXX` — <one-line hook>

## Work

<!-- wk- ids implementing this spec (+ Beads twin if your repo runs the
Beads adapter — see docs/beads-integration-guide.md). -->

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text an evidence command can actually show — never a
  repo-wide clause backed by a package-scoped grep>" (`wk-XXXXXXXX`)
