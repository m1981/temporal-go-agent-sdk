# ADR-003: Satellite placement — what ships in the template, what stays in the consuming repo

Status: Accepted (2026-07-09, Michal; retroactive — records the doctrine
already applied in v0.5.1 and v0.5.2)
Amended by: note (2026-07-10) — the Consequences' pending application
landed as this ADR predicted: the `truth impact` verb passed the
placement test and shipped template-side (v0.5.7, FAULTS W1–W4 per
rule 3); the whisper hook and its deny-list config stayed consumer-side
(ADR-005, accepted in trial).
Date: 2026-07-09
Supersedes: —

## Context

The ledger grew satellites: mechanisms that are not the ledger core but
lean on it — spec-health (v0.5.1, `5a32f91`), doc-health (v0.5.2,
`c466beb`). Each raised the same question: does this belong in the copier
template (every consuming repo gets it and receives updates) or in the
consuming repo (one project's policy)?

The question was answered four times, consistently, without the rule ever
being written down:

- `spec-health.sh` → **template** (consumes only `truth list/issues
  --json`; encodes no project policy).
- The pilot's `check-governance.sh` and its Checks 5/6 (which *call* the
  satellites at pre-commit) → **consuming repo** (ADR immutability rules,
  README header formats, dead component names — pure project policy).
- `doc-health.sh` → **template**, but only after its one policy-bearing
  part (the forbidden-name regexes) was moved out of the script into an
  optional config file.
- The pilot's forbidden names themselves → **consuming repo**, as
  `scripts/doc-health.patterns`, a file the template deliberately does not
  ship.

An unwritten rule that has been load-bearing four times is exactly the
kind of fact a fresh session re-decides differently. Hence this record.

## Decision

Three rules govern every future satellite.

**1. The placement test.** A script ships in the template iff both hold:
(a) it consumes only the ledger surface (`truth * --json`) and/or plain
git; (b) it encodes zero consumer policy — no project names, paths beyond
structural conventions, or governance choices. Fail either test → the
script (or that part of it) stays in the consuming repo.

**2. Policy travels as config the template does not ship.** When a generic
mechanism needs project policy (which names are forbidden, which paths are
frozen), the template script reads an *optional* config file and degrades
gracefully — visibly, not silently — when it is absent. The template never
ships the config. Consequence: consuming repos' config is untemplated, so
`copier update` cannot collide with it, and the script itself stays
byte-identical between template and consumer (the "pre-align, then update,
zero conflicts" playbook, executed successfully at v0.5.1 and v0.5.2).

**3. The birth law.** Every satellite ships, in the same version: seeded
canary faults covering its semantics — including an injection assert so
the canary cannot pass with the fault unseeded, and a fault gating the
graceful-degradation path — plus a section in `.truth/README.md`. No
satellite exists ungated, not even briefly. (Canary growth to date:
19 → 42 → 45 → 48, one batch per satellite.)

## Consequences

Easier: template updates into live consumers are conflict-free by
construction, observed twice. The canary grows monotonically with the
mechanism surface, so "all canaries caught" keeps meaning something. The
placement argument never has to be re-had — apply the test.

Harder: the template carries scripts some consumers will not use
(accepted: they are dependency-free and inert until invoked). Config files
are a new silent-death surface — a deleted or typo'd patterns file turns a
check off; mitigated by rule 3's requirement that the absent-config path
is itself canary-gated and announces itself on stderr.

Pending application: arch-health (dependency-direction check) and the
`truth impact` verb + pre-edit whisper hook (ADR-005) — the verb passes
the test and upstreams; the hook and its deny-list config stay consumer-side.
