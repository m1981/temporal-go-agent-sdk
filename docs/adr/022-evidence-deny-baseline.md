# ADR-022: A template-owned evidence-deny baseline for shells/executors, plus a doctor grey-zone advisory (C)

Status: Accepted (2026-07-19, operator) — proactive hardening prompted by
H4/ADR-021 (a live evidence-screen bypass) and the observation that the
allowlist is consumer-owned, so nothing mechanical stops a consumer from
allowlisting a dangerous program by accident. Amends ADR-009/ADR-021.
Implemented in CLI v0.9.7. Canary FAULT ED; core tests
test_denylist_wins_over_allowlist, test_deny_baseline_not_applied_to_oracles,
test_doctor_grey_zone_advisory.
Date: 2026-07-19
Supersedes: — (adds a layer beneath ADR-021's allowlist boundary; the
boundary is unchanged)

## Context

ADR-021 established that the security boundary of the evidence screen is
the **allowlist** of bare read-only program names — a blocklist cannot be
complete, so it is not the boundary. But the allowlist is *consumer
policy* (`.truth/evidence-allow`, `_skip_if_exists` so a `copier update`
never reverts a consumer's choices). That leaves one accident open: a
consumer who carelessly allowlists a shell or a generic executor — `sh`,
`bash`, `env`, `xargs` — silently converts the read-only screen into
arbitrary execution, because those programs exist precisely to run other
programs. H4 was the neighbouring instance: this repo itself had `git`
allowlisted. The template could only warn in a comment nobody is obliged
to read.

The tension: adding a deny layer risks re-introducing the false
confidence ADR-021 removed ("the template denies the bad stuff, so my
allowlist is safe"), which is never true — there are hundreds of ways to
execute code. The resolution is to split the problem in two, because
"dangerous program" is really two sets that want different treatment.

## Decision

**1. A template-owned deny baseline (`.truth/evidence-deny`), deny-wins,
evidence screen only.** A new file lists *only* programs whose sole job is
to run other programs — shells (`sh`/`bash`/`zsh`/`dash`/`ksh`/`csh`/
`tcsh`/`fish`/`ash`/`busybox`), generic executors and exec-wrappers
(`env`/`xargs`/`nice`/`nohup`/`timeout`/`setsid`/`stdbuf`/`watch`/
`command`/`time`/`flock`/`ionice`/`taskset`/`unshare`/`nsenter`/`chroot`/
`runuser`/`prlimit`/`chrt`/`eatmydata`/`script`/`expect`/`socat`/
`parallel`), and privilege-then-run tools (`sudo`/`doas`/`su`). `time`
earns explicit mention: an independent adversarial review confirmed
`time bash -c <cmd>` is RCE when `time` is allowlisted — program-position
innocent ("time my grep") while `bash` rides in argument position, and it
is both a `/usr/bin/time` binary and a shell keyword. The list covers the
well-known launchers and is NOT a completeness claim (see Non-goals). The
evidence screen refuses any of these in program position **even if the
consumer allowlisted it** (deny-wins, checked before the allowlist). This
makes **no completeness claim** — it is not "the dangerous programs," it
is "the programs that are never a read-only evidence check," so it has
zero false-positive cost. Ownership is the inverse of the allowlist:
`.truth/evidence-deny` is **template-owned** (NOT in `_skip_if_exists`),
so a `copier update` keeps every consumer's baseline current. Slogan: *you
own what you ALLOW; the template owns the baseline DENY.*

The deny baseline applies to the **evidence** screen only, never the
**acceptance** screen: ADR-014 oracles execute repository code on purpose
(`bash run-tests.sh` is their normal shape), so `screen_accept_command`
passes no denylist. This sharpens the ADR-009-vs-ADR-014 line — evidence
is read-only, oracles execute — rather than blurring it.

If the file is absent (an old deployment not yet updated), the deny layer
is simply empty: it fails **open** harmlessly, because the allowlist
remains the boundary. This layer only ever *removes* capability from an
allowlist, never grants any.

**2. A `doctor` grey-zone advisory (WARN, non-blocking).** Programs that
*can* execute code or write files but have plausible read-only uses —
`git`, `python`, `perl`, `ruby`, `node`, `make`, `pytest`, `awk`, `sed`,
`curl`, `wget`, `ssh`, `docker`, … — are **not** hard-denied, because
blocking them would fight legitimate workflows and re-open the
incompleteness trap. Instead `truth doctor` warns when the allowlist
contains one, so the H4-class accident is *surfaced* the moment it would
matter, while the policy stays the consumer's. This is a warning, not a
failure: `doctor` still exits 0.

## Consequences

- The worst accidental footgun (allowlisting a shell) is closed
  mechanically without any completeness claim; the grey zone is surfaced
  without over-blocking. The allowlist remains the boundary (ADR-021).
- Locked mechanically: core `test_denylist_wins_over_allowlist` (an
  allowlisted `bash` is still refused), `test_deny_baseline_not_applied_to_oracles`
  (an oracle may run `bash`), `test_doctor_grey_zone_advisory` (a
  grey-zone allowlist entry warns but does not fail); canary FAULT ED (an
  allowlisted shell is refused at the CLI).
- The deny baseline is data (a file), so a consumer can *audit* exactly
  what the template removes — unlike the code-owned `PROGRAM_ARG_DENY`.
- No change to any legitimate evidence command; the shipped default
  allowlist contained no shells or grey-zone programs, so doctor stays
  0 failures / 0 warnings out of the box.

## Non-goals

Not making the deny baseline a completeness claim (it is not the boundary;
ADR-021 stands). Not hard-denying grey-zone interpreters/VCS (advisory
only — deliberate execution belongs in an acceptance oracle, ADR-014).
Not letting consumers extend the deny file (it is template-owned; a
consumer restricts execution by trimming their allowlist, which they own).
