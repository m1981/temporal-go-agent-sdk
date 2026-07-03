#!/usr/bin/env sh
set -eu

# Config is the single source of per-project settings. A missing or
# unreadable conf is an operator error, not a governance failure — exit 2
# (distinct from the exit 1 used for a failed check) so callers can tell
# "misconfigured" from "you broke a rule".
CONF="$(dirname "$0")/governance.conf"
if [ ! -r "$CONF" ]; then
  printf '%s\n' "✗ governance config missing or unreadable: $CONF" >&2
  printf '%s\n' "  a scripts/governance.conf must sit next to this script." >&2
  exit 2
fi
. "$CONF"

fail=0; say() { printf '%s\n' "$*" >&2; }

# GOVERNANCE_SKIP: comma-separated check numbers to skip for one commit,
# e.g. GOVERNANCE_SKIP=1,3 git commit ...
# ADR_AMEND=1 stays as the documented alias for skipping check 2.
GOVERNANCE_SKIP="${GOVERNANCE_SKIP:-}"
if [ "${ADR_AMEND:-0}" = "1" ]; then
  GOVERNANCE_SKIP="${GOVERNANCE_SKIP:+$GOVERNANCE_SKIP,}2"
fi
skip() { case ",$GOVERNANCE_SKIP," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

STAGED=$(git diff --cached --name-only --diff-filter=ACMR)
[ -z "$STAGED" ] && exit 0

# ── 1: dead names in added lines (skipped while DEAD_NAMES empty) ──
if ! skip 1 && [ -n "$DEAD_NAMES" ]; then
  for f in $STAGED; do
    echo "$f" | grep -Eq "$EXEMPT_PATHS" && continue
    case "$f" in *.md|*.py|*.ts|*.js|*.toml|*.json|*.yaml|*.yml) ;; *) continue ;; esac
    hits=$(git diff --cached -U0 -- "$f" | grep -E '^\+' | grep -Ev '^\+\+\+' \
           | grep -En "$DEAD_NAMES" || true)
    [ -n "$hits" ] && { say "✗ retired name added in $f:"; say "$hits"; fail=1; }
  done
fi

# ── 2: ADR immutability (alias: ADR_AMEND=1, i.e. skip 2) ────────────
if ! skip 2; then
  mods=$(git diff --cached --name-only --diff-filter=M \
         | grep -E '(^|/)adr/[0-9]{3}-' || true)
  [ -n "$mods" ] && { say "✗ accepted ADR modified — supersede instead:";
    say "$mods"; say "  conscious amend: ADR_AMEND=1 git commit ..."; fail=1; }
fi

# ── 3: new-doc three-question gate ──────────────────────────────────
if ! skip 3; then
  news=$(git diff --cached --name-only --diff-filter=A | grep '\.md$' || true)
  for f in $news; do
    echo "$f" | grep -Eq "$EXEMPT_PATHS" && continue
    echo "$f" | grep -Eq "$GATE_EXEMPT_NAMES" && continue
    ok=1
    for k in 'Reader:' 'Enables:' 'Update-trigger:'; do
      git show ":$f" | head -15 | grep -q "$k" || ok=0
    done
    [ $ok -eq 1 ] || { say "✗ new doc $f lacks header:";
      say "  > Reader: <who> | Enables: <what> | Update-trigger: <event>";
      say "  Can't answer all three? Don't write the doc."; fail=1; }
  done
fi

# ── 4: typed READMEs keep their header ──────────────────────────────
if ! skip 4; then
  for f in $STAGED; do
    for r in $TYPED_READMES; do
      [ "$f" = "$r" ] || continue
      git show ":$f" | head -8 | grep -q '> Type:' \
        || { say "✗ $f lost its '> Type: ...' header"; fail=1; }
    done
  done
fi

[ $fail -eq 0 ] || { say ""; say "governance checks failed."; exit 1; }
exit 0
