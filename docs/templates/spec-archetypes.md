# Spec Archetypes: A Field Guide

> Reader: anyone (human or agent) starting a component spec | Enables:
> classifying the component and drafting from the right archetype
> outline | Update-trigger: a new recurring component shape, or a change
> to spec-health / section-contract semantics
> Reference — component specification templates (optional satellite,
> like `.truth/README.md` § Feature specs — the ledger works without it)
> **Drawn for:** any future software project, component-by-component
> **Lineage:** IEEE 830 · Volere · Cockburn · DDD · BDD · ATAM · arc42
> **Use:** classify → interview → draft spec → gate every session
> **Status:** living reference — extend per project in `docs/templates/local-archetypes.md` (see Ownership below)

Six recurring component types, each with a literature-grounded outline, required artifacts, and mechanical verification rules — plus a bootstrap prompt that interviews you into a filled spec at the start of a new project.

Ownership: this guide and the six `archetype-*.md` blanks beside it are template-owned — they update through `copier update`, the same pattern as the `.truth/evidence-deny` baseline (the template owns the baseline, you own your additions). Per-project archetypes and amendments belong in a separate local file — `docs/templates/local-archetypes.md` is the suggested home — never in edits to the shipped files, which an update would hand back as conflicts. If your repo carries its own spec-convention doc, that doc takes precedence over the summary here.

---

## Contents

