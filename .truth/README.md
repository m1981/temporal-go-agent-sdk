# .truth — append-only claims ledger (v0.9.0)

> Reader: any agent or human about to assert, trust, or re-verify a fact about this repository | Enables: filing a claim in one command, and knowing which claims are still live before acting on them | Update-trigger: the record schema, invariants, or CLI contract change

A plain-JSONL truth layer that lives beside a work tracker (e.g. Beads;
optional — the ledger works standalone, see docs/adr/001). Work records
answer *what to do*; this ledger answers *what is known and how*.

The tracker coupling is an adapter seam (v0.4.1, ADR-004): `truth ready`
consumes a JSON array of issues with `id` (+ `title`) from — in
precedence order (ADR-002) — a pipe (`<tracker-cmd> | truth ready
--stdin`), the environment (`TRUTH_TRACKER_CMD="<cmd printing the
array>"`), the **native work kernel** whenever the ledger holds issue
records (in which case the Beads default is never consulted — pipe or
set the env var to keep an external tracker in the loop), or the default
Beads adapter (`bd ready --json`). No tracker at all? The ledger stands
alone and you degrade from a gate to a dashboard (`truth queue`, `truth
list --live`). A missing or failing tracker exits with guidance, never a
traceback — the three external source paths are canary-gated (FAULT J)
and the native path separately (FAULT R3).

v0.4 hardens the fold for confluence (order-independent under
`merge=union`), enforces human-only retraction, makes re-verification
durable, fixes glob path-matching to respect `/`, and closes a
duplicate-claim-id resurrection path. v0.5.3 closes the analogous
issue-side path (duplicate `wk-` ids are first-wins, ADR-006). v0.5.4/
v0.5.5 harden intake (see Record kinds & fold semantics below). See
docs/adr/001 for the readiness-join semantics.

## Record kinds & fold semantics (the CLI contract)

Six record kinds share one envelope (`id`, `kind`, `actor`, `session`,
`ts`, `payload`): **claim**, **verdict** (`agree` / `diverge` /
`cannot_verify` / `retracted`, always with a `basis`), **invalidation**,
**premise**, and the work kernel's **issue** / **issue_event** (ADR-002).
The formal contract is `.truth/schema/claims.schema.json`; `truth
validate` mirrors it in stdlib and the conformance corpus in
`scripts/test-truth-core.py` keeps the two from drifting.

