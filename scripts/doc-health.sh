#!/usr/bin/env bash
# doc-health: judge the live markdown corpus for the two measured decay modes
# of agent-maintained prose — forbidden name patterns (things that were
# renamed but live on in docs) and broken relative links. Sibling of
# spec-health.sh: that script judges cited ledger ids; this one judges the
# prose fabric around them.
#
# Scope: git-tracked *.md only. History is exempt — any path containing an
# archive/, archived/, attic/, adr/, or freeze/ segment, and CHANGELOG files:
# old names and dead paths are the POINT there. Convention for citing rename
# ADRs from live docs without spelling the dead name: wildcard the filename
# (docs/adr/NNN-*.md).
#
# Checks:
#   A  forbidden name patterns, one regex per line (case-insensitive) in the
#      optional scripts/doc-health.patterns ('#' comments allowed). No file,
#      no check — the link check still runs.
#   B  relative markdown links whose target does not exist (anchors stripped;
#      http/mailto/anchor-only/wildcard targets skipped).
# Backtick path mentions are deliberately NOT checked — shorthand like
# `pkg/module.py` is endemic and legitimate; links are the load-bearing refs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FILES="$(git ls-files '*.md' | grep -vE '(^|/)(archive|archived|attic|adr|freeze)/' | grep -vE '(^|.*)CHANGELOG' || true)"
PATTERNS=""
if [ -f scripts/doc-health.patterns ]; then
  PATTERNS="$(grep -v '^[[:space:]]*#' scripts/doc-health.patterns | grep -v '^[[:space:]]*$' || true)"
else
  echo "doc-health: no scripts/doc-health.patterns -- name-pattern check skipped (link check still runs)" >&2
fi

export FILES PATTERNS

python3 - <<'PY'
import os, re, sys
from pathlib import Path

patterns = [re.compile(p, re.IGNORECASE) for p in os.environ["PATTERNS"].splitlines() if p.strip()]
LINK = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)\)')

failures = 0
files = [f for f in os.environ["FILES"].splitlines() if f.strip()]
for f in files:
    text = Path(f).read_text(encoding="utf-8")
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for pat in patterns:
            m = pat.search(line)
            if m:
                hits.append(f"  FAIL  forbidden name '{m.group(0)}' (line {i}) -- listed in scripts/doc-health.patterns; if citing a rename ADR, wildcard the filename (docs/adr/NNN-*.md)")
        for lm in LINK.finditer(line):
            target = lm.group(1).split('#', 1)[0]
            if not target or '://' in target or target.startswith('mailto:') or '*' in target:
                continue
            # leading / means repo-root-relative
            resolved = Path(target.lstrip('/')) if target.startswith('/') else Path(f).parent / target
            if not resolved.exists():
                hits.append(f"  FAIL  broken link '{lm.group(1)}' (line {i}) -- target missing")
    if hits:
        print(f)
        print("\n".join(hits))
        failures += len(hits)

print(f"doc-health: {failures} failure(s) across {len(files)} live doc(s)")
sys.exit(1 if failures else 0)
PY
