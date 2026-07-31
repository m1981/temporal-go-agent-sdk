# ADR-038: the dirty-watch advisory

Status: Accepted (2026-07-31, operator) — R4 of the 2026-07 gates
adoption (provenance: docs/reviews/gates-2026-07/; the gap was named
by the adoption review's missed-items list, the cheapest norm→syntax
conversion in the backlog). Implemented in CLI v0.9.24 — no schema
change (ADR-026: the `$id` stays v0.14; this release's sync surface
is code, stderr, and docs). Core tests TestDirtyWatch; canary FAULT
DW (7 arms).
Date: 2026-07-31
Amends: — . Extends: ADR-034 (an advisory in the CC-1 block; SI-2
subprocess discipline — NUL/unquoted status at the repo root),
ADR-023/024 (INV-M refuses untracked LITERAL watches but exempts
globs; the untracked-under-glob entry is exactly the residual vector
this advisory lights up). Cites: the machinery authoring-loop rule
("commits the CONTENT first … a claim filed before its watched
content lands restales at birth") — this ADR is that rule at the
terminal.
Supersedes: —

## Context

A claim filed before its watched content is committed stales on the
very commit that lands the content — restale-at-birth, the hazard
the two-commit dance choreographs around in prose. The class is
measured: 29/895 meta-repo and 37/390 pilot invalidations landed
within 30 minutes of their claim's own birth, one pilot claim
restaling three times inside 18 minutes (`tr-5c2bd165`; the metric
upper-bounds the class — it cannot distinguish own-content landings
from fast unrelated commits). The hazard is mechanically visible at
filing time in one `git status` call; nothing surfaced it.

## Decision

Filing a claim carrying `evidence_paths` (both verbs) runs one
`git status --porcelain=v1 -z --untracked-files=all` at
`cwd=repo_root()` (SI-2: `-z` emits NUL-separated UNQUOTED names —
default quotepath would octal-quote a non-ASCII dirty file into
`match_paths`-invisibility; `-uall` expands untracked directories so
the exact file under a glob watch is named). The pure side parses
entries — a rename/copy carries two NUL fields, both matched — and
reports a watched path as dirty **structurally**: any XY status
other than clean (`  `) or ignored (`!!`) counts, which covers the
unmerged states (`UU` et al.) a letter whitelist would miss — dirty
precisely during merge-conflict resolution, the pilot's QB-011
scenario. Untracked (`??`) entries count: INV-M refuses untracked
literal watches, but a glob legitimately watches an empty-for-now
namespace, and an untracked file under it is the restale-at-birth
vector itself.

Each dirty watched path voices one line in the CC-1 advisory block
(`dirty watch: <path> … commit the content first, then file`),
mirrored under `--json`. **Never a refusal**: filing ahead of the
content commit is legitimate when the author intends an immediate
re-verify (the dance's step 2), and a gate here would teach
`git stash` as its bypass. When git cannot answer, the advisory
stays silent — it advises, it never gates.

## Explicit non-goals

No refusal; no override flag (nothing is refused, so nothing needs
excusing); no whole-repository dirtiness report — only the claim's
own watched paths are the claim's business (DW3 pins the silence).

## Consequences

The restale-at-birth class becomes visible at the only moment it is
cheap — before the append — and the authoring-loop rule stops
depending on a fresh session having read the machinery doc.
Measurable: birth-adjacent invalidations (the `tr-5c2bd165` metric)
should fall toward the unrelated-fast-commit floor.

**Canary faults.** DW1: a modified watched path earns the advisory.
DW2 (negative control): a clean tree files silently, append
asserted. DW3: dirtiness outside the watch stays silent. DW4: an
untracked file under a glob watch fires, named exactly (`-uall`).
DW6: an uncommitted `git mv` fires via the rename entry's two-field
parse (the OLD name is INV-M-dead post-mv, correctly refused — the
arm watches the new name). DW7: a non-ASCII-named dirty watch still
fires (`-z`; quotepath cannot hide it). DW8: the `UU` both-modified
conflict state fires (structural dirtiness).
