# .truth — append-only claims ledger (v0.5.2)

> Reader: any agent or human about to assert, trust, or re-verify a fact about this repository | Enables: filing a claim in one command, and knowing which claims are still live before acting on them | Update-trigger: the record schema, invariants, or CLI contract change

A plain-JSONL truth layer that lives beside a work tracker (e.g. Beads;
optional — the ledger works standalone, see docs/adr/001). Work records
answer *what to do*; this ledger answers *what is known and how*.

The tracker coupling is an adapter seam (v0.4.1): `truth ready` consumes
a JSON array of issues with `id` (+ `title`) from — in precedence order —
a pipe (`<tracker-cmd> | truth ready --stdin`), the environment
(`TRUTH_TRACKER_CMD="<cmd printing the array>"`), or the default Beads
adapter (`bd ready --json`). No tracker? The ledger stands alone and you
degrade from a gate to a dashboard (`truth queue`, `truth list --live`).
A missing or failing tracker exits with guidance, never a traceback —
all three source paths are canary-gated (FAULT J).

v0.4 hardens the fold for confluence (order-independent under
`merge=union`), enforces human-only retraction, makes re-verification
durable, fixes glob path-matching to respect `/`, and closes a
duplicate-claim-id resurrection path. See docs/adr/001 for the
readiness-join semantics.

## Layout

    .truth/claims.jsonl                the ledger (append-only, event-sourced)
    .truth/schema/claims.schema.json   the formal contract (survives fires)
    scripts/truth                      the CLI: pure core over imperative shell
    scripts/test-truth-core.py         unit + schema-conformance tests (ms)
    scripts/test-truth-v04.py          v0.4 regression tests (confluence, anchors, globs)
    scripts/check-truth.sh             pre-commit/CI gate: strict append-only + schema
    scripts/truth-canary.sh            19 seeded faults (run weekly)
    prompts/truth-verifier.md          fixed verifier prompt (use `truth dispatch`)
    docs/adr/                          decision records: 001 premise validity,
                                       002 work kernel, 003 satellite placement,
                                       004 tracker seam, 005 pre-edit whisper (proposed)

## Install (day 1)

1. `.gitattributes` already sets `.truth/claims.jsonl merge=union`.
2. Hooks are wired in `.git/hooks/` after `git init`/`git clone` — see
   `scripts/install-hooks.sh`, or use CI instead (one of the two MUST exist).
3. `AGENTS.md` already carries the discovery snippet — copy it into
   `CLAUDE.md`, `.cursorrules`, `copilot-instructions.md`, etc. too.
4. `pip install jsonschema` — required so the drift detector runs armed.
5. `scripts/truth doctor` — installation must pass.
6. `bash scripts/truth-canary.sh` — every fault CAUGHT, or stop.

## Work kernel (ADR-002, v0.5)

Issues can live in the same ledger as facts — no external tracker needed:

    scripts/truth issue "title" --premise tr-xxxx   # premise-at-birth
    scripts/truth start wk-xxxx                     # claim it
    scripts/truth done wk-xxxx --basis "..." \
      --claim "<what the work made true>" --class VERIFIED \
      --evidence-cmd "..." --paths "..."            # claim-at-death
    scripts/truth ready                             # open ∧ deps closed ∧ premises valid
    scripts/truth issues                            # full board with derived status

`closed` can be reopened (`done --reopen`); `cancelled` is terminal and
human-gated (`TRUTH_HUMAN=1 truth done wk-x --cancel --basis "..."`).
External trackers still work through the seam (`TRUTH_TRACKER_CMD`,
`--stdin`); `truth issues --ready-json` emits the same contract, so you
can run both and diff. Full semantics: `docs/adr/002-native-work-kernel.md`.

## Feature specs (optional satellite, v0.5.1)

Prose documents rot because they restate facts; the fix is one rule: **a
fact appears in a spec only as a ledger id** (`tr-`/`wk-`), one line of
courtesy hook text beside it — the id is authoritative, the hook is not.
Keep specs in `<component>/docs/specs/*.md`: decisions link to ADRs,
current facts cite `tr-` claims, intended work cites `wk-` issues, and an
Acceptance section pre-writes the `done --claim` texts (commit the work
first, then `done --claim` — a completion claim filed before its shipping
commit trips its own path tripwire).

    bash scripts/spec-health.sh

sweeps every spec and judges each cited id by the ADR-001 matrix
(stale/diverged/retracted/missing/cancelled fail; `cannot_verify` fails
only P0; unverified warns). It also warns when a spec's ground truth is
not a premise of any cited issue — then `truth ready` can't protect it.
Zero-id specs warn as unwired legacy. Wire it into your pre-commit gate
for staged spec changes if your repo has one; canary FAULT S1–S3 cover
the semantics. Projects usually grow a fuller convention doc referenced
from their agent guide (AGENTS.md). Route every new spec from an entry
point (component README or agent guide) — spec-health judges the facts a
spec cites, not whether anyone is ever directed to read it.

## Doc health (optional satellite, v0.5.2)

spec-health protects cited facts; the prose fabric around them rots too.
The two decay modes measured in the field: renamed things living on in
docs, and relative links whose targets moved.

    bash scripts/doc-health.sh

sweeps git-tracked markdown (history exempt: archive/, archived/, attic/,
adr/, freeze/ segments and CHANGELOGs) and fails on broken relative links
and on any regex listed in the optional `scripts/doc-health.patterns`
(one per line — put your project's dead names there; no file, no name
check). Backtick path shorthand is deliberately not checked — endemic and
legitimate; links are the load-bearing references. Cite rename ADRs from
live docs by wildcarding the filename (`docs/adr/NNN-*.md`) so the dead
name never appears. Canary FAULT D1–D3 cover the semantics. Pairs well
with a standing claim whose evidence is the gate itself (see Claim
discipline below).

## Claim discipline (earned lessons)

- **Scope the text to the evidence.** Never write a repo-wide clause
  backed by a package-scoped grep — both genuine diverges in the field
  trial were exactly this gap. If the command searched `src/pkg/`, the
  claim says `src/pkg/`, and names known survivors (tests, attic)
  explicitly.
- **Pin evidence output stable.** When the evidence is a health gate,
  wrap it: `bash scripts/doc-health.sh >/dev/null 2>&1 && echo CLEAN`.
  The raw output embeds counts ("70 live docs") that change with every
  added file, mechanically diverging the hash while the claim stays true.
- **Commit first, then `done --claim`.** A completion claim filed before
  its shipping commit trips its own path tripwire (also noted under
  Feature specs).

## Daily operation

Daily (~2 min): `scripts/truth queue` — empty means carry on.
Weekly (~30 s): `scripts/truth-canary.sh`.
After repo surgery (rebase spree, hook changes, new agent runtime):
`scripts/truth doctor`.
Monthly: re-audit a few fresh sessions' claims by hand against your day-0
baseline — if false-VERIFIED rates haven't moved, the green checkmarks
mean nothing.

## Seeding

Do not bulk-backfill claims. Let them accrete as agents do real work.
At install time, seed only a handful (3-5) of P0 load-bearing facts,
file them properly with real evidence, and dispatch each to a fresh
verifier session so they start `live`. Record a day-0 hand-audit baseline
of recent agent sessions' factual accuracy to compare against later.
