# RESUME — session entry point

Facts live in the ledger, not here: this file carries only ids and commands
(citation over restatement). Update at the end of every substantive session
(charter §7). Last updated: 2026-07-11.

## ⇄ SESSION COORDINATION (open — from the build/orchestration session, HEAD f7ff13e, 2026-07-12)

Two sessions are working this repo on trunk (no branches, shared git index).
There is no live cross-session messaging — THIS FILE + the ledger are the bus.

**From me (build/orchestration) — what I've covered:** built fsguard/pathscope/
file tools (ADR-007..010); installed governance + synced template to v0.5.7;
three SDK evaluations → ADR-011 + AP/PR checklist + PAT registry + dossiers;
filed 6 finding-claims + 4 phase items; wrote the membrane-hardening spec. I
reproduced YOUR pathscope-escape lead and filed it (tr-8f969e5d, fix wk-20a409b1
READY, build-tagged repro escape_repro_test.go). Full plan = 10 tasks (see below).

**Proposed rule:** single writer for `.truth/claims.jsonl` (me, since I hold the
plan) to avoid append races. You write code/tests freely; hand me claim/issue
bookkeeping or tell me and I'll file it.

**I need from you (leave answers in this block or reply via the user):**
- (A) Your task list + the FILES you're actively editing right now (collision-avoidance).
- (B) Any findings NOT yet in the ledger/RESUME — bugs, dead ends, insights.
- (C) Which lane you'll own so I don't dispatch a Fable 5 agent onto it:
      keep going as independent VERIFIER (dispatch tr-8f969e5d / tr-466f3e3e /
      tr-799b362d — satisfies no-self-verify), OR take the pathscope fix
      (wk-20a409b1). Not both. Tell me which.

**Ready-now lanes:** #3 pathscope fix (wk-20a409b1, P0), #4 adversarial review of
a7e069c..HEAD, #5 independent claim verification. Blocked chain: Phase 1
(wk-dcc7a92d) → Phase 2 → Phase 3; Phase 4 after Phase 1.

---

## Bootstrap (30 seconds)

1. Read `AGENTS.md` (binding rules; §8 design-review/evaluations discovery,
   §9 ledger discovery).
2. `scripts/truth queue` — empty means carry on.
3. `scripts/truth ready` — the unblocked work frontier.
4. Before editing any file: `scripts/truth impact <path>` — it names the
   claims your edit will stale and the work items that get HELD.

## Current focus

- **TOP / SECURITY P0 — wk-20a409b1**: pathscope workspace escape, CONFIRMED
  and repro'd (claim tr-8f969e5d). A scoped write to a raw `<root>/link/../x`
  (link→outside) is accepted and lands OUTSIDE root. Repro:
  `go test -tags escape_repro -run TestScopedWrite ./pkg/tools/file/`. READY
  now; fix before relying on pathscope for any sandboxing.
- **wk-dcc7a92d** (ADR-011 phase 1 membrane). Spec:
  `internal/runtime/docs/specs/membrane-hardening.md`. NOTE: currently HELD in
  `truth ready` — two of its premises diverged then were corrected under new
  ids (tr-466f3e3e, tr-799b362d, re-premised), but the diverged originals
  still block (see field-feedback note below). Resolve before coding.
- Sequence after: wk-39850a5b → wk-0bdbd4e4 → wk-7baee278 (rationale: ADR-011).

## Verification debt (independent verifier pass — 2026-07-12)

All 12 dispatched claims now carry a filed verdict (10 agree, 2 diverge).
- Agreed (evidence supports text): tr-1726ec57, tr-dc6b174d, tr-00eded8e,
  tr-d38998db, tr-16104518, tr-b9e3683f, tr-42e5b4c3, tr-e1d73540,
  tr-166b071c, tr-9737e935. The four former stale claims are refreshed, so
  `spec-health` on the fsguard spec now passes.
- Diverged, now CORRECTED (originals terminal, replacements filed):
  tr-6cb4d1a2 → **tr-466f3e3e** (was "5 sites"; really 6, in two files —
  count-free text now), and tr-09eeed62 → **tr-799b362d** (evidence grep
  re-scoped to `.go` so it no longer matches prose in a spec `.md`; finding
  "no recover() in code" still true). Both corrections are `unverified` —
  dispatch them.
- **Pathscope escape now filed**: tr-8f969e5d (P0, verified) + wk-20a409b1
  (fix, READY). See Current focus.
- FIELD-FEEDBACK for the ledger (see planning eval doc): a diverged premise
  permanently HOLDs its work item even after the claim is corrected under a
  new id — there is no premise-supersede/-detach verb (append-only + issue
  first-wins). wk-dcc7a92d is stuck on tr-6cb4d1a2/tr-09eeed62 (diverged)
  despite the corrections. Workaround options: re-file the work item fresh on
  the corrected premises, or a template feature (premise-supersede).
- Command per id, in a fresh session: `scripts/truth dispatch <id>`.

## Known repo oddities

- `docs/reference/code-review.md` is a committed session transcript
  (owner decision pending: keep, move to `docs/archive/`, or remove).
- Template: truth-ledger v0.5.7 (copier ref `543d549`; tags upstream lag
  main — trust `.copier-answers.truth-ledger.yml`, not `git ls-remote`).
- `jsonschema` is not installed (host Python 3.14 pip is broken); drift
  detector runs via fallback.
