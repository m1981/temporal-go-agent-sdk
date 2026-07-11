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

**RESOLVED (2026-07-12, via `claude --resume` CLI relay).** Shared truths T1–T4
all AGREED: (T1) build session is sole `.truth` writer; (T2) HEAD baseline;
(T3) pathscope escape is a real P0; (T4) absolute UTC, canonical order (ts,id).
Lane split: peer = independent VERIFIER (Lane A); build session = build/eval/fix/
orchestration. Peer's lane now DISCHARGED — it delivered two `agree` verdicts,
filed by me under T1 with peer attribution:
- tr-466f3e3e → live, tr-799b362d → live (the two corrected finding-claims).
- tr-8f969e5d (pathscope escape) LEFT for a THIRD uninvolved session — peer is a
  co-discoverer, so not maximally neutral. Still `unverified`; route elsewhere.

**Peer gold knowledge captured (committed):**
- fsguard raw-path root cause → tr-3ef6f8ff (P0), premised into wk-20a409b1.
- stronger upward-symlink variant (`<root>/a/b/link -> <root>` + `..` escapes
  ABOVE root; one non-deterministic probe) → folded into wk-20a409b1 test scope.
- ADR-008 overclaim → KNOWN DEFECT banner (ADR_AMEND).
- SEVERITY NUANCE: the fsguard/pathscope/file trio is imported by NO runtime
  code and NO example (tr-9737e935), so the escape is a real P0 IN THE LIBRARY
  but LATENT — not a live production path until wired in. Sequence: FIX
  wk-20a409b1 BEFORE Phase-1 guard-wiring (already encoded: task #6 blocked by #3).
- ADR-009 soft note (no amend needed): MarkReadRange/CheckEditable exists+tested
  but is NOT wired into pkg/tools/file; the region guard is dormant. ADR-009
  discloses wiring as follow-up, so borderline, not a hard overclaim.

---

## Bootstrap (30 seconds)

1. Read `AGENTS.md` (binding rules; §8 design-review/evaluations discovery,
   §9 ledger discovery).
2. `scripts/truth queue` — empty means carry on.
3. `scripts/truth ready` — the unblocked work frontier.
4. Before editing any file: `scripts/truth impact <path>` — it names the
   claims your edit will stale and the work items that get HELD.

## Current focus

- **pathscope escape — FIXED** (wk-20a409b1 closed at commit 5586595, claim
  tr-d99911b4). Canonical now resolves symlinks in kernel order and fsguard
  writes only the canonical path; 4 escape variants refuse, guarded by
  `TestScopedWrite_*` in the normal suite. Residuals (open, documented):
  ADR-010 TOCTOU + symlink-swap-at-open (no O_NOFOLLOW), unscoped bundles.
- **NEXT / actionable — wk-0eaee8d9** (ADR-011 phase 1 membrane). Spec:
  `internal/runtime/docs/specs/membrane-hardening.md`. READY — re-filed on the
  five LIVE premises (old wk-dcc7a92d closed as superseded; its two diverged
  premises could not be detached). Practically gated on wk-20a409b1: fix the
  guard escape BEFORE wiring the trio.
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
  permanently HOLDs its work item even after the claim is corrected under a new
  id — no premise-detach verb exists. RESOLVED here by re-filing Phase 1 as
  wk-0eaee8d9 on the live corrections and closing wk-dcc7a92d as superseded; the
  limitation stands as real template feedback (a premise-supersede verb would
  avoid the id churn).
- Command per id, in a fresh session: `scripts/truth dispatch <id>`.

## Known repo oddities

- Session transcript archived to `docs/archive/session-transcript-2026-07.md`
  (was `docs/reference/code-review.md`; archive = gate-exempt, non-maintained).
- Template: truth-ledger v0.5.7 (copier ref `543d549`; tags upstream lag
  main — trust `.copier-answers.truth-ledger.yml`, not `git ls-remote`).
- `jsonschema` is not installed (host Python 3.14 pip is broken); drift
  detector runs via fallback.
