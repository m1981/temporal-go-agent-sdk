<!--
TEMPLATE — Archetype B: Data / Persistence Service
Source: spec-archetypes.md (Field Guide) · Lineage: IEEE 830 + API-first
(OpenAPI/AsyncAPI). Copy to <component>/docs/specs/<kebab-case>.md, fill
every bracket, delete guidance comments, delete this banner. Section
contract is fixed by this template set (id-citing rule:
`.truth/README.md` § Feature specs). Verify every
tr-/wk- id is live before citing — never invent one.
-->
# Spec: <Component name> — <one-line role, e.g. "the material catalog service">

> Reader: <who reads this> | Enables: <what it lets them do> |
> Update-trigger: <schema change, endpoint change, freshness-policy
> renegotiation>

Serves: <UC-N (hook), ...>

## Intent

<One paragraph: what data this service owns, why it exists as its own
service rather than living inside a consumer.>

**Non-goals**: <what this service explicitly does NOT own — often the
most important line in the spec; e.g. "price-free by design," "no
write-through from consumers">

### Purpose & scope

<What data it owns, restated as a boundary: this service is the
canonical source for X; it is explicitly not the source for Y (name who
is).>

### Data model

<Schema shape, plus its versioning policy — can a field be added/removed
freely, or does every schema change need a migration + consumer notice?>

### API contract

<Endpoints, request/response shapes, error taxonomy. An actual
OpenAPI/AsyncAPI file should back this; this prose only points at it —
do not restate the schema in prose (facts appear only as ids and
artifacts, never restated as prose — prose has no tripwire; the rule in
`.truth/README.md` § Feature specs applies to schemas too).>

| Endpoint | Trigger | Returns | Failure modes |
|---|---|---|---|
| `<METHOD /path>` | <what calls it> | <shape> | <named errors, not "handles errors"> |

### Business / validation rules

<Rules this service enforces on the data it owns — not general CRUD, the
domain-specific ones.>

### Non-functional requirements

<Availability expectation (can this be down without stopping the
business, for how long); latency budget; data-freshness/staleness
policy for anything cached or mirrored elsewhere.>

### Migration / versioning policy

<What a breaking schema change costs, who gets notified, how consumers
pin a version if they need to.>

### Test / acceptance strategy

<Contract tests per endpoint — what's covered today, what's OPEN.>

## Decisions

- `docs/adr/NNN-*.md` — <one-line hook>

## Ground truths

- `tr-XXXXXXXX` — <one-line hook>

## Work

- `wk-XXXXXXXX` — <one-line hook>

## Acceptance

Pre-written `done --claim` texts, scoped to evidence commands:

- "<claim text an evidence command can actually show>" (`wk-XXXXXXXX`)