Status is derived, never stored: a pure fold replays all events in
`(ts, id)` order — a total order independent of file position, so
union-merged branches derive identical status (confluence). The fold
sorts the raw `ts` string, so `ts` must be the canonical profile
`YYYY-MM-DDTHH:MM:SS.ssssss+00:00` — fixed-width UTC microseconds,
exactly what the CLI mints; any other offset, `Z` suffix, or precision
fails `validate` (ADR-015: string order must equal time order). The fold
reads **no clock**: even TTL expiry is not folded from wall-time — the
`invalidate-scan` (the sole clock reader) counts elapsed time from the
claim's own `ts` and, when *strictly more than* `ttl_days` have passed
(`now - ts > ttl_days`; the exact boundary has not yet expired), appends
an **invalidation record**; only that record demotes the claim to
`stale`. A TTL'd claim the scan has not visited is not stale, however old
(ADR-019 — this is what keeps the fold pure and confluent). Duplicate
claim and issue ids are first-wins (F6, ADR-006): a later append bearing
an existing id is inert. Status is ONE total function (ADR-020): each
verdict/invalidation sets it last-writer-wins in `(ts, id, canon)` order
(`agree→live`, `diverge→diverged`, `cannot_verify→cannot_verify`,
`invalidation→stale`, `retracted→retracted`), EXCEPT `retracted` is
absorbing — once folded to `retracted`, later setters are ignored (tested
on the folded status, not `ts`). So `diverged`, `cannot_verify`, and
`stale` are RECOVERABLE (a later `agree` returns them to `live`), while
`retracted` (claims) and `cancelled` (issues) are terminal and
human-gated (ADR-011; full requirement under v0.6 solo-regime hardening
below); `closed` is not terminal (work is cyclical). Because two verdicts
carry distinct ids and the order is total, verdict ordering is confluent
— backdating a verdict only lowers its key (it cannot resurrect a claim a
later honest `agree` couldn't) and trips an ADR-008 warning; not a
C1-style hole (H3, ADR-020). An `agree` verdict on a path-anchored claim
advances its effective anchor, so re-verified claims stay live across scans.

Intake gates, in refusal order: empty claim text (v0.5.5); near-duplicate
of an active claim (Jaccard token overlap ≥ 0.6; `--duplicate-ok`
overrides) — ADR-018 pins the conformance surface: metric is Jaccard
`|A∩B|/|A∪B|` (not the overlap coefficient), tokens are the *set* of
maximal `[a-z0-9]+` runs of the lowercased text, and "active" is exactly
the `{live, unverified}` statuses (the other five — `stale`, `diverged`,
`cannot_verify`, `retracted`, `disputed` — are dead-for-intake, so a
correcting refile against them is always allowed);
quantifier–scope mismatch (ADR-007, v0.6) — a universally quantified
claim text ("only", "no … anywhere", "the repo") over a scoped evidence
command (`--include`, path arguments, `cd`) is refused unless
`--scope-ok "<one sentence>"` states why the scope covers the
quantifier (stored as `scope_basis`, attackable by verifiers);
statically dead-tripwire paths — a whitespace-containing entry with no
comma, a **literal** path matching zero tracked files, or a **glob** over
a statically-unreachable namespace (INV-M, v0.5.4; ADR-024). A glob over a
*reachable* namespace is exempt because it is *dormant, not dead* — it
fires when the namespace fills (ADR-023) — but a glob that is absolute,
ends in `/`, has a `.`/`..`/empty component, or starts with `.git/` can
never match a repo-relative diff path and is refused (`.git*` and
`.github/**` are reachable and still pass). The one residual that is *not*
statically decidable is a tracked **symlink** literal, which git tracks as
an immutable link, so editing its target never fires — watch real,
reachable paths; applies to every evidence class carrying paths); then, for
VERIFIED: missing evidence command, neither paths nor TTL, no commit to
anchor to, the evidence-command safety screen (ADR-009, v0.6 — quote-aware: every
pipeline segment's program must be a bare name in
`.truth/evidence-allow`; no command substitution; no ASCII control
character except tab — a newline is word-whitespace to the screen's
`shlex` lexer but a statement separator to the executing `/bin/sh`, so
the screen must tokenize like its executor or a hidden second command
slips through into a verifier's recheck (ADR-021, H4); output redirection
only to `/dev/null` or an fd dup (`2>&1`), so the pin-the-output
convention keeps working; an allowlisted program's own write/exec flags
are refused by a per-program deny table — `find -exec/-execdir/-ok/-okdir/-delete/-fprint*/-fls`,
`sort -o/--output/--compress-program`, and a few top-level `git` flags —
but that table is a BLOCKLIST and cannot bound an interpreter or VCS, so
`git`, `sed`, `awk`, and test runners are absent from the shipped
allowlist by design and must not be added for evidence use (ADR-021).
Two guardrails catch an accidental one anyway (ADR-022): a TEMPLATE-owned
`.truth/evidence-deny` baseline hard-refuses shells and generic executors
(`sh`, `bash`, `env`, `xargs`, …) even if you allowlist one — deny-wins,
evidence screen only (an acceptance oracle may still run `bash`) — and
`truth doctor` WARNS (non-blocking) when your allowlist holds a grey-zone
program (`git`, `python`, `curl`, …) that can execute code. You own
`.truth/evidence-allow`; the template owns `.truth/evidence-deny` and a
`copier update` keeps it current;
`--evidence-unsafe-ok` files a *screen failure* anyway with
`evidence.screened=false`, and recheck then refuses to execute the
command, ever — verification becomes manual; but a **missing** allowlist
fails closed *even under* the override (a repo with no `evidence-allow`
cannot file a VERIFIED evidence command at all — the F1 fail-closed
lesson), so the override covers a screened-out program, not the absence
of a policy to screen against), and a nondeterministic evidence command
(two intake runs must
hash identically; `--single-run` overrides). INFERRED requires `--basis`.

