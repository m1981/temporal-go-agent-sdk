# RESUME — session entry point

Facts live in the ledger, not here: this file carries only ids and commands
(citation over restatement). Update at the end of every substantive session
(charter §7). Last updated: 2026-07-11.

## Bootstrap (30 seconds)

1. Read `AGENTS.md` (binding rules; §8 design-review/evaluations discovery,
   §9 ledger discovery).
2. `scripts/truth queue` — empty means carry on.
3. `scripts/truth ready` — the unblocked work frontier.
4. Before editing any file: `scripts/truth impact <path>` — it names the
   claims your edit will stale and the work items that get HELD.

## Current focus

- **wk-dcc7a92d** (ADR-011 phase 1). Spec with design + pre-written
  acceptance: `internal/runtime/docs/specs/membrane-hardening.md`.
- Sequence after it: wk-39850a5b → wk-0bdbd4e4 → wk-7baee278 (rationale:
  ADR-011; the kernel records deps only at issue birth, so ordering beyond
  wk-0bdbd4e4's dep edge lives in ADR-011 prose and here).

## Verification debt (human dispatch required; agents MUST NOT self-verify)

- Stale (mechanically tripwired by later same-package commits; re-run
  evidence via dispatch): tr-1726ec57, tr-dc6b174d, tr-00eded8e, tr-d38998db.
  These 4 are why `spec-health` currently fails on the fsguard spec.
- Unverified since filing: tr-16104518, tr-b9e3683f, tr-42e5b4c3,
  tr-6cb4d1a2, tr-e1d73540, tr-09eeed62, tr-166b071c, tr-9737e935.
- Command per id, in a fresh session: `scripts/truth dispatch <id>`.

## Known repo oddities

- `docs/reference/code-review.md` is a committed session transcript
  (owner decision pending: keep, move to `docs/archive/`, or remove).
- Template: truth-ledger v0.5.7 (copier ref `543d549`; tags upstream lag
  main — trust `.copier-answers.truth-ledger.yml`, not `git ls-remote`).
- `jsonschema` is not installed (host Python 3.14 pip is broken); drift
  detector runs via fallback.