- [Literature lineage](#literature-lineage)
- [A · Domain / Core Library](#a--domain--core-library)
- [B · Data / Persistence Service](#b--data--persistence-service)
- [C · Interactive GUI / Frontend](#c--interactive-gui--frontend)
- [D · Integration / Adapter (ACL)](#d--integration--adapter-acl)
- [E · Pipeline / Transformation / Batch](#e--pipeline--transformation--batch)
- [F · Cross-cutting / Infra](#f--cross-cutting--infra)
- [Layer 0 — above every component](#layer-0--above-every-component)
- [The bootstrap prompt](#the-bootstrap-prompt)
- [Making it self-enforcing](#making-it-self-enforcing)
- [Appendix — oracle recipes that survive the screen](#appendix--oracle-recipes-that-survive-the-screen)

---

## Literature lineage

Each archetype below borrows its outline from a specific tradition, not a generic template. This is the index — which body of thought a given concern belongs to.

| Concern | Primary source | What it's good for |
|---|---|---|
| Requirements shell & fit criteria | Robertson & Robertson — Volere | Quality attributes, testable acceptance thresholds |
| Prose functional requirements | IEEE 830 / ISO 29148 | Service-shaped components: scope, function, interface |
| Actor-goal scenarios | Cockburn — *Effective Use Cases* | Interactive components, traceability to a user's job |
| Executable acceptance | North (BDD) · Adzic — *Spec by Example* | Given/When/Then criteria that double as tests |
| Domain modeling | Evans — *Domain-Driven Design* | Core/domain components, ubiquitous language, ACL pattern |
| Contract-based correctness | Meyer — Design by Contract | Pure functions/libraries: pre/post/invariant |
| Decision capture | Nygard — ADR format | Any component, "why", immutable once accepted |
| System context & views | Brown — C4 · arc42 | Cross-component maps, boundary diagrams |
| Quality-attribute scenarios | Bass/Clements/Kazman — ATAM | Stimulus / response / measure NFR statements |
| Golden-master testing | Classic regression-test practice | Deterministic transformation/pipeline components |

---

## A · Domain / Core Library

**Lineage:** Domain-Driven Design + Design by Contract

Pure logic, no I/O, imported by everything else — the vocabulary and rules the rest of the system builds on. Not a service: nothing to call over a network, nothing to render.

**Canonical outline**

1. **Bounded context & ubiquitous language** — the 3–5 core nouns, defined once, used everywhere identically
2. **Invariants** — what must never be true, with a concrete violation example for each
3. **Entity / value-object model**
4. **Operation contracts** — precondition, postcondition, invariant, per public function
5. **Extension points** — how a new variant/type is added without touching existing code
6. **Non-goals** — explicit refusal of I/O, persistence, UI
7. **Traceability** — which ADR backs each invariant

**Artifacts**
- Unified glossary doc
- ADR log
- Docstring + test pairs per contract
- Extension guide

**Verification rules**
- No import of I/O or framework libraries (static layer-rule check)
- Every public operation has a test asserting its stated pre/postcondition
- Every invariant cites an ADR or ledger id
- A glossary term used in code exists in the glossary (drift gate)

---

## B · Data / Persistence Service

**Lineage:** IEEE 830 + API-first contract (OpenAPI / AsyncAPI)

Owns a schema, exposes it over an interface, may carry validation logic. Judged on correctness of data and clarity of contract, not on interaction design.

**Canonical outline**

1. **Purpose & scope** — what data it owns, what it explicitly excludes
2. **Data model** — schema plus its versioning policy
3. **API contract** — endpoints, request/response shapes, error taxonomy (an actual OpenAPI file backs this, prose only references it)
4. **Business / validation rules**
5. **Non-functional requirements** — availability, latency budget, data-freshness policy
6. **Migration / versioning policy**
7. **Test / acceptance** — contract tests per endpoint

**Artifacts**
- OpenAPI / schema file
- Migration scripts
- Contract-test suite

**Verification rules**
- Schema change requires spec + ADR + changelog entry together
- Every endpoint has a request/response example test
- Any cached or mirrored data has a declared staleness policy

---

## C · Interactive GUI / Frontend

**Lineage:** Cockburn use cases + BDD + interaction design

Any user-facing surface with screens and state. The component most often under-specified, because "it's obvious once you see it" — until the error state nobody designed shows up in production.

**Canonical outline**

1. **Actor & goal** — who, and the job they're trying to get done
2. **Full use-case dress** — preconditions, main success scenario, extensions (Cockburn template)
3. **Screen / state inventory** — per screen: entry state, actions, transitions, exit
4. **Error / validation / empty-state behavior** — named explicitly, never implied
5. **Interaction NFRs** — latency budget, offline/responsive/device constraints, accessibility
6. **Acceptance criteria** — Given/When/Then per screen behavior
7. **Test strategy** — wireframe reference, visual-regression / e2e plan

**Artifacts**
- Dressed use-case doc
- Screen-state table
- Wireframe or mockup reference
- BDD feature files

**Verification rules**
- Every listed screen has an explicit error-state clause
- Every use case's extensions cover "system unavailable" and "user abandons"
- NFR section is non-empty — a stated budget, or an explicit N/A with reason
- Every acceptance criterion links to a real test id before being marked done

---

## D · Integration / Adapter (ACL)

**Lineage:** DDD Anti-Corruption Layer + consumer-driven contract testing

Bridges to a system you don't own or control. The spec's job is to name the boundary precisely, because the failure mode is always "it changed under us and we found out in production."

**Canonical outline**

1. **External dependency pin** — system, version, licensing/ownership boundary
2. **Translation map** — external field/concept → internal model field, one row per mapping
3. **Boundary direction** — read-only, write-back, or both, and why
4. **Divergence handling** — what happens when the external schema changes or is unreachable
5. **Compatibility watch** — how drift in the external system would actually be detected
6. **Regression contract** — golden-master re-run after any change on either side

**Artifacts**
- Field-mapping table
- Contract-test suite
- Compatibility-watch note or gate

**Verification rules**
- Every mapped field cites a test or ledger id as evidence
- A drift-detection mechanism is documented, even if manual — absence fails the gate
- Write-back scope is stated explicitly (prevents silent scope creep)

---

## E · Pipeline / Transformation / Batch

**Lineage:** Design by Contract + golden-master testing

Deterministic input-to-output transformation, no user in the loop, often feeding a downstream system where a wrong output costs real money or time.

**Canonical outline**

1. **Purpose & scope** — input format → output format, one line
2. **Transformation rules** — per feature: trigger, formula, whether it must survive later input changes
3. **Determinism guarantee** — same input always yields the same output, stated as a requirement
4. **Output contract** — exact format (layers, columns, units) — downstream is often external and paid
5. **Validation / gating** — what blocks emission
6. **Golden-master test contract** — reference fixtures, diff strategy

**Artifacts**
- Output-format spec
- Golden fixtures
- Diff / regression harness

**Verification rules**
- A repeatability test proves determinism (run twice, same output)
- Output format is version-pinned; consumers are notified on change
- Emission is gated on validation — no partial or invalid output ever leaves

---

## F · Cross-cutting / Infra

**Lineage:** arc42 cross-cutting concepts + ATAM quality-attribute scenarios

Not a feature — a guarantee threading through every other component: auth, observability, CI gates, an event bus. Usually the spec and the enforcement mechanism are the same artifact.

**Canonical outline**

1. **Concern & scope** — what it guarantees, system-wide
2. **Quality-attribute scenario(s)** — stimulus / response / measure (ATAM form)
3. **Enforcement surface** — which components/layers it touches, who can opt out (and why that's allowed)
4. **Failure / degradation behavior**
5. **Verification mechanism** — the gate itself

**Artifacts**
- Gate script
- Scenario table

**Verification rules**
- The concern's gate script exists and runs in CI or session-close
- "Spec health" for this concern literally means: the gate passes

---

## Layer 0 — above every component

These artifacts don't belong to any single component; they're read before any archetype above is chosen.

1. **Vision / mission** — why the system exists at all, one page
2. **Context map** — C4-level-1 diagram: components + external systems + arrows, dependency direction stated once
3. **Use-case inventory** — sea-level Cockburn goals, one row per actor
4. **NFR / quality-attribute master list** — Volere shell, one place; components reference it instead of repeating it
5. **ADR log** — decisions, immutable once accepted, superseded by a new ADR rather than edited
6. **Component roster** — one row per component: role, owner archetype, dependency direction

---

## The bootstrap prompt

The prompt itself lives at `prompts/spec-bootstrap.md` — one copy, no
duplicate here. Paste it at the start of a new component's life: it
classifies the component into exactly one archetype (asking one clarifying
question rather than guessing silently), branches into that archetype's
question battery, drafts the spec from the matching outline above with
missing answers marked OPEN instead of invented, and attaches the
archetype's verification checklist for every future session to re-check.

---

## Making it self-enforcing

A verification checklist an assistant reads once is a suggestion. The same checklist wired into a script that exits non-zero is a gate. The pattern generalizes across archetypes:

```
# generic spec-health gate — one per component
for component in components:
  # 1. does the spec exist and match the archetype outline?
  assert spec_file_exists(component)
  assert all_required_sections_present(component)

  # 2. is every OPEN marker tracked, not forgotten?
  assert every_open_marker_has_an_issue(component)

  # 3. do cited facts still hold?
  assert every_citation_has_live_evidence(component)

  # 4. does the archetype's own checklist pass?
  assert verification_rules_pass(component)

exit 0 only if all true; otherwise name exactly
what failed and where — never a bare non-zero.
```

The pseudo-code above stays pseudo-code — do not implement it as a second
script. The real, authoritative gate in this repo is
`bash scripts/spec-health.sh` (semantics in `.truth/README.md` § Feature
specs): it sweeps every spec and judges each cited ledger id. Each
archetype's "Verification rules" prose above is a courtesy summary; where
the prose and the gate disagree, the gate is authoritative.

This is not hypothetical machinery — it's the generalized shape of what already runs in the project this guide grew out of: a spec convention with a section contract, a truth ledger binding claims to evidence commands, and a health script that gates on the third check above (cited facts still hold) — the other three ran as convention, not script. For a new project, the same shape can start much lighter — a checklist a human reads at session-close — and grow into scripted gates only where a real incident justifies the weight.

---

## Appendix — oracle recipes that survive the screen

Each blank's Verification & Validation section names a technique and an
instrument; this appendix is the recipe book behind it — the forms that
survived the evidence screen and an adversarial round, and the traps
that looked equivalent and were not. Every recipe here was earned by a
reproduced failure, not deduced.

**The layer-rule sentinel (archetype A), canonical form:**

```
grep -rl 'import os' src/ | wc -l | tr -d ' ' | grep -qx 0 && echo LAYER-CLEAN
```

The `tr -d ' '` is mandatory. macOS `wc -l` pads its count with spaces,
so the unpadded form is a BLIND oracle: empty output and exit 1 in the
clean state AND the violated state — after seeding a real violation, a
recheck still reports "hash matches" and invites an agree. `!`-negation
is not an alternative: the screen refuses it (`!` tokenizes as a
program name). And filing over the exit-1 warning produces a hollow
VERIFIED — the `&& echo LAYER-CLEAN` tail is what gives the claim a
real success token to hash.

**ADR-007 discipline.** The honest wording of a layer rule ("no I/O
imports") is universal, and universal wording over a scoped command
fires the quantifier gate. Don't dodge it: fire the gate honestly, pay
the scope sentence (`--scope-ok` with a basis that says what the scope
actually covers), and pass a deliberate `--ttl-days` — an override
without one silently takes ADR-032's 30-day decay.

**Schema sentinels (archetype B).** Prefer path-tripwired,
output-stable forms: `jq -e 'has("x")' schema.json >/dev/null && echo
SCHEMA-OK` — the watched path stales the claim on any edit, the stable
token survives legitimate evolution. A hash pin on an evolving schema
is a divergence generator: every legitimate change burns the claim and
fails every citing spec. Reserve hash pins for genuinely frozen
contracts.

**Determinism and golden masters (archetype E).** These live ONLY in
the ADR-014 acceptance lane: a wrapper script, allow-listed in
`.truth/accept-allow`, declared as the work item's `--accept-cmd`, run
once at `done`. Every inline form — process substitution, chained
`sh`, temp files — is refused by the evidence screen, by design. The
structural consequence is disclosed, not papered over: an acceptance
oracle runs once; no standing "tests are green" or "pipeline
deterministic" claim exists, and faking one via evidence is refused.

**The gate itself (archetype F).** "The gate passes" is enforced by
`bash scripts/session-close.sh` running the executable drops in
`scripts/session-gates.d/` (or CI) — not by a ledger oracle. Say so in
the spec; a ledger id for "the gate passes" would be a claim about a
thing the ledger doesn't enforce.

**Validation attestations (every archetype).** There is no HUMAN
evidence class; the vehicle for "an expert walked through this and
signed off" is an UNVERIFIED claim with an explicit `--ttl-days N`,
agreed by a cross-session verifier. On expiry, ADR-019 semantics apply:
re-file, don't re-verify — the walkthrough is redone, a fresh claim
filed, and the spec's Validation line edited to cite it. The disclosed
cost: each expiry is a human re-walkthrough + re-file + spec edit + a
commit passing the full spec surface. And `verdict --recheck` on an
attestation files `cannot_verify` — there is nothing deterministic to
re-run; verifiers judge attestations manually (the verifier prompt says
so).

**Consumer conventions.** Per the precedence rule in this guide's
header, a repo carrying its own spec-convention doc outranks the
blanks. Such a repo must add the Verification & Validation section to
its own section contract, or the section is a dead letter there — the
blanks would carry it, the local gate would never miss it.

**The traceability sibling.** The V&V section is the authoring half:
which technique and which validation instrument the spec commits to.
The assertion-level traceability half — spec-coverage manifests:
`SC-<slug>-NNN` assertion ids plus a per-spec manifest watched by two
sentinel claims — is documented in the template source repo's
growth-gate archive. They compose: the V&V oracle id and the spec's SC
manifest cover the same spec from two sides. (`SC-` placeholders here
follow the same rule as `tr-XXXXXXXX`: never write a valid-looking
example id in a shipped doc.)

---

*Field guide compiled from IEEE 830 / ISO 29148, Volere, Cockburn's use-case template, Evans' Domain-Driven Design, Beck/North's BDD lineage, Meyer's Design by Contract, Nygard's ADR format, Brown's C4 model, arc42, and Bass/Clements/Kazman's ATAM — adapted into six recurring component archetypes and one bootstrap interview.*
