# ADR-036: the tombstone citation gate

Status: Accepted (2026-07-31, operator) — R2 of the 2026-07 gates
adoption (provenance: docs/reviews/gates-2026-07/, proposal 07's
tombstone record; the confirmed-critical pathspec finding of the
structured review redesigned the I/O boundary here). Implemented in
CLI v0.9.22, schema `$id` v0.13. Canary FAULT TG (11 arms).
Date: 2026-07-31
Amends: — . Extends: ADR-011 (the ceremony gains a corpus check; the
refusal keeps ADR-011's surface rule — the bypass lives in `--help`
and the README, never in the error path), ADR-034 (SI-1/SI-2/SI-4
applied to their first git-consuming gate), ADR-033 (orphan-ok
counted, CC-2). Cites: ADR-026 (`$id` v0.13 — verdict and
issue_event shapes changed), ADR-012 (only the terminal verb earns
the terminal check — `diverge` is recoverable and uncovered).
Supersedes: —

## Context

The machinery filing-hygiene rule was prose: *before a retraction,
grep the corpus for the id; a retracted id cited by any spec blocks
every spec commit via the health gate; swap citations to the
successor FIRST, then retract.* Retract-first lands the cost later,
on someone else's spec commit — the defining shape of a norm that
wants to be syntax. The volume is batch-shaped, not rare: the pilot
holds 66 retracted verdicts (`tr-efc43840`), the meta-repo 49 at its
review anchor with 22 in one day (`tr-d0759df4`), and 12 of the
meta's 49 were cited in tracked markdown at review time — mostly
historical record, the class a consumer-declared scope exempts
(`tr-f0c94c6c`; that measurement also caught a live stale citation
in the operations guide, fixed in R0).

The naive mechanism was falsified before implementation (the
adoption review's one CONFIRMED-critical finding): handing scope
globs to `git grep` as pathspecs lets one gitignore-idiom line
(`:!…`, `:(exclude)…`) silently invert the sweep, a typo'd glob
reads rc=1 — byte-identical to "clean" — and a subtree cwd truncates
the whole search. The shipped design exists because that review ran.

## Decision

**Sweep.** `verdict <id> retracted` and `done --cancel`, after the
ADR-011 ceremony passes and before the append: the shell runs
`git grep -z -l -F -- <id>` **bare** — no pathspecs, `-z` for raw
NUL-separated names (quotepath octal-quoting would otherwise hide a
non-ASCII citing file, failing the gate open — TG11), `--` pinning
the id to the pattern slot — at
`cwd=repo_root()` (SI-2), with the rc contract pinned in code and
here: 0 = hits, 1 = clean, anything else or spawn failure =
unavailable → **refuse with the reason** (fail CLOSED — the one
earned exception to fail-open-loud: the verb is terminal and the
human is already mid-ceremony; a basis costs a sentence). The core
filters hits through `match_paths(scope_globs)` (SI-1: one glob
grammar) and excludes `.truth/claims.jsonl` structurally —
retraction bases legitimately cite predecessors and successors, so
an unexcluded ledger would make every second retraction
self-blocking (TG9).

**Refusal.** Citations found → refusal listing every citing file
with the ordered remedy (swap to the successor, then retract), and
**exit code 6** — distinct, so a sweep driver can tell "cited, swap
first" from unknown-id, ack-mismatch, and unavailable, which all
exit 1 (the `impact` 3/4 and `baseline` 5 precedent). The refusal
does not name `--orphan-ok` (ADR-011's surface rule).

**Override.** `--orphan-ok "<sentence>"` proceeds and stores
`orphan_basis` on the verdict (or the cancelled issue_event) —
schema `$id` v0.13; the validate mirror refuses an empty basis and a
basis on any non-tombstone record (cross-field, mirror-only per
ADR-027). Counted in the ADR-033 override report (CC-2). Decay:
declined with reason — a tombstone is terminal; nothing later
re-asks.

**Scope policy** (`.truth/citation-scope`, SI-4): consumer-owned,
one glob per line in the CLI glob grammar. Absent → the built-in
default `docs/specs/**` applies with a one-line notice (the corpus
the template ships health-gate teeth for; calibrated against the
pilot: 28 distinct ids cited in its six specs, intersection with its
66 retracted ids empty — zero day-one false refusals; at home the
meta-repo has no `docs/specs/`, acknowledged — the notice says so
until the operator declares a scope). Committed-empty → consciously
disabled, silent. Read `utf-8-sig`; lines starting `:`, `-`, or `!`
refused at load (SI-1); a non-empty file matching zero tracked files
voices a loud dead-scope notice, never a silent clean sweep. The
template ships NO scope file — absent-with-default is the shipped
state, so no copier `_skip_if_exists` entry is needed until a
consumer commits one (which copier then never touches, as a
non-template file).

**Preflight.** `truth citations <id>…` — read-only, no ceremony,
exit 0 = nothing cited inside the scope / 6 = at least one id is,
per-id listing, `--json`. A batch retraction runs one preflight,
then per-id ceremonial verdicts on the clean set. A multi-id ack is
refused on principle: ADR-011's ack authorizes exactly one typed id.
Noted cost: each verdict invocation still re-parses the ledger —
O(ids × ledger-parse); the preflight amortizes the grep side only.

## Explicit non-goals — residuals owned

No automatic citation rewriting (whether a successor covers a citing
sentence is editorial judgment). No `diverge` coverage. Truncated
ellipsis citations (`tr-3b69f8…`-style) are invisible to the `-F`
grep — the companion hygiene rule is full ids in scope-covered
documents. A TOCTOU window exists between sweep and append
(accepted; the spec-health gate remains the backstop where wired).
"Retractions are all human" stays self-attested via actor fields.

## Consequences

The two-step ritual collapses into one verb that refuses in the
wrong order, batch-shaped, with a driver-usable exit-code contract;
the cost moves from a future spec-committer's afternoon to the
retracting human's present minute — the human who holds the context
and is already in ceremony. `--orphan-ok` frequency in the override
report is the gate's own health metric: a rising count means the
scope file is wrong, not the users.

**Canary faults.** TG1: cited retraction refused (exit 6), file
listed, bypass unnamed. TG2: after the citation swaps to a
successor, the retraction proceeds. TG3: `--orphan-ok` proceeds and
stores the basis. TG4: a citation outside the scope globs does not
block. TG5: git-grep unavailable fails CLOSED (PATH-shim arm). TG6:
preflight lists citing files, marks clean ids, exits 6. TG7: the
sweep still refuses from a subdirectory (SI-2). TG8: dead scope
voices the loud notice and proceeds. TG9: the ledger's own citation
never blocks even under a `.truth/**` scope (structural exclusion).
TG10: a pathspec-magic scope line is refused at load (SI-1). TG11: a
non-ASCII-named citing file still blocks -- `git grep -z` emits raw
unquoted names (SI-2; default quotepath would octal-quote them into
invisibility, failing the gate OPEN -- the R2 adversarial review's
catch), and the refusal listing renders them escaped (SI-3).
