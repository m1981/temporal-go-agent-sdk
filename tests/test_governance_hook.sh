#!/usr/bin/env sh
# test_governance_hook.sh — asserts scripts/check-governance.sh behavior.
#
# Plain POSIX sh, no framework. Builds a throwaway git repo per assertion,
# wires in this project's scripts/check-governance.sh + scripts/governance.conf,
# stages a scenario, runs the hook, and checks the exit code.
#
# Run from the project root or from tests/:  sh tests/test_governance_hook.sh
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
HOOK="$ROOT/scripts/check-governance.sh"
CONF="$ROOT/scripts/governance.conf"

[ -r "$HOOK" ] || { echo "cannot read $HOOK" >&2; exit 2; }
[ -r "$CONF" ] || { echo "cannot read $CONF" >&2; exit 2; }

fails=0
pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s (%s)\n' "$1" "$2"; fails=$((fails + 1)); }
check() { # desc, expected, actual
  if [ "$2" = "$3" ]; then pass "$1"; else fail "$1" "expected $2, got $3"; fi
}

# Build a fresh temp git repo wired with the hook + conf. Echoes its path.
mk_repo() {
  d=$(mktemp -d 2>/dev/null || mktemp -d -t govtest)
  mkdir -p "$d/scripts"
  cp "$HOOK" "$d/scripts/check-governance.sh"
  cp "$CONF" "$d/scripts/governance.conf"
  ( cd "$d" \
      && git init -q \
      && git config user.email test@example.com \
      && git config user.name test \
      && git config commit.gpgsign false )
  printf '%s' "$d"
}

# Run the hook inside repo $1 with optional env prefix $2. Echoes exit code.
run_hook() {
  ( cd "$1" && eval "${2:-} sh scripts/check-governance.sh" >/dev/null 2>&1; echo $? )
}

# 1) headerless new .md → blocked (exit 1)
r=$(mk_repo)
printf '# just a title\nno governance header here\n' > "$r/notes.md"
( cd "$r" && git add notes.md )
check "headerless new .md is blocked" 1 "$(run_hook "$r")"
rm -rf "$r"

# 2) headered new .md → allowed (exit 0)
r=$(mk_repo)
printf '> Reader: me | Enables: a decision | Update-trigger: an event\n\n# doc\n' > "$r/notes.md"
( cd "$r" && git add notes.md )
check "headered new .md is allowed" 0 "$(run_hook "$r")"
rm -rf "$r"

# 3) modifying an accepted ADR → blocked (exit 1)
r=$(mk_repo)
mkdir -p "$r/docs/adr"
printf '# ADR-001\nStatus: Accepted\n' > "$r/docs/adr/001-thing.md"
( cd "$r" && git add docs/adr/001-thing.md && git commit -qm 'add adr' )
printf 'sneaky edit\n' >> "$r/docs/adr/001-thing.md"
( cd "$r" && git add docs/adr/001-thing.md )
check "modifying an accepted ADR is blocked" 1 "$(run_hook "$r")"
rm -rf "$r"

# 4) GOVERNANCE_SKIP=3 lets a headerless .md through (exit 0)
r=$(mk_repo)
printf '# headerless on purpose\n' > "$r/notes.md"
( cd "$r" && git add notes.md )
check "GOVERNANCE_SKIP=3 skips the doc gate" 0 "$(run_hook "$r" 'GOVERNANCE_SKIP=3')"
rm -rf "$r"

# 5) missing governance.conf → exit 2 (distinct from a governance failure)
r=$(mk_repo)
rm -f "$r/scripts/governance.conf"
printf 'anything\n' > "$r/notes.md"
( cd "$r" && git add notes.md )
check "missing conf exits 2" 2 "$(run_hook "$r")"
rm -rf "$r"

if [ "$fails" -eq 0 ]; then
  echo "ALL GOVERNANCE HOOK TESTS PASSED"
  exit 0
else
  echo "$fails governance hook test(s) FAILED"
  exit 1
fi
