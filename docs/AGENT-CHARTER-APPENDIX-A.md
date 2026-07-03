# AGENT CHARTER — Appendix A: Component Type Profiles

> **Status:** Binding extension of the AGENT CHARTER. The charter's canonical rules
> (§1–§9) always apply and are NOT repeated here. Where this appendix says SKIP,
> that is as binding as MUST — producing skipped artifacts is scope creep (§4.4)
> and doc theater, not diligence.
> **RFC 2119 language applies.**

---

## A.0 Type Declaration (MUST)

A.0.1. Every top-level component MUST declare its type in the first ten lines of its
README, in this exact format:

```
> Type: C (Backend API) | Status: active | Horizon: H1
> Charter: ../AGENT-CHARTER.md | Profile: Appendix A.3
```

A.0.2. An agent starting work in a component MUST read this declaration first. If it
is missing, adding it (after asking the user, or inferring with an `INFERRED` tag)
is the agent's first task — before the requested work.

A.0.3. If a component's reality no longer matches its declared type (e.g., a Type A
library grew a database), the agent MUST flag this as a P0 finding. Type changes
require an ADR (charter §4.1 applies — a type change is a component-shaping decision).

A.0.4. The recognized types:

| Type | Name | Signature |
|------|------|-----------|
| A | Library / SDK | No UI, no DB, consumed by other code |
| B | CLI Tool | Terminal interface, single user |
| C | Backend API / Service | Network API + DB, no human UI |
| D | Full-Stack App | UI + backend + DB + auth |
| E | Data Pipeline / ETL / ML | Reads sources, transforms, writes targets |
| F | Embedded / Plugin / Host-bound | Runs inside a host (device, Blender, browser) |

---

## A.1 Type A — Library / SDK

**MUST maintain:** README (install + 3 usage examples), API reference generated from
docstrings/types, CHANGELOG (Keep-a-Changelog), semver discipline, ADRs for every
public-API decision.

**SHOULD maintain:** Tutorials/how-tos per Diátaxis; deprecation policy once there
are external consumers.

**SKIP:** Use cases, personas, UX artifacts, seeds, runbooks, ER diagrams.

**Type-specific guardrails:**
- A.1.1. The public API surface is the spec. Any change to it MUST appear in the
  CHANGELOG in the same PR, and breaking changes MUST bump major version.
- A.1.2. Type hints / signatures MUST be complete on public functions — types ARE
  the schema here, and they are CI-checkable (mypy/tsc). Prose describing types
  that the compiler could check is forbidden duplication.
- A.1.3. Evidence check before claiming API stability: run the type checker and
  the doc generator; cite both (charter §1).

---

## A.2 Type B — CLI Tool

**MUST maintain:** README with copy-pasteable examples, `--help` text generated from
command definitions, exit-code contract (documented table), config file JSON Schema
if a config file exists.

**SHOULD maintain:** ADRs for UX decisions (flag names, defaults, breaking flag
changes); shell-completion notes.

**SKIP:** Personas, UX design files, full use cases (commands are the use cases),
seeds (unless the tool owns local state — then a state-init note in README).

**Type-specific guardrails:**
- A.2.1. `--help` output and README examples MUST agree. CI SHOULD run the examples.
- A.2.2. Renaming or removing a flag is a breaking change: CHANGELOG + major bump.
- A.2.3. If the tool reads a config file, the schema MUST be validated at startup —
  a schema not enforced at runtime is decoration (charter §5.4 spirit).

---

## A.3 Type C — Backend API / Service (no UI)

**MUST maintain:** OpenAPI/GraphQL/Proto contract validated in CI; DB migrations
(every schema change is a migration — direct schema edits are forbidden); seeds in
three separated flavors (A.7); C2 diagram showing the service's neighbors; ADRs;
runbook stub once anything runs outside the dev machine.

**SHOULD maintain:** Event schemas in `specs/events/` if it emits/consumes messages;
contract tests with known consumers; observability notes (what to look at when slow).

**SKIP:** UX designs, personas, design tokens.

**Type-specific guardrails:**
- A.3.1. The API contract is design-first or generated-and-committed — either way it
  lives in the repo and CI fails if implementation diverges. An agent MUST NOT change
  an endpoint without touching the contract file in the same PR.
- A.3.2. Migration discipline: migrations are append-only in shared environments.
  Editing an applied migration is the ADR-immutability rule (§5.2) applied to data.
- A.3.3. Evidence check before drawing this service in any diagram: grep for the
  actual client calls (charter §2.2).

---

## A.4 Type D — Full-Stack App (UI + DB)

**MUST maintain:** Everything in A.3, plus: link-to-Figma (or equivalent) inside each
feature spec; committed screenshots of shipped key flows; design tokens as code;
use cases in `docs/use-cases/` for multi-step user flows; E2E tests for the flows
those use cases describe.

