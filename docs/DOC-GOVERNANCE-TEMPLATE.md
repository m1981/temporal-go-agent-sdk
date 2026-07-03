# DOC-GOVERNANCE TEMPLATE — project-agnostic version

> Reader: any new project's first agent session | Enables: installing
> doc-governance without inheriting another project's specifics |
> Update-trigger: a gate design changes in the source project

Reusable across projects. Everything project-specific lives in ONE config
file. Companion files (they ship alongside this doc in every scaffolded
project): `AGENT-CHARTER.md` + `AGENT-CHARTER-APPENDIX-A.md` — they seed
`AGENTS.md`.

The gate logic is NOT inlined in this document. The scripts are the single
source of truth — read them directly:

| Concern | File |
|---------|------|
| Per-project config (the only file you edit) | `scripts/governance.conf` |
| Layer 1 pre-commit checks | `scripts/check-governance.sh` |
| Pre-commit hook shim | `scripts/pre-commit` |
| Layer 2 LLM doc-gate (optional, manual) | `scripts/llm-doc-gate.sh` |

Earlier versions of this template pasted the script bodies inline here. They
were removed in v1.1.0: markdown mangles shell (smart quotes, wrapped long
lines) and two copies inevitably drift. Cite the files above.

═══════════════════════════════════════════════════════════════════════════
DAY-1 RECIPE FOR A NEW PROJECT (staged — install gates when triggers fire)
═══════════════════════════════════════════════════════════════════════════

Day 1 (repo init):
  - AGENTS.md seeded from the charter's core rules: evidence protocol,
    new-doc three-question gate, new-component ADR gate, review contract,
    diagram labels. (Charter §1, §2, §4, §6 + Appendix A.9 — trimmed to
    one page; a rulebook nobody reads is doc creep.)
  - Every component README starts with the Type header (Appendix A.0.1):
    `> Type: <A–F> | Status: active | Horizon: H1 | Role: <one line>`
    `> Charter: docs/AGENT-CHARTER.md | Profile: Appendix A.<n>`
  - docs/adr/ folder + ADR template. Empty is fine; the folder existing
    is what makes "write an ADR" a 5-minute act instead of a project.

First multi-session work OR first teammate:
  - Install the Layer 1 pre-commit hook (`scripts/pre-commit`) with checks
    2–4 active. Check 1 (dead names) stays dormant until your first rename.

First rename/restructure:
  - Add the old names to DEAD_NAMES in `scripts/governance.conf`. This is
    the moment check 1 earns its existence.

First month of real doc volume:
  - Start running the Layer 2 LLM gate (`scripts/llm-doc-gate.sh`) manually,
    weekly. Wire to pre-push only after two weeks of useful verdicts.

Every freeze / quarter:
  - Trust audit + re-stamp (charter freshness ritual).

═══════════════════════════════════════════════════════════════════════════
CONFIG — the ONLY part you edit per project (`scripts/governance.conf`)
═══════════════════════════════════════════════════════════════════════════

Four variables, documented at their point of definition in the file:

  - `DEAD_NAMES` — regex of retired names (empty until your first rename).
  - `TYPED_READMES` — space-separated README paths that must keep the
    `> Type:` header.
  - `EXEMPT_PATHS` — regex of paths where historical names / headerless docs
    are fine (archives, ADRs, CHANGELOG).
  - `GATE_EXEMPT_NAMES` — filenames exempt from the three-question header
    because their format is governed elsewhere (README, AGENTS, …).

Edit `scripts/governance.conf`; do not copy its contents into other docs.

═══════════════════════════════════════════════════════════════════════════
LAYER 1 — pre-commit (`scripts/check-governance.sh`)
═══════════════════════════════════════════════════════════════════════════

Config-driven; sources `scripts/governance.conf`. Four checks:

  1. Dead names in added lines (skipped while DEAD_NAMES empty).
  2. ADR immutability — an accepted `adr/NNN-*` file may not be modified;
     supersede instead. Conscious amend: `ADR_AMEND=1 git commit …`.
  3. New-doc three-question gate — every new `.md` (outside exempt paths /
     names) needs a `> Reader: … | Enables: … | Update-trigger: …` header.
  4. Typed READMEs keep their `> Type:` header.

Skip individual checks for one commit with `GOVERNANCE_SKIP` (comma list),
e.g. `GOVERNANCE_SKIP=1,3 git commit …`. `ADR_AMEND=1` is the alias for
skipping check 2. A missing/unreadable `governance.conf` exits 2 (distinct
from a governance failure, which exits 1).

Install: `scripts/pre-commit` is a two-line shim that calls
`scripts/check-governance.sh`; copy it to `.git/hooks/pre-commit` (the
Copier `install_hooks` task does this for you).

═══════════════════════════════════════════════════════════════════════════
LAYER 2 — LLM gate (`scripts/llm-doc-gate.sh`, optional, manual)
═══════════════════════════════════════════════════════════════════════════

Portable; rules R1–R5 are generic and encoded in the script's system prompt:
R1 duplicate-doc detection, R2 evidence tags, R3 retired names (reads
DEAD_NAMES from `scripts/governance.conf`), R4 mixed-purpose docs, R5
scattered status claims. The script prepends the conf so the model sees the
current name list. The model-call step is marked TODO — wire it to your LLM
CLI before relying on it. Run manually; pre-push only after it proves useful.

═══════════════════════════════════════════════════════════════════════════
NEW-PROJECT BOOTSTRAP PROMPT (paste to an agent in the fresh repo)
═══════════════════════════════════════════════════════════════════════════

"This is a new repo. Set up doc governance from
docs/DOC-GOVERNANCE-TEMPLATE.md: (1) create AGENTS.md seeded from
AGENT-CHARTER.md §1/§2/§4/§6 + Appendix A.9, trimmed to ~one page;
(2) add the Appendix A.0.1 Type header to README.md; (3) create docs/adr/
with a template and README stating the numbering + supersede-don't-edit
policy; (4) create scripts/governance.conf with DEAD_NAMES empty and the
paths adjusted to this repo; (5) install checks 2–4 via the pre-commit hook
(scripts/pre-commit → .git/hooks/pre-commit); (6) test: try committing a
headerless scratch.md and confirm refusal, then remove it. One commit per
step."
