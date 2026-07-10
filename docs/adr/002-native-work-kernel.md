# ADR-002: Native work kernel — issues as ledger records

Status: Accepted (2026-07-08, Michal; implemented in v0.5)
Date: 2026-07-08
Supersedes: — (narrows the role of the external-tracker default introduced
with the v0.4.1 adapter seam; does not remove the seam)

## Context

`truth ready` exists to intersect two answers: what is *unblocked* (the
tracker's) and what is *still true* (the ledger's). Since v0.4.1 the
tracker side is an adapter seam (E1): any command emitting a JSON array of
`{id, title}` issues. The first field trial (kuchnie, 2026-07-08) wired
Beads through that seam and exposed the running cost of keeping the work
side external:

1. **The seam is a defended border.** A normalization adapter, two canary
   checks, and a documented failure-mode table exist solely to keep the
   join alive across a contract the other side can change at will.
2. **Two sync stories.** Ledger records ride every `git push` and merge via
   the union driver with a confluence proof. Beads' issue data is
   Dolt-local; it does not travel with the repo, so the join silently
   depends on state git cannot see.
3. **The discipline gap is structural, not accidental.** The premise link —
   the entire value of the pairing — is a second command against a second
   tool (`truth premise <issue> <claim>`), and nothing in the external
   tracker can even know it is missing. The trial's operator concluded the
   gate "is only as good as the discipline of the agents using it."
4. **A trivial usage profile.** The trial used four tracker verbs: create,
   depend, ready, close. None of the tracker's remaining surface
   (assignees, priorities, due dates, estimates, hierarchy, compaction)
   was touched.

Meanwhile the ledger already holds most of a tracker: append-only records
with a confluent fold ordered by `(ts, id)` (INV-A), premise records that
already carry issue ids, actor/session attribution on every record, a
human gate (G12), and a canary that seeds a fault for every semantic. In
ledger terms an issue *is* a claim about the future — "X should be done
and is not" — an intention that consumes live claims as premises and, on
completion, should produce a new verified claim. The tools were separated
by implementation history, not by kind.

Options considered: (a) keep Beads as the blessed default and harden the
seam further — accepts costs 1–3 permanently; (b) absorb a full tracker
into `scripts/truth` — rebuilds Beads badly inside the one tool whose
credibility rests on being small and auditable; (c) a minimal native work
kernel: issue records in the same ledger, same fold, five verbs, exposed
through the existing E1 seam so it competes with external trackers instead
of forbidding them.

## Decision

Adopt (c). `scripts/truth` gains a work kernel consisting of two record
kinds and five verbs, governed by the ledger's existing principles.

**Records.** Both kinds live in the same `claims.jsonl`, protected by the
same INV-A line-prefix gate, folded in the same `(ts, id)` total order:

    {"kind": "issue", "id": "wk-<hash8>", "ts": ..., "actor": ..., "session": ...,
     "payload": {"title": ..., "text": ..., "deps": ["wk-..."], "premises": ["tr-..."]}}

    {"kind": "issue_event", "id": "tr-<hash8>", "ts": ..., "actor": ..., "session": ...,
     "payload": {"issue": "wk-<hash8>", "event": "claimed" | "released" |
                 "closed" | "reopened" | "cancelled", "basis": "..."}}

(As implemented: the issue's identity is its wk- envelope id; events are
ordinary tr- records referencing it via `payload.issue`, mirroring how
verdicts reference claims. `cancelled`/`reopened` ride flags on `done`
rather than adding verbs.)

Issue *status is derived by the fold, never stored* — exactly as claim
status is. Re-filing an `issue` record with an existing id updates payload
fields (fold: last write in `(ts, id)` order wins); status moves only
through events. Dependency cycles fail loudly at filing time.

**Status semantics.** `open` → `claimed` → `closed`, with `reopened`
returning to open: work is cyclical, so `closed` is NOT terminal — unlike
`retracted`, because closing asserts completion, not falsity. `cancelled`
IS terminal and is a human tombstone requiring `TRUTH_HUMAN=1` (G12
symmetry: killing an intention without evidence of completion is the same
class of act as killing a fact). An agent that believes an issue should
die files `closed` with a basis saying so, or leaves it for the human
queue. `closed` and `cancelled` events require a `--basis`; verdict
discipline applies (cite what you did, never a vibe).

