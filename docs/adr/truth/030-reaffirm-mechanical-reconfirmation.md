# ADR-030: `reaffirm` — mechanical re-confirmation is not first verification

Status: Accepted (2026-07-20, operator) — roadmap-v3 R3 (batch 2, the
churn fix), implemented in CLI v0.9.12; red-team review fixes
(F1 wording, F2 `reaffirm_cleared`, F3 `reason_code` + rescreen test,
F4 override loudness) folded into the same release. Core tests
TestReaffirmTriage / TestReaffirmCLI; canary FAULT RA locks the
mismatch arm.
Date: 2026-07-20
Supersedes: —
Extends: ADR-012 (the mechanical/genuine vocabulary, applied to labor);
ADR-019 (TTL never resets by re-verification); ADR-010 (session
separation); ADR-009/029 (the screen gates execution, intake AND
recheck).

## Context

The meta-repo pilot measured re-verification churn, not filing, as the
dominant operating cost (paper §8 item 2: on the order of ten agree
verdicts per claim; `stats` half-life medians of ~0.02 days in every
tier — claims watching hot paths re-stale within the hour). Almost all
of that labor finds nothing: the evidence command re-runs, the hash
matches, a verifier files the same agree it filed yesterday. ADR-012
gave the *verdict* vocabulary a mechanical/genuine split; this ADR
extends that split to the *labor*: **re-confirming unchanged evidence
of an already-judged claim is mechanical work** — a hash comparison, no
interpretation — while **first verification and every mismatch are
genuine work** — someone must judge whether evidence supports a
sentence, or why a hash moved. A batch verb may automate exactly the
mechanical half and must never touch the genuine half.

## Decision

`truth reaffirm` folds the ledger and walks claims with derived status
`stale`. One pure function (`reaffirm_triage`) assigns each exactly one
arm; the shell only gathers facts, executes, appends, and prints (one
line per claim, a per-arm summary; `--json` for harnesses; `--dry-run`
triages and files nothing).

**1. TTL-staled → skip, re-file required.** ADR-019: TTL counts from
the claim's own ts and re-verification never resets it — an agree here
would be re-staled by the very next scan, forever. TTL-staleness is
read from the claim's *invalidation records*, never recomputed from the
clock: the scan is the sole clock reader and already materialized the
expiry; reaffirm judging time itself would be a second clock in a path
ADR-019 made clock-free. The scan stamps a structured
`reason_code: "ttl"` beside the human reason (red-team F3), and triage
prefers it: TTL expiry is monotone under ADR-019 (the clock never runs
backwards, re-verification never resets it), so ANY scan-stamped ttl
record is durable proof of this arm, and a later invalidation with a
different free-text reason — including a raw-appended forgery — can no
longer flip the claim into the auto-agree path. The prefix match on the
latest record's free-text reason survives only as the fallback for
records that predate the stamp. A raw-appended invalidation with a
forged `reason_code` itself remains the general accepted forged-record
residual (paper §8 item 6): the ledger trusts its appenders.

