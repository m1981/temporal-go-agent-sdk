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

## Verification & Validation

<!-- Pairing fixed by the Field Guide (spec-archetypes.md § Appendix —
oracle recipes). The oracle line cites the id that CARRIES the command
— a wk- with --accept-cmd, or a standing sentinel tr- — never the
command text itself. Prefer path-tripwired, output-stable sentinels
over schema hash pins; a hash pin on an evolving schema is a
divergence generator (recipes in the appendix). -->

Verification: schema/endpoint contract tests + migration round-trip
tests, per the API contract table — oracle carried by `wk-XXXXXXXX`
(`--accept-cmd`) or standing sentinel `tr-XXXXXXXX`.

Validation: pilot consumer + production data-quality monitoring —
<who/what watches, since when> — attestation `tr-XXXXXXXX`
(UNVERIFIED, `--ttl-days N`; expiry means re-walkthrough + re-file +
edit this line).
<!-- The attestation vehicle: an UNVERIFIED claim with an explicit
--ttl-days — no evidence command, a human event on the record. When it
expires (ADR-019), redo the review, file a fresh claim, and edit this
line to cite it. -->

Residual (accepted, not closable): <by TITLE only, e.g. "the world's
semantics drifting under a conformant schema">
<!-- Titles only in this subsection. An id written here is a live
tripwire that fails this spec when it dies — the opposite of
"accepted, not closable". -->

