# ADR-033: override-velocity report

Status: Accepted (2026-07-20, operator) — roadmap-v3 R13 (batch 5,
override decay's instrument), adopting candidate C6 from the 2026-07-20
clean-room convergence analysis. Implemented in CLI v0.9.14, after
ADR-032 (it reads the fields R12 stamps). Core tests TestOverrideReport +
TestOverrideReportCLI; canary FAULT OV (2 arms incl. negative control).
Date: 2026-07-20
Amends: ADR-007 (supplies its adoption gate the instrument it named but
lacked). Extends: ADR-012/030's measurability discipline (make the
mechanical/genuine split grep-able so a rate can be computed). Reads:
ADR-032 (`ttl_default`, decay expiries).
Supersedes: —

## Context

ADR-007's adoption gate — "override rate above ~50% of firings → narrow
the lexicon" — named an instrument (`truth stats`) that did not yet
report overrides. ADR-032 then added a second question the same gate
must answer: are override-decay expiries exceeding genuine diverges
(i.e. is the decay catching drift, or just re-filing unchanged
sentences)? Both need the same thing: counts of override activity a
human can read monthly, and a signal for the specific pathology ADR-032
predicts — a scope justification re-filed **verbatim** after it expired,
which is the shape of an override that was never real judgment.

## Decision

`override_report(events, now)` — a pure fold consumer beside
`stats_report`, counting over the given events (the shell applies any
`--since` window first, matching `stats_report`'s overall-count
convention; no per-window split of its own). It returns:

- `scope_basis_filings` — ADR-007 `--scope-ok` overrides;
- `decay_expiries` — ADR-032 decay invalidations (`reason_code == "ttl"`
  on a `ttl_default` claim). This section is now the **only** place TTL
  expiries are counted: as of the batch-5 red-team fix, the FS-1
  half-life medians `stats` also prints exclude TTL-reason invalidations
  (they are administratively caused, not observed drift — ADR-032
  Consequences), so `decay_expiries` here and the half-life numbers
  measure disjoint populations by design;
- `overridden_duplicates` — G8/`--duplicate-ok` filings;
- `screened_false_filings` — `--evidence-unsafe-ok` filings;
- `max_scope_ttl_days` — the largest `ttl` among scope_basis claims, so
  the visible opt-out (a deliberately large `--ttl-days`) is itself
  visible;
- `repeats` — **verbatim-repeat detection**: a `scope_basis` claim whose
  `tokens()` token set EQUALS that of an EARLIER claim now **dead**
  (stale/diverged/retracted — a claim has no `superseded` status here,
  supersede being premise-scoped, ADR-013), flagged as a repeat. A prior
  claim still **live/unverified** is NOT flagged — that is ADR-018
  near-duplicate territory, a different concern. The detector REUSES the
  existing `tokens()` — no second tokenizer (the ADR-018/021 parity
  lesson: two tokenizers drift).

**Shell.** `truth stats` prints an `overrides` section; for each repeat
a non-blocking advisory line: *"same scope justification re-filed
unchanged after expiry -- review whether the scope judgment was ever real
(ADR-033)"*. `--json` carries the structured section. **No threshold, no
blocking, no new gate** — it is a report.

## Consequences

Easier: ADR-007's and ADR-032's adoption gates become computable from
one command; the hand-audit reads a number instead of grepping the
ledger. The verbatim-repeat advisory names the exact pathology ADR-032
predicts, at the moment it appears. Harder: nothing mechanical — a pure
fold consumer, no new record, status, or fold change.

## Calibration debt and measurement plan

The advisory has an honest false-positive class: a scope justification
CAN be legitimately re-filed unchanged when the scope genuinely still
holds and the sentence was already the best statement of it — an honest
re-affirmation, not rot. Token-set equality cannot tell these apart; only
a human reading both claims can. So the advisory is **non-blocking on
purpose**, and there is **no threshold** until the FP rate is known.
Measurement plan: fold the overrides section into the R11 monthly
hand-audit; after two windows establish the advisory's FP baseline,
consider a threshold tripwire (roadmap Backlog — explicitly deferred).
Until then the report informs a human and gates nothing.

## Residual false negatives (advisory is trivially evadable)

The calibration debt above covers the advisory's false *positives*. Its
false *negatives* are just as real and, unlike the FPs, **trivially
achievable** — the red team demonstrated both:

- **One edit defeats the verbatim advisory.** The `repeats` detector is
  token-**set** equality over `tokens()`. A single synonym swap, or one
  appended junk token, changes the set and the advisory goes silent —
  the re-file is no longer "verbatim" by this test even though the scope
  judgment is unchanged in substance. What does NOT defeat it (the set
  is order-insensitive and `tokens()` normalizes): reordering the words,
  changing case, or altering punctuation. So the advisory catches only
  the laziest repeat and any author who edits at all evades it.
- **The backstop is the raw counters, not the advisory.** This is why
  `scope_basis_filings` and `decay_expiries` are the load-bearing signal:
  they increment on every filing and every expiry **regardless of text
  evasion**, and they are the volume numbers the R11 monthly hand-audit
  reads for the ADR-007/032 adoption gates. The `repeats` advisory is a
  convenience pointer at the one shape a machine can name for free, not
  the measurement — an evaded repeat still shows up as another
  `scope_basis_filings` increment.
- **Cosmetic: repeats name the earliest dead prior, and line count is
  the accumulation signal.** When a justification is re-filed repeatedly,
  each advisory line names the *earliest* dead prior it matches (the walk
  flags against the first matching `seen` entry), and there is no repeat
  *counter* — accumulation shows up as the number of advisory lines, not
  as a tallied count. An auditor reads the count of lines, not a field.

## Non-goals

Not a gate (no blocking, no exit-code effect). Not a judgment: the
advisory flags a token-set match, never asserts the scope judgment was
wrong. Not a second tokenizer (ADR-018/021). Not per-window analytics
beyond what `stats --since` already gives. Not tamper detection: a
raw-appended claim that omits `scope_basis` or `ttl_default` simply is
not counted — the accepted forged-record residual (paper §8 item 6).

Falsifier: a verbatim re-justification after a decay expiry that the
report fails to flag, or a genuinely narrowed re-file that it flags — the
two canary FAULT OV arms pin exactly these.
