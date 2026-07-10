#!/usr/bin/env bash
# spec-health: judge every feature spec by the ledger status of the ids it cites.
# Convention: .truth/README.md § Feature specs. A fact appears in a spec only
# as an id; this script is the tripwire that makes that rule pay rent.
#
# Judges cited claims by the ADR-001 matrix: live ok; unverified warns;
# cannot_verify fails P0 / warns otherwise; stale/diverged/retracted/missing
# fail. Cited issues: cancelled/missing fail. Every id cited ANYWHERE in a
# spec is tripwired (non-goals included) — refer by title to opt out.
# Zero-id specs WARN only (pre-convention legacy prose, wire when next touched).
#
# JSON travels via env vars — fine at current ledger size; revisit before the
# ledger approaches ARG_MAX (~1MB on macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CLAIMS_JSON="$(scripts/truth list --json)"
if ! ISSUES_JSON="$(scripts/truth issues --json 2>/dev/null)"; then
  echo "spec-health: 'truth issues --json' failed; treating issue records as absent (wk- ids will report missing)" >&2
  ISSUES_JSON='[]'
fi
SPEC_FILES="$(find . \( -path ./attic -o -path "*/node_modules" -o -path "*/.venv" -o -name archive \) -prune \
                   -o -type f -path "*docs/specs/*.md" -print | sort)"

export CLAIMS_JSON ISSUES_JSON SPEC_FILES

python3 - <<'PY'
import json, os, re, sys

claims = {r["id"]: r for r in json.loads(os.environ["CLAIMS_JSON"])}
issues = {r["id"]: r for r in json.loads(os.environ["ISSUES_JSON"])}

CLAIM_BAD = {"stale", "diverged", "retracted"}
ID_RE = re.compile(r"\b(?:tr|wk)-[0-9a-f]{8}\b")

failures = warnings = 0
specs = [p for p in os.environ["SPEC_FILES"].splitlines() if p.strip()]
if not specs:
    print("spec-health: no spec files found under */docs/specs/")
    sys.exit(0)

for path in specs:
    with open(path, encoding="utf-8") as f:
        ids = sorted(set(ID_RE.findall(f.read())))
    print(f"{path}")
    if not ids:
        print("  WARN  no ledger ids cited (unwired prose -- wire per the spec convention, .truth/README.md § Feature specs)")
        warnings += 1
        continue
    spec_trs = [i for i in ids if i.startswith("tr-")]
    spec_wks = [i for i in ids if i.startswith("wk-")]
    for rid in spec_trs:
        rec = claims.get(rid)
        if rec is None:
            print(f"  FAIL  {rid}  missing from ledger")
            failures += 1
            continue
        status, tier = rec["status"], rec.get("tier", "P1")
        if status in CLAIM_BAD:
            print(f"  FAIL  {rid}  {status} -- spec stands on a dead fact; renegotiate before coding")
            failures += 1
        elif status == "cannot_verify":
            if tier == "P0":
                print(f"  FAIL  {rid}  cannot_verify on a P0 fact (ADR-001: blocks)")
                failures += 1
            else:
                print(f"  WARN  {rid}  cannot_verify ({tier}) -- passes, but the ground is soft")
                warnings += 1
        elif status == "unverified":
            print(f"  WARN  {rid}  unverified -- dispatch a verifier before leaning on it")
            warnings += 1
        else:
            print(f"  ok    {rid}  {status}")
    covered = set()
    for rid in spec_wks:
        rec = issues.get(rid)
        if rec is None:
            print(f"  FAIL  {rid}  missing from ledger")
            failures += 1
            continue
        covered.update(rec.get("premises", []))
        status = rec["status"]
        if status == "cancelled":
            print(f"  FAIL  {rid}  cancelled -- spec cites a dead intention")
            failures += 1
        else:
            print(f"  ok    {rid}  {status}")
    # Ground truths not carried as premises on any cited issue are invisible
    # to `truth ready` -- only this script would catch their death.
    if spec_wks:
        for rid in sorted(set(spec_trs) - covered):
            if rid in claims:
                print(f"  WARN  {rid}  cited as ground truth but premise of no cited issue -- `truth ready` won't protect it (truth premise <wk-id> {rid})")
                warnings += 1

print(f"\nspec-health: {failures} failure(s), {warnings} warning(s) across {len(specs)} spec(s)")
sys.exit(1 if failures else 0)
PY
