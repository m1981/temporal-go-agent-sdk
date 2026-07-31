# ADR-026: the schema $id is a schema-contract version, and the hard version stamps are decidable in the battery (M1)

Status: Accepted (2026-07-19, operator) — spec-precision + a decidable-check
improvement from batch-2 review finding M1, re-verified against v0.9.8 in a
sandbox and by an adversarial reviewer before adoption. No runtime behavior
change: the changes are one `$id` string, three doc-stamp corrections, and
three new core tests. Implemented in the next release (CLI v0.9.9). Core tests
test_readme_title_equals_cli_version, test_schema_id_is_pinned,
test_schema_shape_fingerprint.
Date: 2026-07-19
Supersedes: — (adds a versioning policy the surfaces followed informally, and
mechanizes the two stamps that are a hard invariant)

## Context

Finding M1 observed that four surfaces carried divergent version stamps and
that nothing mechanical caught the drift:

- The CLI was at v0.9.8; the README **title** said v0.9.0 though its body
  already documented ADR-024/025 (v0.9.8 content); the paper's status line
  said the template "has since moved to v0.6.4" though its body covered
  mechanisms through v0.9.6; the schema `$id` said `truth-ledger-record.v0.7`.
- The `$id` staleness is the sharpest: a JSON-Schema `$id` is a
  contract-identity URI, and the record **shape** changed *after* v0.7 — the
  `contradicts` kind landed at v0.9.0, and field/constraint additions landed
  at v0.8.1 (the ts pattern) and v0.9.1/2 (overridden_duplicates, the
  issue_event accept returncode rule). Git history shows the `$id` was bumped
  *in the same commit* as each schema change through v0.7, then silently
  lapsed three times. It is stale by three shape changes, not one.
- The existing doc-coverage tripwire (a ledger claim watching the paper, the
  CLI, and the schema together) watches record **kinds and hardening ADRs**,
  not version **stamps** — so this class of drift had no mechanism at all.

The README title had, by contrast, moved in lockstep with the product version
on **every** feature release (v0.6.0 → v0.6.2 → v0.7.0 → … → v0.9.0) until the
v0.9.x spec-precision batch updated bodies but not the header stamp. So
"README title == CLI version" is a real invariant that lapsed, not a
coincidence — which makes it mechanizable without guessing a cadence.

## Decision

**1. The `$id` is a schema-contract version, defined and set correctly.** The
`$id` carries a two-component `vMAJOR.MINOR` schema-contract version that is
**independent of the product version** and is bumped **only when the record
shape changes** (a new kind, field, or constraint). It is set to
`truth-ledger-record.v0.9`. Not `v1.0` — that would falsely signal a
compatibility break, when all seven kinds and every record since v0.4 remain
valid. Not a patch-granular `v0.9.8` — that breaks the two-component
convention and would imply shape changes across 0.9.3–0.9.8 that never
happened (the last schema-shape commit predates them). Nothing resolves the
schema by its `$id` string (grep-confirmed: the literal appears only on the
definition line; the schema has no `$ref`, and both conformance tests load it
by path), so moving the URI breaks no consumer.

**2. The two hard-invariant stamps are decidable in the battery.** Two core
tests (which ship to deployments, where both surfaces come from the template
and so stay equal):

- `test_readme_title_equals_cli_version` — the README title MUST equal the CLI
  version (`scripts/truth` line 2). A release that bumps one MUST bump both.
- `test_schema_shape_fingerprint` — a sha256 of the schema **minus its own
  `$id`** is pinned. **Any** edit to the schema breaks the fingerprint,
  forcing a conscious "is this a shape change? then bump `$id`" review before
  the pin is updated. A bare `$id`-equals-constant test would *not* catch the
  next lapse — nothing ties the constant to the shape, so a shape change that
  forgets the bump still passes it. The fingerprint is the thing that turns
  the next silent lapse into a red test instead of the next audit's finding.
  `test_schema_id_is_pinned` additionally pins the expected `$id` string.

**3. The paper reference-not-restates its version.** The paper's status line no
longer names a frozen version; it points at `scripts/truth` for the current
version and lets the ADRs below say where each mechanism landed — the same
anti-drift discipline the paper already applies to its own line count. So it
carries no stamp to drift. The README file-tree's ADR listing likewise ends
with "the batch-2 spec-precision ADRs 014+ (the directory lists the current
set)" rather than a frozen enumeration.

## Consequences

- The `$id` correctly identifies the current contract, and a future shape
  change cannot ship without either bumping it or consciously overriding the
  fingerprint pin — the drift that lapsed three times is now a test failure.
- The two hard version stamps agree mechanically; the two that are
  informational (the paper, the README body) reference-not-restate.
- No runtime change: `truth` behaves identically; only `validate`'s durable
  contract identity and three doc stamps moved, plus three battery tests.

## Non-goals

Not enforcing the paper's prose against the code (the doc-coverage tripwire
already watches that surface). Not making the README body's ADR references
exhaustive (reference-not-restate is deliberate). Not a general SchemaVer
specification — the policy is exactly "two components, bump on shape change,"
enforced by the fingerprint. Not tying the `$id` minor to the product minor
(they are independent by design; the schema changes far less often).
