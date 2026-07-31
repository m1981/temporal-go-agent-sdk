# ADR-009: Evidence-command safety screen

Status: Accepted (2026-07-12, operator) — proposed 2026-07-11 in
`docs/hardening-proposals-solo-regime.md`, implemented in CLI v0.6.0;
screen made quote-aware the same day after the first two real ledger
commands exposed false-positive classes (see Decision). Canary faults
E1–E4.
Amended by: note (2026-07-12, F1) — an independent Fable review found
the screen bare-name only: allowlisted programs whose own flags open an
exec or file-write channel (find -exec/-fprintf, sort -o, git -c
<k>=!cmd) passed screening and would detonate on recheck — contradicting
this ADR's "read-only by construction" claim. v0.6.2 adds a per-program
argument-deny table and drops git from the shipped default allowlist
(its exec surface is unbounded); find and sort stay, their write/exec
flags refused (canary E5).
Amended by: ADR-027 (2026-07-19, M2) — states that the JSON Schema is
deliberately silent on this screen's semantics: `evidence.screened` is a
bare optional boolean with no `if/then`, because the property "a
screened=true was actually screened / is safe to re-execute" is enforced
OPERATIONALLY here (screen at filing; recheck trusts the stored flag only
to refuse, and re-screens everything else fresh before executing), not
structurally at `validate`. The silence is also a backward-compat
necessity (pre-ADR-009 records carry no `screened` key). The schema is a
necessary-not-sufficient gate.
Amended by: ADR-029 (2026-07-19, M4) — states that this screen is a GATE ON
EXECUTION, not a flat peer of the determinism double-run: a screen-failed
command is not run (so it reports the screen refusal, never determinism)
unless `--evidence-unsafe-ok` bypasses the whole screen (allowlist AND the
ADR-022 deny baseline), running it once in the author's own session as
`screened: false` for `recheck` to refuse.
Date: 2026-07-11
Supersedes: —

## Context

`run_evidence` executes an author-supplied string with `shell=True` —
at intake, and again **in a different session's context** whenever a
verifier runs `verdict --recheck`. That second execution is deferred
code execution across the very trust seam G11 protects: G11 ensures the
verifier receives no author *reasoning*; nothing ensured the verifier
didn't execute author *code*. The realistic regime threat: a
prompt-injected authoring session files a VERIFIED claim whose evidence
command is a payload, and the payload detonates when an obedient
verifier — instructed by the fixed prompt to recheck first — obeys.

## Decision

A static screen applied in **both** places the shell executes evidence:
intake (before the determinism double-run touches anything) and recheck.
Screening at recheck is not redundant — records may predate the screen
or have been appended raw; recheck rescreens against the *current*
allowlist.

**Mechanism.** Tokenize QUOTE-AWARE (shlex punctuation mode, stdlib).
The command passes iff every segment's program token is a bare name
(not a path — `./grep` is an attacker-supplied binary wearing an
allowlisted name) present in `.truth/evidence-allow`; no command
substitution or subshells; output redirection only to `/dev/null` or an
fd dup (`2>&1`); input redirection (`<`) allowed. Field note, recorded
because it earned the design: the first two real ledger commands each
broke a naive draft of this screen — a `grep -oE '…|…'` regex carries
pipes *inside quotes* (arguments, not separators), and
`>/dev/null 2>&1 && echo SENTINEL` is the paper's own §9 pin-the-output
convention and is read-only by definition.

**Allowlist is consumer policy** (ADR-003 rule 2 placement): the
template ships a read-only-by-construction default
(`.truth/evidence-allow`; `sed`/`awk` deliberately excluded — `sed -i`
and awk redirection write without a `>` the screen could see); test
runners are NOT shipped — a test runner executes repository code, which
is exactly the channel being screened; a consumer adds theirs as a
conscious, committed decision. `copier update` never reverts the file
(`_skip_if_exists`). Missing allowlist → VERIFIED intake fails closed
(the F1 lesson), even under the override.

**Override semantics — the load-bearing part.** `--evidence-unsafe-ok`
files anyway with `evidence.screened: false`, but **recheck never
executes an unscreened command**: it declines, files nothing, and tells
the verifier to run the command themselves if they trust it and file a
manual verdict naming what they ran. Filing freedom is preserved; the
*deferred, cross-session* execution channel is closed unconditionally.

## Explicit non-goals

Not a sandbox — an allowlisted `git log` still reads anything the
repository can read; output confidentiality is out of scope (the ledger
stores only the output *hash*, never output). Not full shell parsing —
constructs the tokenizer cannot confidently decompose fail closed.

## Consequences

Easier: verifier sessions become safe to run against a ledger whose
authors may have been prompt-injected — the one genuine security gap in
the regime closes. Harder: evidence commands lose expressive power by
default; commands in the test-runner class (e.g. the template's own
canary sentinel, `bash …-canary.sh >/dev/null 2>&1 && echo ALL-CAUGHT`)
recheck manually unless the consumer allowlists their runner. The
allowlist is one more config surface that can rot — `doctor` checks it.

Falsifier: any path by which `verdict --recheck` executes a command that
was never screened against the current allowlist.
