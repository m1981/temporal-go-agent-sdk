# ADR-037: recipe lints + the generated-paths refusal

Status: Accepted (2026-07-31, operator) — R3 of the 2026-07 gates
adoption (provenance: docs/reviews/gates-2026-07/, proposal 07's
linter record). Implemented in CLI v0.9.23, schema `$id` v0.14.
Core tests TestRecipeLints; canary FAULT RC (10 arms).
Date: 2026-07-31
Amends: — . Extends: ADR-009/ADR-021 (the lints consume the screen's
own shlex token stream — a second screen-side parser stays forbidden,
the F1/F5 drift lesson; a whitespace splitter would be gameable by
quote-splitting), ADR-012 (the `-n` lint names its exact mechanical-
divergence class), ADR-014 (warnings never refuse — the confused-
deputy lesson: a gate refusing legitimate filings teaches its own
bypass), ADR-032 (the generated override DECAYS — included, not
declined: "this path is generated" rots as build systems change, and
the re-ask is exactly the scan→re-file loop), ADR-034 (SI-4 policy-
file semantics; the lints ride the CC-1 block). Cites: ADR-026
(`$id` v0.14 — `generated_ok_basis` is a shape change).
Supersedes: —

## Context

Three recipe rot classes and one watch rot class were field-
exercised, named in prose (the kuchnie multiagent field note, the
batch-M note, `template/.truth/README.md`'s claim discipline), and
left to memory:
1. **Line-number output** — a `grep -n` recipe diverged mechanically
   in the pilot when an additive edit shifted numbers (ADR-012's
   exact class; the fact held, the recipe broke).
2. **Volatile literals** — a meta-repo claim hardcoded `v0.9.8`,
   broken by the v0.9.9 bump, diverged then retracted; the repair
   anchored to the schema `$id` — itself version-shaped, which is
   why this class needs carve-outs, not a blanket rule. Measured at
   adoption: roughly a quarter of real recipes carry version shapes,
   mostly legitimate invariants.
3. **Line-spanning phrases** — subsumed by ADR-035: the motivating
   hollow claim filed with exit 1 on a positive sentence, which the
   exit gate now refuses; the residual lexical heuristic was dropped
   at adoption (≥5-word quoted phrases are ~13% of real recipes,
   mostly legitimate, and the naive word count mis-tokenizes regex
   alternations).
4. **Generated artifacts as watches** — a pilot claim watching a
   generated file restaled on every regeneration; the proposed
   repo-declared list never shipped, until now.

## Decision

**Recipe lints** (warnings in the CC-1 advisory block; never
refusals), computed on `_evidence_toks()` — the ONE screen-side
tokenization shared with the ADR-009 screen:
- `-n`/`--line-number` as an argument of a grep-family program
  (per-SEGMENT: `sort -n` never fires) → the ADR-012 lint.
- A version-shaped (`v?X.Y[.Z]`) or date-shaped (`YYYY-MM-DD`)
  literal in a non-carved token → a warning naming the token and its
  expiry. Carve-outs (a tuple of named rules, changed only with the
  RC faults): path-context (the token contains `/` — filenames
  legitimately carry versions and dates), the schema-`$id` shape
  (`truth-ledger-record.vN` — the deliberately release-independent
  anchor that fixed the original defect), and frozen-record dates
  (Accepted/Amended/Date contexts — those never change). A
  deliberate version pin stays legitimate; the warning is the
  recorded acknowledgment that its divergence at the next bump will
  be genuine, successor material.

**The generated-paths refusal**, at the INV-M position (a
pre-execution gate-table row covering EVERY evidence class — an
INFERRED claim's watch restales identically): a `--paths` entry
matching the consumer-owned `.truth/generated-paths` list is
refused — watch the SOURCE the generator reads. `--generated-ok
"<sentence>"` files it, stores `generated_ok_basis` (schema v0.14;
the validate mirror refuses an empty basis and a basis beside
present-but-empty paths — an absent key is tolerated so both
contract surfaces agree on every FS-2 mutant, the ADR-035
returncode-tolerance pattern), is counted in the override report
(CC-2), and **decays** per ADR-032 (default 30-day TTL when no
explicit `--ttl-days`; the scan→re-file loop re-fires this gate).

**Policy-file semantics** (SI-4): the template ships
`.truth/generated-paths` EMPTY with a policy header — committed-
empty is conscious "nothing here is generated" and stays silent;
deleting the file leaves the check dark with one advisory line per
path filing saying so; pathspec-magic line starts are refused
(SI-1); the file is consumer-owned (`_skip_if_exists` in copier).

## Explicit non-goals

No semantic recipe judgment; no rewriting; no phrase-length
heuristic (dropped, revivable as its own ADR with a canary-pinned
boundary if ADR-035's coverage proves insufficient). The
volatile-literal shapes are lexical: a codename-versioned string
passes; extending the shapes is a constants-plus-RC-faults change.

## Consequences

Two field rules fire themselves at the only moment a rule reliably
reaches a fresh session — the terminal, as the claim is filed — and
the generated list becomes policy with a refusal behind it at the
position that covers all classes. Measurable: the ADR-012
mechanical-divergence rate (counted) and the ADR-035 hollow counters
are the before/after; the generated-ok row in the override report is
the policy file's health metric.

**Canary faults.** RC1: `grep -n` warns. RC1b: `sort -n` does not
(per-segment). RC2: a version literal warns naming the token. RC3:
schema-`$id` and path-context tokens stay silent (carve-outs as
properties). RC4: an INFERRED watch on a generated path is refused;
RC4b: `--generated-ok` stores the basis and takes the ADR-032
default decay. RC5: an absent list voices the dark notice and the
lints still fire (partial, loud fail-open). RC6: the shipped
committed-empty list is silent on a clean filing (SI-4). RC7: a
quote-split literal (`'v9.8''.7'`) still warns — the shlex token
stream, one parser. RC8: a `--generated-ok` that matched nothing is
voiced, NOT stored, and does NOT decay (the R3 adversarial review's
catch: ADR-032 re-asks a RECORDED judgment, so the decay row keys on
the stored basis and sits after the generated gate).