## v0.6 solo-regime hardening (docs/hardening-proposals-solo-regime.md)

Beyond the two intake gates above: `validate` (and therefore the commit
gate) fails on a backdated duplicate-id append — the canonical-order
substitution the fold's first-wins dedup composed with timestamp forgery
(ADR-008) — and warns on clock regression beyond 300s; identical
duplicated lines (git union-merge shape) still pass. `verdict <id>
agree` from the claim's own session is refused (ADR-010; self-diverge
and self-cannot_verify stay allowed — they run against interest;
`TRUTH_SELF_VERDICT=1` is the human override, self-attested like
TRUTH_HUMAN). Tombstones (claim retraction, issue cancel) now require
TRUTH_HUMAN=1 **plus** either an interactive typed-id confirmation at a
real terminal or, for headless human use, `TRUTH_HUMAN_ACK=<exact-id>` —
an acknowledgment that must name the specific record it kills, so a
lingering export cannot authorize arbitrary tombstones (ADR-011).
`verdict <id> diverge --mechanical` records that the measuring recipe
changed rather than the fact (ADR-012; status unchanged, queue and
stats display it). `truth stats [--json] [--since ts]` reports status/
tier counts, verdict rates split by subtype, per-tier claim half-life
(live→stale), and queue aging — the mechanical half of the monthly
audit; once ≥5 half-life observations exist for a tier, filing a
TTL'd claim prints the observed median beside the author's choice
(suggestion only). `doctor` additionally checks the evidence allowlist
exists and warns when load+fold exceeds 200ms (the FS-3 scale gate —
the snapshot cache is deliberately unbuilt until that warning fires).

## Layout

    .truth/claims.jsonl                the ledger (append-only, event-sourced)
    .truth/schema/claims.schema.json   the formal contract (survives fires)
    .truth/evidence-allow              ADR-009 allowlist: which programs may
                                       re-run inside verifier sessions
                                       (consumer policy; updates never revert it)
    scripts/truth                      the CLI: pure core over imperative shell
    scripts/test-truth-core.py         unit + schema-conformance tests (ms),
                                       incl. the FS-2 constraint-enumerated
                                       mutant corpus: generated near-valid
                                       records on which the stdlib mirror and
                                       the JSON Schema must agree, closing
                                       the F1/F8 drift class
    scripts/test-truth-v04.py          v0.4 regression tests (confluence, anchors, globs)
    scripts/check-truth.sh             pre-commit/CI gate: strict append-only + schema
    scripts/truth-canary.sh            seeded-fault suite (run weekly; it
                                       prints its own count — all CAUGHT, or stop)
    prompts/truth-verifier.md          fixed verifier prompt (use `truth dispatch`)
    docs/adr/                          decision records: 001 premise validity,
                                       002 work kernel, 003 satellite placement,
                                       004 tracker seam, 005 pre-edit whisper
                                       (accepted in trial), 006 issue-fold
                                       first-wins, and the v0.6 solo-regime
                                       hardening set: 007 quantifier-scope
                                       gate, 008 order coherence, 009
                                       evidence-command screen, 010 session
                                       separation, 011 tombstones-need-a-
                                       terminal, 012 divergence subtype,
                                       013 premise supersede (v0.6.4)

## Install (day 1)

