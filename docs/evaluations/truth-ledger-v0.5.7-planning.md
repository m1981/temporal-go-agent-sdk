# Evaluation: truth-ledger v0.5.7 planning machinery, reconciled with the paper

> Reader: this repo's operator and the truth-ledger template author (same person) | Enables: deciding how session-survival planning is done here, and feeding second-deployment evidence back to the paper | Update-trigger: a new template version changes the planning surface, or the paper (v2) is revised

Evaluated 2026-07-11 against template `543d549` (v0.5.7) and
`truth-ledger/docs/truth-ledger-paper-v2.md`. Evidence tags per charter §1.

## Correction to the prior evaluation (an instance of the paper's own §2 finding)

The prior session-evaluation claimed "v0.5.4 is the latest" —
VERIFIED-shaped but wrong: the evidence was `git ls-remote --tags` (latest
*tag*), the claim said latest *version*; main had moved to v0.5.7 untagged.
This is exactly the paper's dominant failure class (§2): a correct evidence
command backing an overreaching claim text — a quantifier/evidence-domain
mismatch, by this repo's own operator-agent, caught by reading the paper.
Filed here as a worked example rather than swept away.

## What planning machinery v0.5.7 actually has — VERIFIED(CLI + ADRs at 543d549)

- **Topology**: `issue --deps` (birth-time only; no post-hoc edit verb —
  ADR-006 first-wins makes duplicate-id re-filing inert, so ordering added
  later must live in prose: ADRs and RESUME.md).
- **Validity**: `--premise` at birth, `truth premise` post-hoc; `ready` =
  open ∧ deps closed ∧ premises valid (ADR-001 matrix).
- **Intent-time impact (new, ADR-005 trial, v0.5.7)**: `truth impact <path>` —
  which live/unverified claims watch a path, and which open issues those
  claims premise. Forward-looking; the piece the v0.5.4 evaluation missed.
- **Decomposition**: feature specs (`*docs/specs/*.md`), facts as ids,
  acceptance as pre-written `done --claim` texts, judged by spec-health.
- **Absent, still**: priority, milestones, estimates, progress-within-item —
  VERIFIED(grep in `scripts/truth` = 0). Planning here is topology +
  validity + impact + prose, deliberately.

## The reconciled proposal (what this repo now does)

1. `RESUME.md` (root, gate-exempt name the template pre-reserved) — ids and
   commands only, per the paper's §5 citation-over-restatement: prose facts
   rot, cited ids stay checkable. Caveat, honestly held: §5's transferable
   hypothesis says a new artifact class needs its own health tripwire;
   RESUME.md has none (spec-health sweeps only `*docs/specs/*`), so it is
   kept pointer-only and updated per charter §7 — accepted risk, not
   a solved problem.
2. `internal/runtime/docs/specs/membrane-hardening.md` — Phase-1 decomposition
   in the spec-health-native form: premises cited, acceptance pre-written.
3. Dep edges post-hoc: **dropped** (kernel design forbids it; see above) —
   ordering carried by ADR-011 + RESUME.md instead.

## Second-deployment observations (for the paper, §5 / §8 item 1 / ADR-005 gate)

This repo is a second deployment (day-0 2026-07-10; distinct operator-agent
sessions; 35+ records) — the "second repository" §5 says its decay
hypothesis needs, with the standing caveat that the operator overlaps the
template author, so §8 item 1 is only partially answered:

- **Tripwires fired correctly under real work**: 4 claims mechanically
  staled by later same-package commits (fsguard follow-on work) — recall
  behaved as designed; facts remained true (suites green), matching the
  paper's "diverged/stale conflates reality-change with recipe-change"
  vocabulary debt (§8 item 7).
- **ADR-005 adoption-gate data point**: the first real `truth impact` probe
  (`internal/runtime/base/runtime.go`) named 3 P0 claims and the held work
  item, and directly changed the next session's plan (the spec now mandates
  an impact check before editing). One whisper, behavior changed, no
  fatigue observed — n=1 for the gate ADR-005 is waiting on.
- **Discovery limit (§8 item 5) exercised**: the scaffolded AGENTS.md
  variant initially failed doctor G2 (no `scripts/truth` mention) — the
  behavioral-compliance limit is real; fixed by adding the discovery
  section, worth a template-side default.
- **spec-health §5 blind-spot warning fired usefully twice** (facts cited
  as ground truth but premise of no issue), both fixed by `truth premise` —
  evidence the warning earns its place.