**2. Mechanically unexecutable → skip, manual verification only.** The
recheck refusal discipline (ADR-009/029), reused verbatim: a
`screened: false` capsule (filed `--evidence-unsafe-ok`) is the
author's own admission and is final — the command is NEVER executed; a
command the CURRENT allowlist screen refuses (records may predate the
screen, and policy is the committed list *now*) is likewise never
executed; a claim with no evidence command has nothing to re-run; a
recheck exiting 127 is environment, not reality (`recheck_verdict`'s
existing rule). Also in this arm: a stale claim **no verifier ever
agreed with**. Reaffirm re-confirms a verification that already
happened; auto-filing a FIRST agree would be first verification without
judgment — the exact thing `verdict --recheck` refuses when it reports
a matching hash instead of filing ("a matching hash is a report, not a
judgment"). Prior human/verifier judgment is what licenses the
automation; without it there is nothing mechanical to re-confirm.

**3. Same-session → skip.** ADR-010, reused verbatim from
`verdict agree`: the authoring session agreeing with itself is
self-verification, batch edition — a session that files claims and then
sweeps them back to live has erased the independence seam (G11).
`TRUTH_SELF_VERDICT=1` remains the loud F4-class override — but note
the amplification: on a manual agree it bypasses the seam for ONE claim
the operator is looking at, while here one env var bypasses it for
every same-session claim in the sweep, so reaffirm prints a stderr
WARNING naming the override and the count of same-session claims it
auto-agreed.

**4. Otherwise, run the recheck — through the SAME path.** The evidence
command executes via `screen_evidence_command` (current allowlist +
ADR-022 deny baseline, gating execution per ADR-029) then
`run_evidence` + `recheck_verdict` — the identical machinery
`verdict --recheck` uses; a second executor or screen is forbidden (the
F1/F5 and ADR-005 drift lesson). Then:

- **MATCH** (hash and exit code equal the capsule): append
  `agree` with basis `"reaffirm: hash-match, no judgment re-run"` and
  `anchor_commit` = current HEAD when the claim carries evidence_paths
  — the same re-anchor rule as a manual agree, so the effective anchor
  advances (F2) and the next scan diffs from here. Be precise about
  what a match means: the COMMAND OUTPUT is unchanged, nothing more.
  When evidence_paths is wider than what the command reads, a
  watched-but-unread path change is exactly what staled the claim, the
  output still matches, and this arm re-agrees anyway (see Non-goals).
  The anchor advance is the benefit (no re-stale loop) and also the
  masking move: the unjudged watched-path change would otherwise sit
  outside every future scan diff window, invisible. So the reaffirm
  agree records what it auto-cleared (red-team F2) in
  `reaffirm_cleared: {"prior_anchor": ..., "touched": [...]}` — the
  prior EFFECTIVE anchor (the diff base the scan staled the claim
  against) and the watched files that changed in prior_anchor..HEAD,
  computed with the scan's own `changed_files_since` + `match_paths`
  (no second differ); if the diff fails, the prior anchor alone is
  recorded. An auditor can replay every burial from the ledger. The
  basis string names the automation honestly: a verifier reading the
  ledger can distinguish a judged agree from a mechanical one, so
  FS-1's rates stay measurable (the ADR-012 motivation, labor edition).
- **MISMATCH: file NOTHING.** Not agree, obviously — but not diverge
  either, although single-claim `verdict --recheck` auto-files diverge.
  The asymmetry is deliberate: `--recheck`'s auto-diverge lands in
  front of a verifier who invoked it for that one claim and is already
  looking — the ADR-012 mechanical-vs-genuine judgment (and a possible
  `--mechanical` annotation) happens seconds later. A batch sweep has
  no judge present; auto-filing diverge wholesale would stamp dozens of
  claims with an unjudged negative verdict, flooding the queue with
  status changes nobody examined and pre-committing the eventual
  verifier (the same pre-commitment `--recheck` refuses on the agree
  side). A mismatch is therefore a *report*: the claim is listed as
  "diverged evidence — dispatch for judgment" and its status stays
  stale, which already queues P0/P1 for humans. The dispatch path
  decides mechanical vs genuine.

## Consequences

Easier: the measured bulk of verification labor — re-running unchanged
evidence — becomes one command in a fresh session, and re-verified
claims stay live across scans (F2) instead of re-staling on frozen
anchors; the human queue receives only judgment cases. Harder: nothing
mechanical — no fold change, no new record kind or status; a reaffirm
agree is an ordinary verdict record any fold since v0.4 handles.
Auditability: the fixed basis string makes automated agrees
grep-able, so a future FS-1 metric can split reaffirmed from judged
agrees the way ADR-012 split diverges; `reaffirm_cleared` (MATCH,
above) additionally pins WHAT each mechanical agree buried behind its
anchor advance. Both new payload fields (`reaffirm_cleared` on the
agree, `reason_code` on scan TTL invalidations) ride the open payload
objects of schema and mirror — no contract-shape change, older folds
ignore them.

## Non-goals and residuals

Not a substitute for verification: reaffirm never judges whether
evidence supports a claim's text. And be plain about what the match arm
actually checks, because it is narrower than "unchanged evidence": it
re-agrees whenever the COMMAND OUTPUT is unchanged — even if a watched
path the command does not read changed. That gap is not hypothetical;
it is the normal shape of a stale claim here: evidence_paths wider than
the command's read set is what makes a claim stale while its output
still matches, and the text-vs-evidence question that change raises
("does the sentence still hold now that a watched file moved?") is
exactly the judgment `verdict --recheck` deliberately defers to a human
— reaffirm auto-clears it. The `reaffirm_cleared` field makes each
such clearance auditable after the fact (see MATCH), but auditability
is not judgment: **operators must keep evidence commands as wide as
their evidence_paths**, or reaffirm will silently re-agree claims whose
watched-but-unread paths changed — the INV-M/doc-coverage residual
class, accepted and named here. Also not auto-diverge (above), not TTL
renewal (ADR-019) — and a raw-appended invalidation with a forged
reason remains the accepted §8-item-6 forged-record residual, narrowed
but not closed by `reason_code` (arm 1). Not execution of anything the
screen refuses (ADR-009/021/022/029), not scan-time auto-execution
(the red-team's do-not-do list: reaffirm is a deliberate verb run in a
verifier session, never a hook side effect).
