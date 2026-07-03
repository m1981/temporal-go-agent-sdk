# Architecture Decision Records

> Reader: any agent about to make or change an architectural decision | Enables: finding what was already decided and recording new decisions in a 5-minute act | Update-trigger: a new ADR is added or an existing one is superseded

This folder holds Architecture Decision Records. An empty folder is fine —
its existence is what makes "write an ADR" a small act instead of a project.

## Numbering

- Files are named `NNN-short-kebab-title.md`, zero-padded, starting at `001`.
- `000-template.md` is the template — copy it, don't number real ADRs `000`.
- Numbers are assigned in order and never reused, even if an ADR is rejected.

## Immutability & superseding (charter §5.2)

- An **accepted** ADR is immutable. Do not edit its Context or Decision to
  change the outcome — the pre-commit hook blocks modifications to
  `adr/NNN-*` files for this reason.
- To change a past decision, write a **new** ADR that sets
  `Supersedes: ADR-NNN`, and update the old ADR's Status line to
  `Superseded by ADR-MMM` (this status flip is the one allowed edit;
  commit it with `ADR_AMEND=1 git commit ...` if the hook objects).
- Code and specs reference decisions by number (`ADR-017`), never by title.

## Status values

`Proposed` → `Accepted` → `Superseded by ADR-NNN` (or `Rejected`).