**SHOULD maintain:** Personas (once >1 user type); component library docs (Storybook)
past ~10 shared components; analytics/event-tracking spec.

**SKIP:** Nothing structural — Type D is the full-load case. Fidelity is throttled
by horizon (charter §4.4), not by artifact class.

**Type-specific guardrails:**
- A.4.1. **Post-launch, code + screenshots are the source of truth; the design file
  is a design-time artifact.** An agent MUST NOT "fix" shipped UI to match a Figma
  file without confirming which is authoritative — flag the divergence instead.
- A.4.2. Each use case SHOULD map to at least one E2E test; the test file references
  the use case ID (UC-NN). An E2E-less use case for shipped H1 functionality is a
  P1 finding.
- A.4.3. User stories live in the tracker, use cases live in the repo. An agent MUST
  NOT copy transient tracker tickets into `docs/` — that creates a second, rotting
  source of truth.

---

## A.5 Type E — Data Pipeline / ETL / ML

**MUST maintain:** Source schemas (what you read, with an `EXTERNAL — not under our
control` marker where true); target schemas (your contract); data dictionary with
field-level meaning, units, and nullability; DAG/flow diagram; data-quality checks
that run in CI or orchestration; ADRs for format/schema decisions.

**SHOULD maintain:** Lineage notes (which source fields feed which target fields);
freshness/completeness SLAs once anyone depends on the output; sample data for dev.

**SKIP:** UX artifacts, personas, use cases (replace with "business questions this
data answers" — one short section in README).

**Type-specific guardrails:**
- A.5.1. A target-schema change is a breaking API change: version it, changelog it,
  and check for downstream consumers before merging.
- A.5.2. Data dictionary coverage is CI-checkable: every target field MUST have an
  entry. Claiming coverage requires running the check (charter §1.4).
- A.5.3. Source schemas drift outside your control — the pipeline MUST fail loudly
  on schema drift, not coerce silently.

---

## A.6 Type F — Embedded / Plugin / Host-bound (device, Blender, browser ext.)

**MUST maintain:** Host interface spec (which host APIs/versions you depend on —
pinned); state machine diagram for modes/lifecycle if the component has modes;
message/file format schemas at every boundary with the host; ADRs (choices are
expensive to reverse here); install-into-host instructions in README.

**SHOULD maintain:** Compatibility matrix (host versions tested); a hardware/host-in-
the-loop test plan where pure unit tests can't cover behavior.

**SKIP:** DB migrations, seeds, runbooks (unless it ships to third parties), personas.

**Type-specific guardrails:**
- A.6.1. Host-version dependency MUST be pinned and stated in README line 1–10 area
  (next to the type declaration). "Works with Blender" is UNVERIFIED; "tested on
  Blender 4.2, VERIFIED(ci log)" is a claim.
- A.6.2. If two Type-F components target the same host in one repo, that is an
  automatic duplication-scan trigger (charter §4.2) — justify or consolidate.

---

## A.7 Cross-Type Rule: Seeds Come in Three Separated Flavors (MUST)

Applies wherever seeds exist (Types C, D, sometimes E):

| Flavor | Directory | Runs where | Never |
|--------|-----------|-----------|-------|
| Dev seeds | `seeds/dev/` | Local dev only | in prod |
| Test fixtures | `seeds/test/` | Reset each test run | shared with dev |
| Prod bootstrap | `seeds/bootstrap/` | Every deploy, idempotent | contain sample data |

A.7.1. An agent MUST NOT add sample/demo data to bootstrap seeds, and MUST NOT make
tests depend on dev seeds. Each `seeds/` tree carries a 5-line README stating its
flavor and trigger.

---

## A.8 Growth Gates (SHOULD)

Artifacts are added when their trigger fires — not before (doc theater) and not
long after (debt). When an agent observes a fired trigger without its artifact,
that is a P1 finding:

| Trigger just became true | Artifact now due |
|---|---|
| First external user/consumer | CHANGELOG + semver |
| First database table | Migrations + seed separation (A.7) |
| First network API endpoint | Contract file in repo + CI validation |
| First UI screen | Figma link in spec + tokens as code |
| First production deployment | Runbook stub + observability note |
| First second-person on the team | ADR folder + PR template + CONTRIBUTING |
| First event emitted/consumed | Event schema in `specs/events/` |

---

## A.9 The Three-Question Gate for Any New Document (MUST)

Before creating any doc not mandated by the component's profile above, the agent
MUST answer, in the PR/commit description:

1. **Who will read this?** (a named role — "nobody" kills the doc)
2. **What decision or action does it enable?** ("none" kills the doc)
3. **What event triggers its update?** ("nothing" kills the doc — it will rot)

If any answer is empty, do not write the document. Charter §6.3's specificity rule
applies: documentation that would fit any project is decoration.

---

*Governed by charter §5.2: extend or change this appendix via a superseding ADR.*
