# ADR-025: doctor decides the hook-or-CI commit-gate MUST, and the invariant table discloses commit-gate conditionality (H6)

Status: Accepted (2026-07-19, operator) — spec-precision + a decidable-check
improvement from batch-2 review finding H6, re-verified against v0.9.7 in a
sandbox before adoption. Behavior change: `doctor` now passes a CI-only repo
whose CI config names the gate script (previously a false FAIL). Implemented
in CLI v0.9.8. Core tests test_ci_gate_names_detects_and_misses; canary FAULT
DG (doctor decides hook-or-CI). Amends the invariant table's INV-A/INV-G/INV-N
rows and §8 item 5.
Date: 2026-07-19
Supersedes: — (makes an existing behavioral MUST decidable; discloses a
conditionality the invariant table left implicit)

## Context

Finding H6 observed that the README's one **MUST** — "run
`install-hooks.sh` … or use CI instead — one of the two MUST exist" — is
enforced by no automatic mechanism, and that the invariant table lists the
commit-gate-dependent invariants (INV-A append-only prefix gate, INV-G
retraction terminality via commit-time duplicate-id detection, INV-N
issue-fold protection, and every ADR-008/ADR-016 order detection) as if
they were unconditionally active. Sandbox re-verification confirmed the
blast radius is real, not theoretical: in a repo with no installed hook, an
**in-place rewrite of a committed ledger line committed successfully** —
INV-A silently void, because the prefix gate never ran. `truth claim` also
files happily with no gate present.

`doctor` is the intended check (README step 5, "installation must pass";
§6.3, "doctor checks the installation"), and in code it **does** fail
(exit 1) when no executable `check-truth` pre-commit hook is found in the
*effective* hooks dir (it reads `core.hooksPath`, so it catches the
"file exists but is not active" case). But two gaps made H6 valid:

1. **The spec never states doctor's pass/fail condition.** "Checks the
   installation" does not say doctor *fails* without the gate — so the
   decidable behavior the code already has was undocumented.
2. **doctor could see only the hook arm.** It has no CI detection, so a
   repo correctly gated by CI (the README's explicit alternative) got
   `doctor: FAIL`. A health check that false-fails a valid configuration
   teaches its operator to ignore it — the worst outcome for the one
   mechanism meant to decide the MUST.

3. **The conditionality was disclosed only generically.** §8 item 5
   ("agent compliance is behavioral… a runtime that never loads them
   bypasses everything") names the limit but not *which invariants* it
   voids; the invariant table presents those gates as absolute.

## Decision

**1. doctor decides both arms of the MUST.** When no local `check-truth`
(resp. `invalidate-scan`) hook is found, doctor now greps the known CI
configs for the gate script name: the **top-level `*.yml`/`*.yaml`** files
under `.github/workflows/` and `.woodpecker/` — *exactly* what those CIs
execute, so a `disabled/` subdirectory or a `truth.yml.disabled` rename
(gates the CI never runs — an operator's "off" switch) does **not** count —
plus the top-level configs `.gitlab-ci.yml`, `.circleci/config.yml`,
`azure-pipelines.yml`, `Jenkinsfile`, `.drone.yml`,
`bitbucket-pipelines.yml`, `.woodpecker.yml`, `.travis.yml`,
`.buildkite/pipeline.yml`. A match passes the arm (reported "via CI — not
locally verifiable"); neither hook nor CI reference fails it (exit 1). The
scan is read-guarded, so an unreadable or directory-shaped candidate makes
doctor *report*, not traceback. This is best-effort with the
**same rigor as the discovery-snippet grep**: a CI file naming the gate is
evidence it runs, exactly as `scripts/truth` in `AGENTS.md` is evidence the
layer is discoverable — not proof the pipeline fires on the right events,
and not a completeness claim (a homegrown CI path doctor does not know is a
disclosed residual, mitigated by: name the gate script in a file doctor
greps, or install the hook). The CI arm is self-certified — doctor cannot
run the pipeline — and says so.

**2. The spec states doctor's decidable condition.** README step 5 and the
paper's §6.3 doctor note now say: `doctor` FAILS (exit 1) unless, for each
gate, an active `check-truth`/`invalidate-scan` hook OR a CI config naming
it exists. This makes the README's sole MUST decidable by one command.

**3. The invariant table discloses commit-gate conditionality.** INV-A,
INV-G, INV-N, and the ADR-008/016 detection notes now state they hold *only
where the commit gate runs* (installed hook or CI naming the gate; `doctor`
decides it), and that where neither exists the invariant is unenforced —
the specific, named blast radius of §8 item 5, which is cross-referenced.

## Consequences

- The one MUST is now decidable by `truth doctor`, and a CI-only repo is a
  first-class configuration instead of a false FAIL.
- The invariant table no longer overstates: commit-gate invariants are
  labelled conditional, honestly matching that the gate is host-installed.
- No new runtime refusal: `truth claim`/`done` still do not check the gate
  (deliberate — bootstrapping files claims before hooks are wired; doctor
  is the check). This is stated, not silent.
- Locked mechanically: core `test_ci_gate_names_detects_and_misses` (a
  top-level workflow naming the gate is found; an unrelated file is not)
  and `test_ci_gate_names_top_level_yaml_only` (a subdir / `.disabled`
  workflow is NOT found); canary FAULT DG, four arms — a bare repo FAILs
  (exit 1); a subdir-only workflow still FAILs; a top-level CI naming BOTH
  `check-truth` AND `invalidate-scan` PASSes both arms at exit 0 (the arm
  asserts the INV-C-via-CI line too, so a broken post-merge arm is caught —
  an H6 adversarial finding); a directory-shaped hook path does not
  traceback.

## Non-goals

Not verifying the CI pipeline actually runs (undecidable from config text;
self-certified, same class as the discovery grep and TRUTH_HUMAN). Not
adding an operation-time refusal or warning to `truth claim`/`done` (the
operator chose doctor as the check; a per-operation warning was considered
and declined as noise). Not claiming the CI-file list is complete (a
disclosed residual).
