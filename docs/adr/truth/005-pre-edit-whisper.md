# ADR-005: Pre-edit whisper — mechanical impact surfacing at edit intent

Status: Accepted in trial (2026-07-10, Michal) — the `truth impact` verb
and canary faults shipped template-side in v0.5.7; the whisper hook is
wired consumer-side in the template repository itself, whose own ledger
(created 2026-07-10) is the re-scoped trial venue: it has live watched
paths and demonstrably active harness sessions, which the pilot this
gate originally named could not be confirmed to have from here. Full
acceptance — recommending the hook pattern to consumers — still waits on
this ADR's own adoption-gate evidence: whispers that change agent
behavior, without fatigue. Template-side faults are W1 (watched path
reports, injection-asserted), W2 (unwatched path silent — the fatigue
budget as a property), W3 (premised work predicted HELD), W4 (unreadable
ledger degrades visibly); the deny-stage check is consumer policy and
lives with the hook, outside the template canary.
Amended by: note (2026-07-12) — first trial evidence landed
(2026-07-11 cross-model runs; scored record in trial-prompts/RUNBOOK.md
with raw event streams alongside): the behavior-change half of the gate
is met on two model tiers (Fable and Sonnet both surfaced or acted on
the prediction unprompted); the deny stage held mechanically on every
Claude tier; and the hook pattern proved harness-portable — a pi
extension (.pi/extensions/truth-whisper.ts, same deny list, same
matcher, same metric file) blocked the exact edit that an unarmed,
norms-informed external agent had made the day before. The gate stays
open on the fatigue half: whisper-count-per-session evidence from
ordinary work sessions (.git/truth-whisper.seen) is still accumulating.
Trial also surfaced, unfixed: the deny reason's amend-flow hint reads
as a bypass ritual to weaker models, and the consumer hook misbehaves
in git worktrees.
Amended by: note (2026-07-12) — both consumer-hook residuals above are
now closed (scripts/truth-whisper.py + .pi/extensions/truth-whisper.ts):
the deny reason names a human actor and no longer teaches a bypass
(one voice with .githooks/pre-commit); the worktree crash is fixed by
resolving the seen-cache via `git rev-parse --git-path` and wrapping the
append (whisper fails OPEN, per this ADR). Building the gate surfaced a
third, latent bug — the hook compared an abspath'd file against git's
realpath'd root, so a symlinked path component (macOS /var, symlinked
homes) made an in-repo file look external and bailed BEFORE the deny
stage, i.e. deny failed OPEN; both harnesses now realpath both sides.
The consumer hook, which has no template-canary home (ADR-003 rule 2),
now has its own gate: scripts/test-whisper-hook.sh (deny voice, main +
worktree whisper, injection-verified). The fatigue half of the adoption
gate is still the only thing open.
Originally: Proposed (2026-07-09; adoption gated on earning its keep in
the pilot first, per the growth-gate discipline).
Date: 2026-07-09
Supersedes: —

## Context

The paper's stated weakest link is behavioral: the entire truth layer is
discovered through a snippet in instruction files, and an agent runtime
that never loads them bypasses everything. All current triggers are
post-hoc (commit, merge) or voluntary (`ready`, `list --live`). Nothing
fires at the moment of *intent* — when a file is about to be edited.

The motivating idea (operator, 2026-07-09) was a checkout model in the
Perforce/ClearCase style: no edit without a checkout, and on-checkout
hooks firing immediate actions, possibly agent calls. Examination against
field data kept one insight and rejected the rest:

- **Kept:** the pre-change intent signal. Agents edit through harness
  tools, and tools are interceptable — a pre-edit hook *is* a checkout
  event, deterministic and free.
- **Rejected — locks:** checkout locking solves write conflicts; the
  field's disease is stale knowledge, not concurrency (six sessions
  interleaved one ledger, zero corruption).
- **Rejected — agent calls in the trigger path:** the trigger would be
  mechanical but the action a judgment again; judgments stay scarce,
  attributable, and human-adjacent (operations guide §4).
- **Rejected — blocking as the default:** prevention must be near-perfect
  to beat detection and fails open trivially (edit outside the harness);
  detection at commit is already property-grade. Per-edit prompts would
  also rebuild the warning-fatigue loop v0.4 repaired (F2) — the pilot's
  tripwire precision was good *because* firing is commit-grained and rare.

