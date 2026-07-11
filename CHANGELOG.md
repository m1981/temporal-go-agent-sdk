# Changelog

All notable changes to temporal-go-agent-sdk are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `fsguard`: optional edit-region coverage (ADR-009) — `MarkReadRange` records
  which 1-based line ranges of a file a partial Read surfaced, and
  `CheckEditable` refuses an edit whose span falls outside the observed union
  with the new `ErrRegionNotRead` sentinel (`ErrInvalidRange` for malformed
  ranges). `Snapshot` gains an optional `Ranges` field; pre-existing snapshots
  and the `MarkRead`/`CheckWritable` whole-file semantics are unchanged.
- Initial scaffold from the project-template Copier template.
