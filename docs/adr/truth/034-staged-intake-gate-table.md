# ADR-034: the gate system — staged intake table, CC-1 advisory block

Status: Accepted (2026-07-31, operator) — R0 of the 2026-07 gates
adoption (provenance chain: docs/reviews/gates-2026-07/, plan of
record 06, proposal 07). Implemented in CLI v0.9.20. Core tests
TestAdvisoryAssembler + the updated TestEvidenceExitWarning; canary
FAULT GS (5 arms incl. negative control).
Date: 2026-07-31
Amends: — . Extends: ADR-029 (the execution-boundary presentation is
preserved by construction — the screen and the double-run are stage
boundaries, never table rows), ADR-032/033 (their notices ride the new
block unchanged in substance). Cites: ADR-009, ADR-026 (no schema
change here, so no `$id` bump — the record shape is untouched).
Supersedes: —

## Context

Five gate ADRs were adopted at once (the 2026-07 review chain), each
adding an intake refusal or advisory. Individually each would have
negotiated its pipeline position in prose ("after X, before Y") — the
pattern under which cross-cutting properties erode one gate at a time.
The adversarially verified findings of that review chain are mostly
*system* properties no single gate can own: advisories rode the exact
stderr channel a `tail -1` capture already swallowed once (the pilot's
QB-011 incident); "at most one advisory block" was unenforceable while
each notice printed itself; ESC bytes survive INV-M (which refuses
only whitespace), so raw interpolation of claim-derived text into
notices permits terminal-escape injection; and `.truth/accept-allow`
sat on the wrong side of the ADR-022 copier-ownership asymmetry from
v0.7.0 (deployment-edited, template-clobberable — tr-f49a00ee).

## Decision

1. **Order is data.** Intake gates are rows of `INTAKE_GATES` —
   `(stage, name, gate_fn)`; `gate_fn(ctx)` returns a refusal string
   (the shell `sys.exit`s it) or None, and may stash derived values in
   the shared ctx. Stages: `pre-execution` (text/path/policy checks) →
   the **execution boundary** — the ADR-009 evidence screen, then the
   G6 determinism double-run, DELIBERATELY NOT ROWS (ADR-029
   Decision 1: the screen is a gate on execution, not a peer refusal
   in a flat list; FAULT SD keeps pinning that contrast) →
   `post-execution` (gates reading the captured evidence; rows land
   there from ADR-035 on). A later gate ADR adds a row, not a
   paragraph; a core test pins the row sequence, FAULT GS1/GS2 pin
   the staged order end-to-end.
2. **One advisory block (CC-1).** Post-append notices — the v0.9.11
   hollow-VERIFIED exit warning, the ADR-032 default-expiry notice,
   the FS-1 half-life note (moved post-append) — fold into one
   contiguous stderr block, every line prefixed `truth: advisory:`.
   Silence on clean. Exempt with reason: the commit-gate banner,
   which must fire at dispatch even on refused filings
   (fail-open-with-noise is its documented property). Under `--json`
   the echoed record carries the messages as an `advisories` array;
   the ledger line never stores them (the echo is presentation, the
   record is the contract).
3. **Escaped rendering (SI-3).** Every advisory renders through a
   control-byte escape (`_escape_ctrl`), so claim-derived substrings
   cannot inject terminal escapes or spoof injection-asserted canary
   strings.
4. **Housekeeping riding the same seam:** `truth stats` folds once
   and shares the result across its consumers (each used to re-fold
   and re-sort the whole event list); `_glob_rx` is lru_cached (pure;
   also speeds the invalidate-scan and impact paths); `.truth/
   accept-allow` joins copier `_skip_if_exists` (consumer policy,
   like evidence-allow — the ADR-022 asymmetry now states it).

## Structural invariants (SI-1..SI-4) — normative for every later gate

- **SI-1, one glob grammar:** no git verb ever receives a CLI-owned
  glob (evidence paths or any policy-file glob) as a pathspec; git
  runs bare and the core filters through `match_paths()` (git's `*`
  crosses `/`; the CLI's deliberately does not — the v0.4 lesson).
  Policy loaders refuse lines starting with `:`, `-`, or `!`.
- **SI-2, subprocess discipline:** gate subprocesses run with
  `cwd=repo_root()`; name-emitting git verbs use NUL/unquoted forms
  (`--porcelain=v1 -z`, `--name-only -z --no-renames` or
  `-c core.quotepath=off`); exit codes are pinned per verb in the
  adopting ADR's text.
- **SI-3, advisories are a contract:** the prefix, the `--json`
  mirror, and escaped rendering, as decided above.
- **SI-4, policy-file semantics:** new `.truth/` policy files are
  consumer-owned (`_skip_if_exists`), read as `utf-8-sig`, and
  distinguish committed-empty (consciously configured — silent) from
  absent (built-in default + one-line notice); a non-empty list
  matching zero tracked files earns a loud dead-scope notice.

SI-1/SI-2/SI-4 bind gates that do not exist yet; their canary arms
arm with their first consumer (ADR-035 on) rather than as vacuous
no-op tests here. SI-3 is armed now (GS3–GS5 + the escape unit test).

## Consequences

Refusal behavior is byte-identical to v0.9.19 (proved by the R0
adversarial review's twin-sandbox parity run); the stderr shape
changed (one prefixed block), `--json` gained the advisories mirror,
and one advisory was deliberately ADDED: `done --claim --ttl-days`
now earns the FS-1 note it never printed, because claim-at-death
shares `intake_advisories` — identical intake, identical advice — consumers grepping `truth: warning: evidence command exited`
must switch to the `truth: advisory:` prefix (CHANGELOG v0.9.20
breaking-note). Later gate releases (ADR-035…039 placeholders in the
review chain) each add: a table row, its faults, its override-report
row in the same diff, and — only where the record shape changes — the
ADR-026 `$id` bump. The fatigue budget is now a fold, not a
convention: GS4 (two advisories → one contiguous block) and GS5
(clean filing → zero advisory lines) hold it as a property.

**Canary faults.** GS1: a filing tripping both the G8 duplicate gate
and the evidence screen refuses with the G8 message (pre-execution
precedes the boundary; nothing ran). GS2: the same contrast for the
ADR-007 gate. GS3: `--json` echo carries `advisories[]`; the ledger
line does not. GS4: decay notice + exit warning render as one
contiguous prefixed block. GS5 (negative control): a clean filing
prints zero advisory lines.
