# ADR-004: Tracker adapter seam — the ledger degrades to a dashboard, never errors

Status: Accepted (2026-07-09, Michal; retroactive — records the v0.4.1
decision, commits `04c376e` and `4c74f36`, which predates ADR-002)
Amended by: ADR-002 (2026-07-08, implemented v0.5) — the three-source
precedence in the Decision below gained a fourth entry: when the ledger
holds issue records and `TRUTH_TRACKER_CMD` is unset, the native work
kernel serves the issue list and the Beads default is never consulted.
Shipped order: `--stdin`, `TRUTH_TRACKER_CMD`, native kernel, `bd ready
--json`; the native path is canary-gated separately (FAULT R3).
Date: 2026-07-09 (decision made 2026-07-08, v0.4.1)
Supersedes: — (ADR-002 later narrowed the external tracker's *role* by
adding a native work kernel; it explicitly kept this seam)

## Context

`truth ready` is a join: the tracker answers *what is unblocked*, the
ledger answers *what is still true*. v0.4 hard-wired the tracker side to
one command (`bd ready --json`), which made the ledger's flagship gate
hostage to one external tool's presence, health, and output contract.

Alternatives considered at the time:

1. **Require a tracker** — error when absent. Rejected: it makes the
   truth layer uninstallable in repos that track work elsewhere (or not at
   all), for no epistemic gain.
2. **A plugin/registry system** — per-tracker adapter modules. Rejected:
   machinery disproportionate to the need; the join needs only `id` and
   `title`.
3. **A minimal seam with graceful degradation** — chosen.

## Decision

`truth ready` consumes any source that emits a JSON array of issue objects
with an `id` (plus optional `title`), resolved in precedence order:

1. a pipe: `<tracker-cmd> | truth ready --stdin`
2. the environment: `TRUTH_TRACKER_CMD="<cmd printing the array>"`
3. the default Beads adapter (`bd ready --json`, raw array only — a `bd`
   version emitting anything other than a bare JSON array hard-fails here;
   normalization requires pointing `TRUTH_TRACKER_CMD` at
   `scripts/truth-bd-adapter.sh`, i.e. via path 2, not this default)

A missing or failing tracker does not produce a traceback and does not
disable the ledger: `ready` exits with guidance, and the layer **degrades
from a gate to a dashboard** (`truth queue`, `truth list --live` remain
fully functional). All three source paths are canary-gated (FAULT J
family, `4c74f36`).

The contract is deliberately minimal — `{id, title}` — because the join
uses nothing else; richer coupling (premises, status, dependency graphs)
is exactly what ADR-002's native kernel later provided *inside* the
ledger, where the contract cannot drift.

## Consequences

Easier: the ledger installs anywhere, tracker or no tracker. Tracker
migrations never touch core code — the pilot ran Beads and the native
kernel side by side, diffing `truth issues --ready-json` against the Beads
adapter through the same seam, which is also what made ADR-002's migration
path incremental rather than a rewrite.

Harder: a misconfigured `TRUTH_TRACKER_CMD` that emits a *valid but wrong*
array is indistinguishable from a healthy one (the seam validates shape,
not provenance); the failure-mode table in the README and the FAULT J
canaries cover absence and malformation, not misdirection. Accepted: the
regime is solo-operator, and the join's output is human-reviewed at
`ready` time.

Field note (2026-07-08/09): the seam survived the trial that motivated
ADR-002 — four tracker verbs used, two canary checks defending the
normalization, and the documented conclusion that the *external* half of
the join "is only as good as the discipline of the agents using it,"
which is the observation the native kernel answers.
