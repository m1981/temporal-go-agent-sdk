# ADR-012: Divergence subtype — paying down the vocabulary debt

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md`, implemented in CLI v0.6.0.
Canary fault M1; conformance fixtures both ways.
Date: 2026-07-11
Supersedes: — (resolves the paper's §8 item 7)

## Context

"Diverged" conflates two facts the pilot already separated by hand in
the paper's §2 table: *reality changed* (the claim is wrong) and *the
measuring recipe changed* (output format drift; the fact still true).
The distinction was unnamed in the status vocabulary, and FS-1's
efficacy metrics are impossible without it — a genuine-divergence rate
diluted by mechanical divergences measures nothing.

## Decision

`truth verdict <id> diverge --mechanical` stores
`"subtype": "mechanical"` in the verdict payload (schema: optional enum
of exactly that value). The fold is **unchanged** — status is still
`diverged`, the claim still queues, because a mechanically diverged
claim still needs a human action: re-file with a stable evidence recipe
(the §9 pin-the-output convention exists to make this rare). `queue`
and `list` display the subtype; `stats` reports
`diverge_genuine` / `diverge_mechanical` separately. The verifier
prompt gained one instruction: if the hash mismatch traces to output
format rather than the claimed fact, add `--mechanical`.

## Explicit non-goals

No new status. Subtype is display-and-measurement metadata; deriving
different *policy* from it (e.g. auto-refiling) would put a judgment in
a mechanical path and needs its own ADR.

## Consequences

Easier: §2-style tables become mechanical queries; TTL calibration
(FS-1 half-life) can exclude mechanical noise; the human queue shows
"needs a better recipe" distinctly from "needs a correction". Harder:
nothing measurable — one optional flag, no fold change, no required
field.
