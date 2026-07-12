# RESUME — session entry point

Facts live in the ledger, not here: this file carries only ids and commands
(citation over restatement). Update at the end of every substantive session
(charter §7). Last updated: 2026-07-12. HEAD at handoff: d26ab5c.

## Bootstrap (30 seconds)

1. Read `AGENTS.md` (binding rules; §8 design-review/evaluations, §9 ledger).
2. `scripts/truth ready` — THE authoritative plan (open ∧ deps closed ∧
   premises live). The task tool, if any, only mirrors this.
3. `scripts/truth queue` — what needs a verifier's attention.
4. Before editing a file: `scripts/truth impact <path>` — names the claims your
   edit will stale and the work it will HOLD.

## Regime (how work is planned here)

- The **ledger is the plan.** `truth ready` is authoritative; `truth start
  wk-…` a work item before dispatching it; `truth done wk-… --claim` on finish.
- **Single ledger writer** when sessions run concurrently (append-race safety):
  the orchestrating session files claims/verdicts; others hand it the text.
- **No self-verify.** The session that files/authors a claim must not verify it;
  route to a fresh session (`truth dispatch <id>`).
- Template: truth-ledger `e1647e2` (v0.5.7+; `.copier-answers.truth-ledger.yml`).
  Use `copier update --vcs-ref=HEAD` (NOT `copier copy` — it needs a tty).
  New gates live: quantifier/scope intake (`--scope-ok`), evidence allowlist
  `.truth/evidence-allow` (`--evidence-unsafe-ok`), backdating detection,
  `diverge --mechanical`. Canary is 80 faults.

## Done (shipped + closed)

fsguard/pathscope/file guard layer (ADR-007..010); the **pathscope+fsguard
symlink escape FIXED** (wk-20a409b1, commit 5586595, kernel-order symlink
resolution + canonical-path I/O; regression guard `TestScopedWrite_*`);
**Phase 1a membrane** changes 1–4 (wk-0eaee8d9, commit 8332e65: typed
tool-result envelope, static model-facing errors, panic-recover + per-tool
timeout, uuid SideEffect); three SDK evaluations → ADR-011 + AP/PR checklist
+ PAT registry + `docs/evaluations/`; truth-ledger installed and upgraded.

## Authoritative frontier (from `truth ready`, 2026-07-12)

READY now (no coupling → quick wins first):
- **wk-92a000e0** — extend static errors to 2 sub-agent sites (AP-05;
  temporal agent_workflow.go:1544, local agent_loop.go:635). Small.
- **wk-8468e36a** — P2 guard-tools hardening (read_file size cap,
  CreateExclusive cleanup on write-error, pathscope case-fold). Small.
- **wk-ceaabb07** — Phase 1b: wire guard trio + Snapshot into runtime
  (architectural; COUPLES with Phase 2 — wiring before convergence = rework).
- **wk-7baee278** — Phase 4 platform hygiene.
- **wk-e97339d3** — DECISION: ADR namespace collision (see below).

HELD:
- **wk-39850a5b** — Phase 2 (converge dual loop). Premise tr-e1d73540 STALE
  (Phase 1a edited both loops). Still TRUE (both loops exist) → needs
  RE-VERIFICATION (verifier session), then Phase 2 unblocks.
- **wk-0bdbd4e4** — Phase 3, deps on Phase 2.

## Verification debt (verifier session only — `scripts/truth queue`)

11 stale/diverged claims await re-dispatch; all still true (suites green),
mechanically staled by fix/membrane commits. Priority: **tr-e1d73540**
(unblocks Phase 2). Then the Phase-1a completions (tr-97c678ec, tr-e8195632,
tr-fdc3a4bb, tr-f4c87e4e), fix completion tr-d99911b4, sub-agent finding
tr-33b577c9 (premise of wk-92a000e0), and the earlier fsguard-spec set.
`truth dispatch <id>` in a fresh session; that clears `spec-health` red too.
(tr-8f969e5d / tr-3ef6f8ff are stale-because-FIXED — leave them, historical.)

## Open decisions / oddities

- **wk-e97339d3 (ADR collision):** template ledger ADRs 007-012 now clash by
  number with project ADRs 007-011. Cannot renumber ours (immutable ledger
  refs); template re-adds 0NN each update. Needs a template-side convention
  (LADR-NNN / docs/adr/ledger/). Safe interim: relocate the (not-README-linked)
  template ADR files to docs/adr/ledger/.
- **Phase 1b vs Phase 2 sequencing:** recommend Phase 2 FIRST (converge, then
  wire once), but Phase 2 is HELD on re-verification — so quick wins
  (wk-92a000e0, wk-8468e36a) are the clean next dispatch meanwhile.
- Sub-agent residual (tr-33b577c9) and P2s are honest follow-ons to shipped work.
- `jsonschema` not installed (host Python 3.14 pip broken); drift detector
  runs via fallback — install on a working interpreter to fully arm it.
- Transcript archived at `docs/archive/session-transcript-2026-07.md`.
