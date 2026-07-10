#!/usr/bin/env bash
# truth-bd-adapter.sh -- normalize `bd ready --json` (Beads) into the exact
# shape `truth ready` consumes: a JSON array of {"id", "title"} objects.
#
# WHY THIS EXISTS (read before trusting it):
#   The truth join keys only on issue["id"] and displays issue["title"]
#   (scripts/truth: join_ready). Beads is young and its `ready --json`
#   field names may differ across versions (id vs issue_id; title vs
#   summary vs name). Rather than hardcode a guess into the ledger, this
#   adapter maps whatever bd emits down to the two fields the join needs,
#   and FAILS LOUDLY if it cannot find an id -- a silent empty join would
#   let work proceed on premises nothing checked.
#
# USAGE:
#   TRUTH_TRACKER_CMD="bash scripts/truth-bd-adapter.sh" scripts/truth ready
#   # or as a pipe:
#   bash scripts/truth-bd-adapter.sh | scripts/truth ready --stdin
#
# CONTRACT: prints a JSON array to stdout, exit 0. On any failure, prints a
# diagnostic to stderr and exits non-zero so `truth ready` degrades with
# guidance instead of joining against nothing.
set -euo pipefail

BD_CMD="${TRUTH_BD_CMD:-bd ready --json}"

if ! command -v "${BD_CMD%% *}" >/dev/null 2>&1; then
  echo "truth-bd-adapter: '${BD_CMD%% *}' not found on PATH." >&2
  echo "  Install Beads (npm install -g @beads/bd) and run 'bd init', or" >&2
  echo "  point TRUTH_TRACKER_CMD at a different tracker. The ledger also" >&2
  echo "  works standalone: scripts/truth queue / list --live." >&2
  exit 127
fi

RAW="$($BD_CMD)" || { echo "truth-bd-adapter: '$BD_CMD' exited non-zero." >&2; exit 1; }

# Normalize with Python (stdlib only, same runtime the ledger already needs).
printf '%s' "$RAW" | python3 -c '
import json, sys

raw = sys.stdin.read().strip() or "[]"
try:
    data = json.loads(raw)
except json.JSONDecodeError as e:
    sys.stderr.write(f"truth-bd-adapter: bd output is not JSON ({e}).\n")
    sys.exit(1)

# bd may return a bare array, or an object wrapping one (e.g. {"issues":[...]}).
if isinstance(data, dict):
    for key in ("issues", "ready", "tasks", "results", "data"):
        if isinstance(data.get(key), list):
            data = data[key]; break
    else:
        data = [data]
if not isinstance(data, list):
    sys.stderr.write("truth-bd-adapter: expected a JSON array of issues.\n")
    sys.exit(1)

ID_KEYS    = ("id", "issue_id", "issueId", "key", "ref", "slug")
TITLE_KEYS = ("title", "summary", "name", "text", "description")

out, dropped = [], 0
for it in data:
    if not isinstance(it, dict):
        dropped += 1; continue
    iid = next((str(it[k]) for k in ID_KEYS if it.get(k) not in (None, "")), None)
    if iid is None:
        dropped += 1; continue
    title = next((str(it[k]) for k in TITLE_KEYS if it.get(k) not in (None, "")), iid)
    out.append({"id": iid, "title": title})

if dropped:
    sys.stderr.write(f"truth-bd-adapter: warning: {dropped} issue(s) had no "
                     f"recognizable id and were dropped.\n")
if not out and data:
    sys.stderr.write("truth-bd-adapter: bd returned issues but none had an id "
                     "field this adapter recognizes -- check `bd ready --json` "
                     "shape and extend ID_KEYS.\n")
    sys.exit(1)

json.dump(out, sys.stdout)
'
