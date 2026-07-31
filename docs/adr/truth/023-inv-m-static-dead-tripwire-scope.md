# ADR-023: INV-M is a static-dead-tripwire gate, not a liveness guarantee — globs are dormant, the symlink is the residual (H5)

Status: Accepted (2026-07-19, operator) — spec-precision from batch-2 review
finding H5, re-verified against v0.9.7 in a sandbox before adoption. Zero
behavior change; amends the wording of INV-M (Appendix A of the paper),
its §1 intake summary, and the residual note. Implemented (as prose +
mechanical locks) in CLI v0.9.8. Core tests
test_empty_glob_is_dormant_not_dead, test_dead_literal_is_the_decidable_case;
canary FAULT T gains a dormant-glob-materializes arm.
Date: 2026-07-19
Supersedes: — (sharpens ADR-nothing; restates an invariant's guarantee to
match what its gate actually decides)
Amended by: ADR-024 (2026-07-19). This ADR's "over the `*`/`?`/`**` glob
language no glob is permanently unmatchable" and "the tracked symlink is
the lone residual" OVERCLAIM — an adversarial verifier found
statically-unreachable globs (`.git/*`, `/etc/*.conf`, `zone/*/`,
`../*.txt`, `dbl//*.txt`) that are exempt yet can never fire, and the
completion claim tr-fe1169f4 diverged for it. ADR-024 refuses those at
intake and corrects the wording. The dormant-glob result below (a glob
over a REACHABLE namespace fires when it fills) stands unchanged.

## Context

Finding H5 argued that INV-M's stated guarantee — "every `evidence_path`
matches ≥1 tracked file at filing time, **or is an explicit glob**" — does
not entail the property INV-M's falsifier names ("one accepted claim whose
tripwire can never fire"), because the glob exemption admits a glob
matching zero files (e.g. `src/ghost/*.py`) that, the finding claimed,
"can never fire." The symlink residual was cited as a second instance.

The meta-point is correct and worth pinning: the **gate** decides a
*weaker* property than the **invariant** was worded to claim. But the
specific new instance was re-verified in a sandbox against the real CLI,
and the sandbox **refuted** it:

- **An empty glob is dormant, not dead.** A claim filed with
  `--paths "src/ghost/*.py"` against a tree where `src/ghost/` holds no
  `.py` file is accepted (glob-exempt). When `src/ghost/appeared.py` is
  later created, tracked, and diffed against the claim's anchor,
  `invalidate-scan` marks the claim `stale (paths changed)`. It **fires.**
  The reason is structural: `dead_literal_paths` checks literal membership
  only at *filing* time, but the invalidator `_evidence_paths_touched`
  re-runs `match_paths` against *every scan's* diff. A glob is therefore a
  standing watch on a **namespace**, not a frozen file-set. Over the
  screen's glob language (`*`/`?`/`**`, where `*`/`?` stop at `/`), there
  is no syntactically-valid glob that is permanently unmatchable, so an
  exempted glob is never permanently dead — only dormant until its
  namespace is populated.

- **The tracked symlink is permanently dead, and is the lone residual.** A
  literal `--paths "link.txt"` where `link.txt` is a tracked symlink passes
  intake (git tracks the link, so it is a real tracked file), but editing
  the pointed-at `target.txt` produces **0 stale** — the diff shows
  `target.txt`, never `link.txt`, because git tracks the immutable link
  object (mode `120000`), not the target. This case *can* falsify INV-M's
  liveness falsifier, and it was already acknowledged by inspection
  (meta-repo, 2026-07-13).

So the honest correction is the inverse of the finding's proposal: do not
treat the empty glob as a leak (it is sound-by-design), and do restate
INV-M to describe the property its gate actually decides.

## Decision

**Restate INV-M as a *static-dead-tripwire* gate, not a liveness
guarantee.** The gate decides one decidable property at filing time: no
`evidence_path` entry is *statically* dead — specifically it refuses (a) a
whitespace-containing entry with no comma (a forgotten-comma literal that
matches nothing) and (b) a **literal** (non-glob) path matching zero
tracked files (a literal has exactly one referent; if that referent is not
tracked, its tripwire can never fire). It makes **no** claim that every
accepted tripwire *can* fire. Two cases lie outside what the gate decides,
and the spec now names both explicitly:

1. **Globs are dormant watches, sound by design.** A glob matching nothing
   yet is legitimate intent; it fires when its namespace is populated
   (verified). It is never permanently dead, so it is correctly exempt —
   this is a feature, not a residual.
2. **A tracked symlink literal is the residual.** It passes the
   file-existence check yet is permanently dead. Mitigation stays
   guidance ("watch real paths"), not a gate — deciding it would require
   resolving link targets at intake, and the class has not recurred.

No CLI behavior changes: `dead_literal_paths` already exempts globs and
refuses zero-match literals exactly as this ADR describes; the invalidator
already re-evaluates globs per scan. This ADR changes *wording and
mechanical locks*, so that the invariant is stated as strong as what it
enforces — no stronger.

## Consequences

- INV-M's paper row, §1 intake summary, residual note, the template
  README, and the tutorial are reworded to say the gate refuses *static*
  dead tripwires (comma-typo and zero-match **literals**), that globs are
  dormant-not-dead (they fire when the namespace fills), and that the
  tracked symlink is the one permanent residual.
- Locked mechanically: core `test_empty_glob_is_dormant_not_dead` (a glob
  is exempt at intake *and* its invalidator fires once a matching file
  appears — the exact fact that refutes "an empty glob can never fire"),
  core `test_dead_literal_is_the_decidable_case` (a zero-match literal is
  refused, a glob is not); canary `FAULT T` gains an arm that files an
  empty-glob claim, materializes the namespace, and asserts the claim goes
  stale.
- The refuted half of H5 is recorded here so a future reader does not
  re-raise "an empty glob can never fire" — the sandbox says it does.

## Non-goals

Not adding any gate for the symlink residual (guidance only, unchanged).
Not refusing zero-match globs (they are dormant, not dead — refusing them
would break the legitimate "watch a not-yet-created file" intent). Not
claiming INV-M now guarantees liveness — it guarantees the absence of
*static* dead tripwires, and the symlink residual is why liveness stays
unclaimed.
