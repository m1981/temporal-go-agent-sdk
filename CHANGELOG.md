# Changelog

All notable changes to temporal-go-agent-sdk are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- `fsguard` (ADR-010, **breaking** for `Filesystem` implementors): the seam's
  `WriteFile` is replaced by two atomic primitives — `CreateExclusive`
  (O_CREATE|O_EXCL) and `WriteFileAtomic` (write-temp-then-rename).
  `CommitWrite` now refuses a new-file create that raced with an external
  create (new static sentinel `ErrConcurrentCreate`) instead of clobbering
  it, replaces existing files atomically so concurrent readers never see a
  torn write, and re-verifies freshness immediately before the write call. A
  residual TOCTOU window on existing files remains (modification between the
  final re-read and the rename) and is documented in ADR-010.

### Added
- `fsguard`: optional edit-region coverage (ADR-009) — `MarkReadRange` records
  which 1-based line ranges of a file a partial Read surfaced, and
  `CheckEditable` refuses an edit whose span falls outside the observed union
  with the new `ErrRegionNotRead` sentinel (`ErrInvalidRange` for malformed
  ranges). `Snapshot` gains an optional `Ranges` field; pre-existing snapshots
  and the `MarkRead`/`CheckWritable` whole-file semantics are unchanged.
- Initial scaffold from the project-template Copier template.
