# ADR-009: fsguard edit-region coverage tracked as line ranges

> Status: Accepted — with a CLARIFICATION (2026-07-12)
> Date: 2026-07-11
> Supersedes: —

> **CLARIFICATION (2026-07-12):** the closing line "this closes the edit-region
> coverage sibling" overstates operational reality. `MarkReadRange`/
> `CheckEditable` are built and tested but have ZERO non-test callers, and the
> write path (`CommitWrite`) is freshness-only — it never consults
> `CheckEditable` or the ranges map, so a partial read still authorizes a
> whole-file overwrite (by design: `TestCheckWritable_AfterPartialRead_
> StillFreshnessOnly`). The primitive exists; it protects nothing until an Edit
> tool routes through `CheckEditable`. Read "closes" as "provides the
> primitive," not "enforces coverage on writes." Wiring is tracked separately.

## Context

Under ADR-007, fsguard answers only "was this file observed, and is it still
what was observed?". A partial read therefore over-authorizes: a Read tool with
offset/limit can surface lines 1–20 of a file and the guard will then bless an
edit to line 500, because it tracks *that* the file was read, not *which part*.
The edit's provenance is overstated — the model is rewriting content it never
saw (wk-3c9b615d).

Duplication scan per charter §4 — VERIFIED(grep -rniE
'MarkReadRange|CheckEditable|LineRange|ByteRange' pkg internal): no existing
range/region/offset-coverage code anywhere in the tree; this extends fsguard
rather than duplicating a sibling. VERIFIED(grep -rn 'Snapshot' pkg internal):
no code outside fsguard constructs a `Snapshot` literal, so the type can grow a
field additively.

Options considered:
1. **Byte ranges.** Simpler to verify mechanically against the observed
   content (`end <= len(content)`), and insensitive to line-ending questions.
   Rejected: neither side of the seam speaks bytes — a partial Read is
   expressed as a line offset/limit and an Edit targets a line span, so every
   caller would convert lines→bytes at the boundary, and each conversion is a
   fresh off-by-one opportunity in exactly the code the guard exists to check.
2. **Line ranges.** Matches the Read offset/limit surface and how edits are
   addressed; chosen. The accepted cost: the recorded ranges are
   caller-asserted (the guard does not count lines in `content` to validate
   them) — but that is the same trust already extended to `content` itself in
   `MarkRead`, and any lie is bounded by the freshness hash: it dies as soon as
   the file changes.
3. **Change `CheckWritable`/`MarkRead` to be range-aware.** Rejected: it would
   break the shipped contract (tr-00eded8e consumers) for no gain; coverage is
   meaningful only for callers that perform region edits.

## Decision

We will extend `pkg/tools/fsguard` (no new component) with optional, additive
line-range coverage: `MarkReadRange(path, content, ranges ...LineRange)`
records which 1-based line ranges of the observed content were surfaced, and
`CheckEditable(path, span LineRange)` passes only if the span lies within the
union of observed ranges — *after* the same freshness (hash) check as
`CheckWritable`, which itself keeps its whole-file-overwrite meaning
unchanged. Observed ranges union with overlap/adjacency merging; a full
observation (`MarkRead`, `MarkWritten`, `CommitWrite`) covers every span; a
content-hash change discards ranges recorded against the old body. An
out-of-coverage edit fails with the static, path-and-span-free sentinel
`ErrRegionNotRead` (same injection-channel rule as ADR-007's sentinels).

Snapshot back-compat: `Snapshot` gains `Ranges map[string][]LineRange`
(`json:"ranges,omitempty"`), keyed like `Reads`. A path present in `Reads` but
absent from `Ranges` means "fully observed" — which is exactly what a pre-009
snapshot asserts — so old snapshots restore with their original meaning and
fully-read files keep the old wire shape. Covered by a legacy-JSON restore
test.

## Consequences

- Easier: a Read tool that surfaces a slice of a file can now grant edit
  rights scoped to that slice; provenance is no longer file-granular. The
  change is purely additive — every pre-existing test passes unmodified, and
  no caller changes are required — VERIFIED(go test -race -cover
  ./pkg/tools/fsguard: ok, 55 tests, 97.7% coverage).
- Harder / ruled out: `CheckWritable` (and therefore `CommitWrite`) remains
  freshness-only, so a partial read still authorizes a *whole-file* overwrite —
  region enforcement binds only callers that ask the region question via
  `CheckEditable`; wiring it into the `pkg/tools/file` Edit path is follow-up
  work, not part of this decision. Line identity is anchored to the observed
  content hash, not tracked across rewrites: after any change, coverage resets
  and the region must be re-read (deliberate — remapping lines across edits
  would need a diff engine for marginal benefit). Ranges are caller-asserted,
  not verified against the content's line count (trade-off accepted in option
  2 above).
- Lifespan: permanent, same as ADR-007; this closes the "edit-region
  coverage" sibling that ADR-007 anticipated.