**Readiness.** `ready(issue) = status is open ∧ every dep is closed ∧
every premise passes the ADR-001 matrix` — the matrix is reused verbatim
(live passes; unverified warns; cannot_verify blocks only P0; stale/
diverged/retracted/missing always block, shown as HELD). Nothing in
ADR-001 changes.

**Verbs.**

    truth issue "title" [--deps wk-a,wk-b] [--premise tr-x --premise tr-y] [--text ...]
    truth start <wk-id>            # files claimed
    truth done <wk-id> --basis "..." [--claim "<fact>" --evidence-cmd ... --paths ...]
    truth ready                    # native join when issue records exist
    truth issues [--json | --ready-json]

Two behaviors are the point of the ADR and must not be cut in
implementation:

- **Premise-at-birth.** `--premise` is accepted at creation; an issue
  created with zero premises prints a warning naming the discipline it is
  skipping. Not an error — ADR-001's friction budget (E4) applies to work
  exactly as it applies to claims.
- **Claim-at-death.** `truth done --claim ...` files the completion fact
  and the closing event atomically (one fold, two records, same session).
  The claim goes through the normal intake — including the G6 determinism
  double-run — and is subject to verification like any other. Work
  consumes truths and emits truths; the kernel records both ends.

**E1 preserved, defaults re-pointed.** `truth issues --ready-json` emits
the exact `[{id, title}]` adapter contract, making the kernel a tracker
source like any other. Source precedence for `truth ready` becomes:
`--stdin`, then `TRUTH_TRACKER_CMD`, then **native if any issue records
exist**, then the external default (`bd ready --json`). A repo that never
files an issue record keeps its external tracker untouched; a repo can run
both during migration and diff the joins.

**Refusal list (binding).** The kernel will not grow: assignees,
priorities, due/defer dates, time estimates, labels, hierarchical issues,
comments, attachments, queries beyond the five verbs, or compaction.
Anything on this list requires a superseding ADR, not a flag. Rationale:
the ledger's audit-worthiness is a function of its size; the canary must
be able to exercise every semantic, and every feature added here is a
feature the confluence and append-only arguments must newly cover.
Compaction in particular is refused because it cannot coexist with INV-A
without an epoch/snapshot mechanism — if issue-record volume ever makes
the fold measurably slow, that is the trigger for a dedicated ADR, and the
known cliff is accepted and documented now.

**Canary (gating, before merge).** New seeded faults, at minimum: agent
`cancelled` without `TRUTH_HUMAN=1` must be refused; `ready` must HOLD an
issue whose premise is stale and pass one whose premise is live
(diverged-premise blocking is covered by the ADR-001 conformance matrix at
unit-test level, not by a dedicated seeded fault); dep-blocked issues must
not appear; a dependency cycle must be rejected at
filing; direct edit of an issue record must trip the INV-A gate;
`issues --ready-json` piped through `truth ready --stdin` must produce the
identical join as the native path (the seam and the kernel may never
disagree); `done --claim` must file both records or neither. Per the
standing rule, each fault must also *demonstrably inject* (the canary must
not lie in either direction).

## Consequences

One storage, one merge story, one fold: issues gain the confluence proof,
git-native sync, attribution, and the human gate for free, and the E1
border shrinks from "defended contract with a third-party tool" to "an
optional compatibility surface we also happen to implement." The
premise-discipline gap becomes partially mechanical (warning at birth)
instead of purely cultural, and the claim-at-death path closes the loop
the two-tool design left open. The external-tracker seam remains for teams
invested in one — and doubles as the migration and the exit path: run
both, compare, retire the loser.

The costs are accepted knowingly. `scripts/truth` grows by roughly two
hundred lines and the canary by several checks — real growth in the one
file whose smallness is a feature; the refusal list is the fence. Issue
events churn faster than facts, so the ledger file grows faster than
before; at the scale this tool targets (solo developers and small teams
with agent swarms) the fold stays in milliseconds, and the compaction
cliff is documented rather than engineered for. Users of Beads-specific
ergonomics (`bd prime` context injection, IDE integrations, ephemeral
issues) lose them unless they keep Beads through the seam — the kernel
deliberately does not compete on features, only on epistemics. Revisit via
superseding ADR if: the refusal list is breached in practice, fold time on
a real repo exceeds ~1s, or the A/B period shows the four-verb model is
too thin for real multi-agent work.
