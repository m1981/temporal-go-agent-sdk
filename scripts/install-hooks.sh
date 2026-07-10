#!/usr/bin/env bash
# Wires local git hooks. Local hooks don't survive clones -- if your team
# can't rely on that, use the CI equivalents instead (one of the two MUST
# exist): a job running scripts/check-truth.sh on PRs touching the ledger,
# and a job running `scripts/truth invalidate-scan --quiet` after merges.
set -euo pipefail
# If core.hooksPath points elsewhere (husky, lefthook, .githooks), hooks
# written to .git/hooks are DEAD FILES -- refuse to pretend otherwise.
HOOKS_PATH="$(git config core.hooksPath || true)"
if [ -n "$HOOKS_PATH" ]; then
  echo "install-hooks: core.hooksPath=$HOOKS_PATH is set; .git/hooks would never run." >&2
  echo "  Wire the truth hooks into your hook manager instead, e.g. add to" >&2
  echo "  $HOOKS_PATH/pre-commit:   bash scripts/check-truth.sh" >&2
  echo "  $HOOKS_PATH/post-merge:   python3 scripts/truth invalidate-scan --quiet" >&2
  exit 1
fi
HOOK_DIR="$(git rev-parse --git-dir)/hooks"
cat > "$HOOK_DIR/pre-commit" <<'HOOK'
#!/usr/bin/env bash
exec bash scripts/check-truth.sh
HOOK
cat > "$HOOK_DIR/post-merge" <<'HOOK'
#!/usr/bin/env bash
python3 scripts/truth invalidate-scan --quiet
HOOK
chmod +x "$HOOK_DIR/pre-commit" "$HOOK_DIR/post-merge"
echo "hooks installed: pre-commit, post-merge"
