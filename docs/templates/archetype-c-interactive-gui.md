<!--
TEMPLATE — Archetype C: Interactive GUI / Frontend
Source: spec-archetypes.md (Field Guide) · Lineage: Cockburn use cases +
BDD + interaction design. If your repo already carries a filled GUI spec,
read it before filling this one — a worked example shows what a filled row
looks like, including how to write an honest "OPEN" cell instead of
inventing a behavior nobody specified. Copy to
<component>/docs/specs/<kebab-case>.md, fill every bracket, delete
guidance comments, delete this banner.
-->
# Spec: <Component name> — <one-line role, e.g. "screens">

> Reader: <who reads this before touching a screen> | Enables: <judging
> a screen's state/error/NFR coverage without re-deriving it from
> use-cases.md's prose> | Update-trigger: <a screen ships/changes state,
> an error/empty state is discovered, an NFR is set/renegotiated>

Serves: <UC-N (screen), UC-M (screen), ...> <!-- if the use-case dress
already exists in a use-cases.md, reference it here and do not restate
its main scenario/extensions in this file — this spec is narrower and
screen-shaped, the use case is goal-shaped. -->

## Intent

<Scope: which screens this spec covers. Non-goals: visual design
(color/layout, unless that's genuinely this project's concern);
anything owned by an external system's own UI (name it, per whatever
your project's own ACL/adapter boundary is).>

### Screen inventory

| Screen | Entry state | Core actions | Error / empty states | Exit |
|---|---|---|---|---|
| <Screen name> | <what's true when you land here> | <what you can do> | <named explicitly — "OPEN" if genuinely undefined, never left blank> | <what happens next, and where> |

### Interaction NFRs

| Screen | Constraint | Status |
|---|---|---|
| <Screen name> | <latency budget / offline tolerance / device constraint / accessibility> | <a number, or "OPEN — no fit criterion set"> |

### Test strategy

<What test convention covers this screen today (manual checklist,
Playwright, visual regression) — and honestly, what's OPEN. Prose
promising tests that don't exist yet is exactly the failure mode this
Field Guide exists to catch; if they're not written, say so.>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

- `tr-XXXXXXXX` — <one-line hook, tie it to the screen/row it supports>

## Work

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text — for a GUI, this usually means: a named state is
  reachable/unreachable under a named condition, proven by a test
  driving the actual UI, not just the underlying domain logic>" (`wk-XXXXXXXX`)

<!-- Any OPEN cell above with no wk- id attached surfaced while drafting
this spec, not from prior planning — say so plainly, in a closing
paragraph, rather than silently filing work on the reader's behalf. -->
