# ADR-039: the blast forecast and the churn report — advisory only

Status: Accepted (2026-07-31, operator) — R5, the final release of
the 2026-07 gates adoption (provenance: docs/reviews/gates-2026-07/;
the rev-1 refusal gate was severed there after its default threshold
was falsified against this repository's own history, `tr-c3087292`).
Implemented in CLI v0.9.25, schema `$id` v0.15. Core tests
TestBlastForecast; canary FAULT BF (7 arms).
Date: 2026-07-31
Amends: — . Extends: ADR-034 (SI-2 subprocess discipline; the
advisory rides the CC-1 block), ADR-033 (the churn section is that
ADR's move — a report a human reads, named as such; the rev-1 text
overclaimed it as ADR-032's mechanical revisit and was corrected at
review). Cites: ADR-026 (`$id` v0.15 — `blast_forecast` is a shape
change), ADR-030 (the reaffirm trial whose first read gates any
future refusal ADR), the growth-gate #3 design (the staler ranking
is its demand-signal generator).
Supersedes: —

## Context

Re-verification churn is the regime's dominant operating cost
(paper §2.2: ~98.5% of verdict labor re-confirms; §8 item 2), and
watch breadth is its largest controllable driver — governed until
now by prose (§9: "scope `--paths` to the narrowest set"). The field
cost is measured: the pilot's hottest claim — four watched paths —
staled 15× and re-agreed 15× over its 15.3-day life (median
agree→stale 0.31 h), its dominant staler a *document*; in the second
deployment one commit re-staled 8 claims (2 genuinely affected).

The rev-1 proposal shipped a refusal above a fixed threshold of 15.
The adoption review replayed that default against this repository:
**82 of 96 path-carrying claims would have refused**
(`tr-c3087292`) — `--blast-ok` as a per-filing ritual in the
template's own home. Meanwhile the shipped countermeasure for
exactly this churn — reaffirm's hash-match arm (ADR-030) — is
mid-trial. Gating filings on a cost the running countermeasure may
have absorbed, with a threshold falsified at home, would invert the
house's own ADR-032/033 calibration discipline. This ADR ships the
instrument and defers the gate.

## Decision

**The forecast, honest about what it is.** Filing a claim with
`evidence_paths` stamps `blast_forecast`: the count of distinct
commits in the trailing `BLAST_WINDOW_DAYS` (30) touching any
watched path — gathered by one `git log --format=%x01%H
--name-only --no-renames` with `core.quotepath=off` at
`cwd=repo_root()` (SI-2), matched core-side by `match_paths` against
the deduplicated distinct-file set. This is an **upper bound on
stalings, not an expectation**: a claim stales only from live, so N
commits between re-verifications produce one staling. (The log runs with `--since-as-filter`, never plain `--since` — the
latter STOPS the traversal at the first out-of-window commit, so one
backdated commit near the tip would empty the log into a quietly-cold
0-under-ok, the exact 0-as-unknown this ADR forbids; on git < 2.36
the option errors into the loud unavailable path, the preferred
failure mode — the R5 adversarial review's catch, pinned by BF6's
two-direction assertion. Residual: a
newline inside a filename breaks the line parse — disclosed;
`--no-renames` mirrors the invalidation scan's own recorded lesson
so forecast and staling agree on the rename event class.)

**Advisory above the floor, silence below (CC-1).** One line at or
above the floor: `blast: watch matched N commits in the last 30d --
an upper bound on stalings; narrower --paths cut re-verification
load`. **The floor self-calibrates**: P90 of stored
`blast_forecast` values over LIVE path-claims once
`BLAST_MIN_OBSERVATIONS` (20) exist; the calibrated value clamps to ≥1 (an
all-cold corpus must not flag stone-cold watches as hot); the constant
`BLAST_ADVISORY_FLOOR` (15) is the cold-start fallback only.
Calibration reads LIVE claims, so a fresh (unverified) claim's
forecast joins the sample only after its first agree — in a repo with
no verifier loop the floor stays at the fallback, the documented cold
start — a
per-repo percentile stored as a universal constant is a category
error (at review, a fixed 15 would have printed on ~85% of this
repo's filings). The effective floor and its source print in the
stats section, so calibration is visible.

**Loud degradation, nothing stored.** Shallowness is probed first
(`git rev-parse --is-shallow-repository` — a shallow `git log`
truncates SILENTLY, and a quietly-cold forecast is the exact silent
skip this design forbids): the advisory says "a forecast would be a
floor, not a bound; skipped". An unborn HEAD or any log failure
voices "history unavailable". In both cases `blast_forecast` is
**absent**, never 0-as-unknown.

**The churn report.** `truth stats` gains the `blast` section
(shared fold): observed invalidations vs forecast-at-filing per
path-claim (top 5 by observed), the per-path staler ranking read
from invalidation `touched` lists (no git work — the record already
carries them), and the effective floor + source. ADR-033's move.

**The refusal gate deliberately does not ship.** It returns only as
its own future ADR after ≥30 days of forecast-vs-observed data from
this report AND the reaffirm-trial read, with the threshold derived
from the measured distribution — this paragraph is the demand
signal; the report above is its instrument. The staler ranking is
likewise the demand-signal generator for growth-gate #3
(coarse-watch/fine-verify): it names the paths whose claims deserve
symbol pins first.

## Explicit non-goals

No refusal (severed, above). No semantic narrowing — commits are
counted, not meanings; a newly-hot file forecasts cold and the
report catches it after the fact (the accepted trade). No TTL
coverage (clock decay, not commit decay). No auto-narrowing of
`evidence_paths` — the forecast informs the author; it does not
author.

## Consequences

Authors see the price of a broad watch at the moment they choose
it, in a number with honest semantics; the operator gets the churn
ledger the gate decision always lacked; the refusal question becomes
a measurement with a date. Cost: one log traversal, one rev-parse
per path filing.

**Canary faults.** BF1: a hot watch (≥floor commits/30d) voices the
upper-bound advisory. BF2 (negative control): a sub-floor watch
stays silent. BF3: a shallow clone voices floor-not-bound, never a
quietly-cold number. BF4: `blast_forecast` stored on the record;
`validate` accepts it and tolerates its absence on legacy lines.
BF5: `stats` renders the blast section. BF6: a
`GIT_COMMITTER_DATE`-backdated out-of-window commit is filtered OUT
while in-window commits still count — both directions asserted, so a
plain-`--since` traversal stop cannot pass vacuously (BLAST_WINDOW_
DAYS is a constant paired with these faults). BF7: an unborn-HEAD repo voices
history-unavailable and stores no forecast.
