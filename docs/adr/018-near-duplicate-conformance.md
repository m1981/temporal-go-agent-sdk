# ADR-018: Near-duplicate intake is Jaccard over a fixed token set (H1)

Status: Accepted (2026-07-18, operator) — source: independent review
finding H1 (High), a spec-precision defect confirmed against the shipped
CLI. Ratifies the existing v0.4 implementation as normative; no behavior
change. Canary FAULT I (metric-identity arm); core test
`test_near_dup_metric_is_jaccard_not_overlap`.
Date: 2026-07-18
Supersedes: — (pins prose that was underspecified in paper §1 and
`.truth/README.md`; leaves the code path unchanged)

## Context

The intake gate that refuses near-duplicate claims (guard G8) has been
concrete in code since v0.4, but the **normative prose** described it
only as "word-level, case-folded token overlap ≥ 0.6 against claim text"
(paper §1) and "≥0.6 token overlap" (`.truth/README.md`). H1 observed
that this underdetermines three things a clean-room second implementer
must pin, and that two conforming implementations would then accept vs.
refuse the same second claim — the two-implementers conformance test
fails:

1. **The metric.** "Overlap ≥ 0.6" names no formula. Jaccard
   (`|A∩B|/|A∪B|`), the overlap coefficient (`|A∩B|/min(|A|,|B|)`), and
   Dice (`2|A∩B|/(|A|+|B|)`) all differ across the 0.6 boundary. The
   phrase "overlap" most naturally reads as the overlap *coefficient* —
   which is precisely the metric the reference does **not** use.
2. **The tokenizer.** "word-level, case-folded" fixes neither the split
   rule (punctuation, hyphenation, stemming) nor multiplicity.
3. **The active set.** "active claims" was never mapped onto the status
   vocabulary, and the parenthetical "corrections of dead claims are
   always allowed" implied a dead set without enumerating it. The
   near-dup dead set need not equal ADR-013's supersede dead set, and it
   does not.

Worked divergence (a strict token-subset, the common "agent elaborates
on an existing claim" case): A = "auth module owns login", B = "auth
module owns login and also owns logout and session refresh handling".
`A`'s tokens ⊆ `B`'s. Jaccard = 4/10 = **0.40** → the reference
**accepts** B (not a duplicate). Overlap coefficient = 4/4 = **1.0** →
an implementer who read "overlap" literally **refuses** B. Same input,
opposite decision.

## Decision

Ratify the shipped implementation as the normative specification:

- **Metric — symmetric Jaccard:** `|A∩B| / |A∪B|`, where `A`, `B` are the
  token sets of the two claim texts; `0.0` when either set is empty.
  Refuse intake when the value is **≥ 0.6** (`DUPLICATE_THRESHOLD`)
  against any active claim. Not the overlap coefficient, not Dice —
  Jaccard is symmetric and treats a strict elaboration (subset ⊂
  superset) as *not* a duplicate, which is the intended behavior: adding
  material is a new claim, not a restatement.
- **Tokenizer:** `set(re.findall(r"[a-z0-9]+", text.lower()))` — lowercase,
  then every maximal run of ASCII `[a-z0-9]` is one token; every other
  character is a delimiter (so hyphens, slashes, punctuation split; no
  stemming). The result is a **set**: token multiplicity and order are
  discarded.
- **Active set — exactly `{live, unverified}`.** Every other status —
  `stale`, `diverged`, `cannot_verify`, `retracted`, `disputed` — is
  *dead for near-dup intake*, so a correcting claim against one is
  always allowed (UC-4). This is the positive-form definition: it stays
  correct as the status vocabulary grows (`disputed`, v0.9.0, was added
  after the gate and is exempt for free), and it is deliberately
  independent of ADR-013's supersede dead set.

## Consequences

- The two-implementers conformance test now passes by construction: the
  metric, tokenizer, and active set are each pinned to one reading.
- Locked mechanically so prose and code cannot silently drift apart
  again: core test `test_near_dup_metric_is_jaccard_not_overlap` asserts
  the worked example lands at 0.40 (accepted) and that the overlap
  coefficient on the same tokens would be 1.0 (would-refuse); canary
  FAULT I gains a metric-identity arm asserting a token-superset claim is
  **accepted** at the CLI layer.
- No behavior change and no version bump on its own account: the CLI
  already computed exactly this. This ADR is documentation catching up
  to code, plus the conformance locks.

## Non-goals

Not changing the threshold, the metric, or the tokenizer (semantic
similarity, stemming, and embeddings are all out of scope — the gate is a
cheap syntactic tripwire, ADR-003-style consumer discipline handles the
rest). Not unifying the near-dup dead set with ADR-013's supersede dead
set — they answer different questions and are allowed to differ.