1. `.gitattributes` already sets `.truth/claims.jsonl merge=union`.
2. Run `bash scripts/install-hooks.sh` after every `git init`/`git clone`
   (local hooks do not survive clones), or use CI instead — one of the
   two MUST exist. This is the *commit gate* (`check-truth`); without it
   INV-A/INV-B/INV-G/INV-N and the ADR-008 order detections do not run and
   the ledger's append-only guarantee is unenforced. For CI, name the gate
   scripts (`check-truth`, `invalidate-scan`) in a workflow `doctor` greps
   (`.github/workflows/*`, `.gitlab-ci.yml`, `.circleci/config.yml`,
   `Jenkinsfile`, …) so the installation stays decidable.
3. `AGENTS.md` already carries the discovery snippet — copy it into
   `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, etc.
   too (those are the exact paths `truth doctor` checks).
4. `pip install jsonschema` — required so the drift detector runs armed.
5. `scripts/truth doctor` — installation must pass. It exits 1 (fails)
   unless, for each gate, an active hook OR a CI config naming the gate
   script exists; the CI arm is self-certified (doctor greps for the name,
   it cannot run your pipeline). A clean exit 0 is the decidable proof the
   MUST in step 2 holds (ADR-025).
6. `bash scripts/truth-canary.sh` — every fault CAUGHT, or stop.

## Work kernel (ADR-002, v0.5)

Issues can live in the same ledger as facts — no external tracker needed:

    scripts/truth issue "title" --premise tr-xxxx   # premise-at-birth
    scripts/truth start wk-xxxx                     # claim it (files 'claimed')
    scripts/truth start wk-xxxx --release           # give it back: claimed -> open
    scripts/truth done wk-xxxx --basis "..." \
      --claim "<what the work made true>" --class VERIFIED \
      --evidence-cmd "..." --paths "..."            # claim-at-death
    scripts/truth ready                             # open ∧ deps closed ∧ premises valid
    scripts/truth issues                            # full board with derived status
    scripts/truth premise wk-xxxx tr-new \
      --supersedes tr-old                           # redirect a DEAD premise to its
                                                    # corrected claim (ADR-013) — refused
                                                    # while the old one still passes ready

Issue states form `open ⇄ claimed → closed`: `start` files `claimed`,
`start --release` returns a claimed item to `open` (valid only from
`claimed`, basis optional, not human-gated), `closed` can be reopened
(`done --reopen`); `cancelled` is terminal and
human-gated per ADR-011 — at your own terminal,
`TRUTH_HUMAN=1 truth done wk-x --cancel --basis "..."` then type the id
back when prompted; headless,
`TRUTH_HUMAN=1 TRUTH_HUMAN_ACK=wk-x truth done wk-x --cancel --basis "..."`.
External trackers still work through the seam (`TRUTH_TRACKER_CMD`,
`--stdin`); `truth issues --ready-json` emits the same contract, so you
can run both and diff. Full semantics: `docs/adr/002-native-work-kernel.md`.

**Acceptance oracles (ADR-014, v0.7).** `issue --accept-cmd "<cmd>"
[--accept-kind verification|validation]` declares an executable finish
line at birth (default kind `verification` = suite/gate, "built right";
`validation` = golden-diff, "built the right thing" — 12207's two V's).
A plain `done` then runs the command from the repo root and refuses the
close on non-zero exit; the close event records `accept: {executed,
returncode}`, and validate rejects an executed acceptance with a
non-zero returncode. Oracles execute repository code by purpose, so they
are screened (ADR-009's screen, reused) against their **own** committed
allowlist, `.truth/accept-allow` — never `evidence-allow`, which stays
read-only. Missing list fails closed; the template ships it empty
(header explains the policy trade). `--accept-unsafe-ok` files an
unscreenable oracle with `screened: false` (done then refuses to execute
it), and at `done` closes without running an oracle that *cannot* run,
stamped `executed: false` — it never overrides an oracle that ran and
failed. `--cancel`/`--reopen` skip the oracle. Canary FAULTS AC1–AC7.

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

## Pre-edit whisper (ADR-005, v0.5.7 — verb template-side, hook consumer-side)

    scripts/truth impact <path>...      # what knowledge does editing endanger?

Read-only fold query: for each repo-root-relative path, the
live/unverified claims watching it (the same matcher `invalidate-scan`
uses — one matcher, by decree) and the open work premised on them. Exit
0 = silence (nothing watched; the fatigue budget is a canary-gated
property, FAULT W2), exit 3 = report on stdout, `--json` for harnesses.
Output is prediction, never judgment: the verb files nothing — appends
remain the scan's and the verifiers' job. The whisper HOOK (PreToolUse
in an agent harness; a deny list for frozen paths; per-session dedup) is
consumer policy and deliberately not shipped (ADR-003 rule 2) — wire it
per ADR-005's Decision, and watch its adoption gate: whispers that
change agent behavior, without fatigue.

**Contradictions (issue #4, v0.9.0 — 29148 set consistency, rule R5).**

    scripts/truth contradicts <tr-a> <tr-b> --basis "<why not both>"

A DECLARED edge, mirroring premise — no NLP: the moment a gate needs a
model to fire, it is a review, not a refusal. While an edge connects
two claims whose statuses would otherwise both be live, BOTH derive
**DISPUTED** — which behaves like diverged everywhere: premised work
HOLDs, spec-health fails citers, both sides queue naming their
counterpart. Any other endpoint state leaves the edge dormant. There is
no arbitration verb: retract, supersede, or re-file one side and the
edge stops firing. Intake refuses self-edges, unknown or retracted
endpoints, and duplicate edges in either direction; note that a claim
CONTRADICTING an existing one is usually also its near-duplicate, so
filing the second side legitimately takes `--duplicate-ok` — that is
the flag's honest use, not a bypass. Canary FAULTS C1–C5.

**Baselines (issue #3, v0.8.0 — ISO 10007 set-level status accounting).**

    scripts/truth baseline <ref> [--json]      # the frozen status account
    scripts/truth baseline <a> --diff <b>      # release-notes delta

`baseline <ref>` folds the ledger as it stood at any git ref (tag, sha,
HEAD) into a deterministic snapshot — claims by status/tier, issues by
state, sorted id lists; `--json` redirected to a file and committed IS
the persisted baseline artifact (the CLI deliberately persists
nothing). `--diff` folds two refs and prints born records, status
transitions grouped `from->to`, and **DISAPPEARED** records — a record
present at the older ref and absent at the newer is impossible between
ancestor and descendant of an append-only file, so it means rewritten
or divergent history: 10007's omission, caught by exactly the
comparison the standard prescribes, exit 5 (gateable). Exit 2 =
unreadable ref. Canary FAULTS BL1–BL4.

**The backward slice (issue #5, v0.7.1).**

    scripts/truth impact --inverse [--under DIR] [--exclude PREFIX]...

flips the question: which tracked files does NO active claim watch? —
the 24765 backward trace a curation-only ledger cannot otherwise ask.
Joins `git ls-files` against the evidence-path globs of every
non-retracted claim (stale/diverged still watch — that is knowledge
needing re-check, not absence; only retraction kills a watch), same
matcher by the same decree. Exit 0 = scope fully watched, 4 = dark
files listed on stdout (distinct from forward's 3, so satellites gate
each separately), 2 = the scope matched nothing (a typo'd `--under`
must refuse, never read as a clean audit). Expect noise on a first run
(lockfiles, assets): `--exclude` is the pressure valve; module
inventories and dark-file triage (adopt/attic/delete) are downstream
satellites' work, not this verb's. Canary FAULTS W5–W8.

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
  Note the ADR-009 screen: `bash` is not in the shipped
  `.truth/evidence-allow`, so this exact command is refused at intake
  until you either add `bash` there (a conscious, committed policy
  choice — it runs repository code) or file with `--evidence-unsafe-ok`
  (recheck then never executes the command; verification is manual).
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