## Decision

Two pieces, split by the ADR-003 placement test.

**1. `truth impact <path>...` — core verb, template-side.** A pure,
read-only fold query: for each path, the live/unverified claims whose
`evidence_paths` match it, and the open issues carrying those claims as
premises. Constraints:

- **One matcher.** Path matching reuses the exact function
  `invalidate-scan` uses (`*` stops at `/`, `**` spans). A second matcher
  implementation is forbidden — two copies of the matching contract will
  drift (the F1/F5 lesson), and then the whisper predicts stalings the
  scan never executes.
- **Exit codes are the contract:** `0` silent (nothing watches these
  paths), `3` watched (report on stdout). `--json` for harnesses.
- **Mechanics, never judgment.** Output *predicts* what the machinery
  will do ("committing a change here STALES tr-x; if premise tr-y dies,
  `ready` HOLDs wk-z"), ordered by tier (ADR-001), phrased as prediction —
  an edit is a draft with no anchor commit, so the whisper never files
  anything. Appends remain the scan's and the verifiers' job.

**2. The whisper hook — consuming-repo-side** (fails the placement test:
frozen-path policy and harness wiring are consumer-specific). A pre-edit
hook (e.g. PreToolUse on Edit/Write in the agent harness) with two stages
and opposite failure policies:

- **Deny stage, fails closed:** paths on a deny list (frozen snapshots,
  accepted ADRs, attic) block with the reason and the documented amend
  flow. Norm→property conversion for rules that today are sentences in
  instruction files. The deny list is a config file the template does not
  ship (ADR-003 rule 2).
- **Whisper stage, fails open — visibly:** run `truth impact`; on exit 3,
  inject the report into the agent's context. If the CLI errors, emit one
  line ("truth impact unavailable") and allow the edit — advisory
  machinery never blocks work, but may not fail silently (the F1 lesson).

**Fatigue budget, designed in (the F2 lesson):** silence is the default
and a *canary-gated property* — unwatched paths must produce zero output;
plus first-touch-per-session dedup, re-whispering only when the ledger has
changed since.

**Self-defense (ADR-003 rule 3):** canary faults W1–W4 — watched path
reports the claim (with injection assert), unwatched path stays silent,
denied path blocks, unreadable ledger degrades visibly without blocking.
`doctor` checks the hook is wired in the *active* hook path, with the same
skepticism the pilot's verifiers showed toward `core.hooksPath`.

## Explicit non-goals

No locks. No agent calls fired by edits. No edit-time staling (the
ledger's time base is the commit; drafts have no anchor). No coverage of
human editors — humans meet the ledger at commit, as before; the
asymmetry is accepted and documented, not hidden.

## Consequences

Easier: discovery of the truth layer becomes a property of the harness
instead of a hope about instruction files — an agent that read nothing
still gets the ledger surfaced the moment it touches a watched file. The
frozen set gains real enforcement. `impact` is also a useful human query
("what does the ledger know about this file?") independent of any hook.

Harder: two new config surfaces (deny list, hook wiring) that can die
silently — mitigated by W-faults and doctor, but the dead-tripwire episode
(field notes §3.1) says metadata rot is the failure mode to respect. The
whisper's value degrades if evidence_paths coverage is sparse or mis-filed
— it inherits the ledger's existing INV-M exposure rather than adding to it.

One-sentence summary: **the whisper is `truth ready` inverted** — instead
of the agent asking "what work is safe?", the harness asks "what knowledge
does this edit endanger?" — same fold, same matrix, same matcher, new
trigger.

## Adoption gate

Implement in the pilot repository first (spec per its convention, `wk-`
issue, Acceptance pre-written with the W-fault names). Upstream the verb
as a subsequent minor version (v0.5.3, the number this gate originally
reserved, was consumed by ADR-006's issue-fold hardening before this ADR
was adopted) — with the W-faults in the shared canary — only after pilot
sessions demonstrate signal (whispers that changed an agent's action)
without fatigue (whisper count per session staying low). If the fatigue
budget fails in practice, the fallback is narrowing the whisper to P0/P1
tiers before abandoning it.
