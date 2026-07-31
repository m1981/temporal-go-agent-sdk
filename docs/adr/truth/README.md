# docs/adr/truth — the truth-ledger machinery ADR series

> Reader: anyone citing or extending a truth-ledger decision record | Enables: telling the template's machinery ADRs apart from this repository's own ADR series, and citing them by the right path | Update-trigger: an ADR is added to the machinery series, or the namespacing convention changes

This directory holds the truth-ledger MACHINERY decision records
(001-033 and counting). It is template-owned: `copier update` extends
it, and the number space here belongs to the template alone. Since
v0.9.18 it is namespaced apart from the consumer's own `docs/adr/`
series — born of a real collision in a consumer repo, where the
template's ADR-001 and the project's own ADR-001 (and several more)
landed in one directory, and immutable ledger citations made
renumbering impossible. Number your project's ADRs in plain
`docs/adr/`; cite these as `docs/adr/truth/NNN-*.md`.
