# ADR-021: The evidence screen must tokenize like its executor; the arg-deny blocklist cannot bound interpreters (H4)

Status: Accepted (2026-07-18, operator) — source: independent review
finding H4 (High), whose spec-precision framing concealed a live
security bypass confirmed in a sandbox and by an independent adversarial
review. Amends ADR-009. Implemented in CLI v0.9.6. Canary FAULT ES;
core tests test_screen_rejects_control_chars, test_arg_deny_covers_h4_gaps.
Date: 2026-07-18
Supersedes: — (hardens ADR-009's evidence screen; the allowlist model is
unchanged)

## Context

ADR-009 screens an evidence command before it is stored, because the
command re-executes later inside a *verifier's* session at `--recheck`
(and at VERIFIED intake) — deferred code execution across the trust
seam. The screen tokenizes with Python `shlex` (punctuation-chars mode)
and requires every pipeline segment's program to be a bare allowlisted
name. H4 raised two objections; both are real.

### 1. The screen tokenized differently from its executor — a live bypass

`run_evidence` executes with `subprocess.run(cmd, shell=True)` — i.e.
`/bin/sh`. The screen and the executor were **two different tokenizers**,
and they disagree. `shlex`'s whitespace set includes newline; `/bin/sh`
treats a newline as a statement separator. So:

```
grep x /dev/null
touch PWNED
```

folds, in `shlex`, to `[grep, x, /dev/null, touch, PWNED]` — `touch` in
*argument* position, screened as a harmless argument to the allowlisted
`grep` — while `/bin/sh` runs `grep …` and then `touch PWNED`. Confirmed
live: the screen returns None (approve) and the shell creates the file.
A trailing `# comment` before the newline works identically. This is the
exact deferred-execution attack ADR-009 exists to stop, reachable by any
claim author against any verifier who rechecks.

The general rule: a screen is only sound if its tokenization is a sound
over-approximation of the executor's — every program the shell will run
must be seen by the screen as a program (and thus allowlist-checked). Any
character that is word-whitespace to `shlex` but a command separator to
`/bin/sh` breaks that. Newline and carriage return are such characters;
tab and space are separators to neither (word-whitespace to both).

### 2. The arg-deny blocklist cannot bound an interpreter or VCS

The bare-name allowlist does not see a program's *own* exec/write flags,
so ADR-009 added `PROGRAM_ARG_DENY` (F1). H4 noted this table is a
blocklist, referenced but not reproduced in the spec, and admitted
incomplete. The adversarial review confirmed it is worse than cosmetic:
with `git` on an allowlist, `git filter-branch --tree-filter '<cmd>'` is
arbitrary code execution the screen approves, alongside `git archive -o`,
`config --file`, `bundle`, `worktree`, `format-patch -o`,
`checkout-index`, `bisect run`, `submodule foreach`, and `-c <k>=!cmd`
aliases. No enumerable deny set closes a VCS's surface. (It also found a
precise enumerable gap on shipped tools: git denied `--output`/`-O` but
not lowercase `-o`, and `sort --compress-program=<cmd>` — an exec channel
on GNU coreutils — was undenied.)

## Decision

**1. Screen/executor tokenizer parity (the bypass fix).** The screen
refuses any evidence command containing an ASCII control character other
than tab — every byte `< 0x20` except `\t`, plus `0x7f`. These are the
characters `shlex` treats as word-whitespace but the shell treats as
separators or invisible manipulators; refusing them makes the screen's
token stream a sound over-approximation of `/bin/sh`'s for the command
class the screen admits (single printable line; `$(`/backtick already
refused; every shell operator either emitted as a token by `shlex` and
handled, or — for a control-char separator — now refused). Evidence
commands are single-line by convention, so this refuses only attacks and
mistakes. Fail-closed remains the rule: this answers H4's "decidability
is tied to the library" — the screen's *soundness* no longer depends on
`shlex` and `/bin/sh` agreeing on newline, because newline is refused
outright; any remaining tokenizer disagreement is confined to
safe-but-ambiguous commands the screen *rejects*, never admits.

**2. The blocklist is defense-in-depth, not the boundary; git stays out.**
The security boundary is the **allowlist of bare, read-only program
names** plus fail-closed tokenization — not `PROGRAM_ARG_DENY`. The deny
table is a courtesy that blunts a few *shipped* tools' known write flags
(`find -exec`/`-fprint*`, `sort -o`/`--output`/`--compress-program`),
which for those bounded tools is complete as far as is known. It is
explicitly **not** a mechanism that can make an interpreter, test runner,
or VCS safe. `git` (and `sed`, `awk`, `make`, `pytest`, …) are absent
from the shipped default allowlist by design and **must not be added for
evidence use**; the docs no longer imply the blocklist makes re-adding
git safe. The enumerable gaps found are closed (git `-o`; sort
`--compress-program`), and `git` is removed from this repo's own
`.truth/evidence-allow` (it was unused).

**3. The screen is one closed procedure, reproduced in the spec.** ADR-009
and the README now state the full algorithm and the `PROGRAM_ARG_DENY`
contents verbatim, so a clean-room implementation is a function of the
spec, not of a library — closing H4's "referenced but not reproduced"
gap. A second screen implementation remains forbidden (`screen_accept_command`
delegates to the one function — the F1/F5 drift lesson).

## Consequences

- The confirmed newline/control-char bypass is closed; the adversarial
  review could not break the fixed screen for the tokenizer-mismatch
  class (process substitution, here-strings, brace/ANSI-C expansion,
  escaped separators, redirection tricks all refused or inert).
- Locked mechanically: core `test_screen_rejects_control_chars` (newline,
  CR, and the `#comment\ncmd` variant refused; tab and legitimate
  pipelines/quoted-pipes still pass) and `test_arg_deny_covers_h4_gaps`
  (the table's contents pinned, including git `-o` and sort
  `--compress-program`); canary FAULT ES (a newline-smuggled command is
  refused at the CLI). The FS-2-style intent: the screen's decisions are
  now pinned, not implied.
- No legitimate single-line evidence command is affected.

## Non-goals

Not converting the deny table into a git-subcommand allowlist (git is out
of the default set entirely — the right layer is the allowlist, not the
blocklist). Not re-tokenizing to match a specific non-POSIX shell
(evidence executes under `/bin/sh`; a consumer who changes the executor
owns that parity). Not sandboxing evidence execution (a larger change;
the allowlist + read-only discipline remains the model).
