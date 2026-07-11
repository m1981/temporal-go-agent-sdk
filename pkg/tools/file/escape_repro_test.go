package file

// Regression guard for wk-20a409b1 (P0): a symlink inside the workspace root
// followed by ".." used to escape the scope. pathscope.Check canonicalized the
// path through filepath.Abs, which cleans ".." LEXICALLY (so
// "<root>/link/../pwned" was judged as in-root "<root>/pwned" and approved),
// while fsguard.CommitWrite wrote the ORIGINAL, un-cleaned path, where the
// kernel resolves link -> outside FIRST and ".." after — landing the bytes
// OUTSIDE the root.
//
// Fixed by (1) fsguard.OSFilesystem.Canonical resolving component-by-component
// in kernel order (symlinks before ".."), and (2) fsguard's Guard performing
// all filesystem I/O on that canonical path, so the location pathscope
// approves is exactly the location written.
//
// The escape paths are built by raw string concatenation on purpose:
// filepath.Join would clean the ".." away before the tool ever saw it, hiding
// the regression.

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/pathscope"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// rawJoin concatenates path segments without any lexical cleaning, so ".."
// survives all the way to the tool (and, if the guard ever regresses, to the
// syscall).
func rawJoin(segs ...string) string {
	out := segs[0]
	for _, s := range segs[1:] {
		out += string(os.PathSeparator) + s
	}
	return out
}

// requireRefusedOutside asserts the write was refused as out-of-workspace and
// that no file appeared at the location the kernel would have resolved the
// raw path to.
func requireRefusedOutside(t *testing.T, execErr error, landed string) {
	t.Helper()
	if b, statErr := os.ReadFile(landed); statErr == nil {
		t.Fatalf("ESCAPE: scoped write landed at %s = %q, outside the root (Execute err=%v)",
			landed, string(b), execErr)
	}
	require.ErrorIs(t, execErr, pathscope.ErrOutsideWorkspace,
		"a write resolving outside the workspace root must be refused as out of scope")
}

// Original repro: "<root>/link" -> a SIBLING directory outside the root;
// "<root>/link/../pwned" kernel-resolves to the sibling's parent (the temp
// dir), outside the root.
func TestScopedWrite_SymlinkThenDotDot_Refused(t *testing.T) {
	tmp := t.TempDir()
	root := filepath.Join(tmp, "work")
	outside := filepath.Join(tmp, "outside")
	require.NoError(t, os.MkdirAll(root, 0o755))
	require.NoError(t, os.MkdirAll(outside, 0o755))
	require.NoError(t, os.Symlink(outside, filepath.Join(root, "link")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	escapePath := rawJoin(root, "link", "..", "pwned")
	_, execErr := tools.Writer().Execute(context.Background(),
		map[string]any{"path": escapePath, "content": "PWNED"})

	resolvedTmp, rerr := filepath.EvalSymlinks(tmp)
	require.NoError(t, rerr)
	requireRefusedOutside(t, execErr, filepath.Join(resolvedTmp, "pwned"))
	requireRefusedOutside(t, execErr, filepath.Join(tmp, "pwned"))
}

// Stronger reviewer variant: an UPWARD symlink "<root>/a/b/link" -> <root>
// followed by ".." resolves ABOVE the root entirely ("<root>/.." — the
// machine temp area), so the bytes would land at the root's PARENT.
func TestScopedWrite_UpwardSymlinkThenDotDot_Refused(t *testing.T) {
	root := t.TempDir()
	require.NoError(t, os.MkdirAll(filepath.Join(root, "a", "b"), 0o755))
	require.NoError(t, os.Symlink(root, filepath.Join(root, "a", "b", "link")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	escapePath := rawJoin(root, "a", "b", "link", "..", "pwned-above")
	_, execErr := tools.Writer().Execute(context.Background(),
		map[string]any{"path": escapePath, "content": "PWNED"})

	resolvedRoot, rerr := filepath.EvalSymlinks(root)
	require.NoError(t, rerr)
	requireRefusedOutside(t, execErr, filepath.Join(filepath.Dir(resolvedRoot), "pwned-above"))
	requireRefusedOutside(t, execErr, filepath.Join(filepath.Dir(root), "pwned-above"))
}

// INTERMEDIATE symlink: the link sits in the middle of the path with real
// components after it. "<root>/a/link/deep/../pwned" must resolve the link
// (to outside) before the trailing ".." is applied — the write lands nowhere.
func TestScopedWrite_IntermediateSymlinkThenDotDot_Refused(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	require.NoError(t, os.MkdirAll(filepath.Join(outside, "deep"), 0o755))
	require.NoError(t, os.MkdirAll(filepath.Join(root, "a"), 0o755))
	require.NoError(t, os.Symlink(outside, filepath.Join(root, "a", "link")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	escapePath := rawJoin(root, "a", "link", "deep", "..", "pwned-mid")
	_, execErr := tools.Writer().Execute(context.Background(),
		map[string]any{"path": escapePath, "content": "PWNED"})

	resolvedOutside, rerr := filepath.EvalSymlinks(outside)
	require.NoError(t, rerr)
	requireRefusedOutside(t, execErr, filepath.Join(resolvedOutside, "pwned-mid"))
	requireRefusedOutside(t, execErr, filepath.Join(outside, "pwned-mid"))
}

// Control: a symlink that stays INSIDE the root must still be usable — the
// fix bounds symlinks, it does not ban them. A create through an in-root
// symlinked dir succeeds and lands at the link's in-root target.
func TestScopedWrite_InRootSymlink_StillAllowed(t *testing.T) {
	root := t.TempDir()
	realDir := filepath.Join(root, "real")
	require.NoError(t, os.MkdirAll(realDir, 0o755))
	require.NoError(t, os.Symlink(realDir, filepath.Join(root, "alias")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(context.Background(), map[string]any{
		"path": filepath.Join(root, "alias", "notes.txt"), "content": "hello",
	})
	require.NoError(t, err, "a symlink resolving inside the root must remain writable")

	b, err := os.ReadFile(filepath.Join(realDir, "notes.txt"))
	require.NoError(t, err)
	assert.Equal(t, "hello", string(b), "the write lands at the link's in-root target")
}
