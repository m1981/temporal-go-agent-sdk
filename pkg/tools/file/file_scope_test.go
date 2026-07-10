package file

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/fsguard"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/pathscope"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Acceptance (wk-93dc3566): a write resolving outside the workspace root is
// refused with ErrOutsideWorkspace and the file is NOT created.
func TestScopedWrite_OutsideWorkspace_RefusedAndNotCreated(t *testing.T) {
	root := t.TempDir()
	outside := filepath.Join(t.TempDir(), "evil.txt")

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": outside, "content": "pwned"})
	assert.ErrorIs(t, err, pathscope.ErrOutsideWorkspace)

	_, statErr := os.Stat(outside)
	assert.True(t, os.IsNotExist(statErr), "a refused write must not create the file")
}

// The scope check runs BEFORE the guard: an existing unread file outside the
// workspace is refused as out of scope, not as unread.
func TestScopedWrite_OutsideWorkspace_ScopeCheckedBeforeGuard(t *testing.T) {
	root := t.TempDir()
	outside := filepath.Join(t.TempDir(), "existing.txt")
	require.NoError(t, os.WriteFile(outside, []byte("original"), 0o644))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": outside, "content": "pwned"})
	assert.ErrorIs(t, err, pathscope.ErrOutsideWorkspace)
	assert.NotErrorIs(t, err, fsguard.ErrNotRead, "out-of-scope must be decided before freshness")

	b, _ := os.ReadFile(outside)
	assert.Equal(t, "original", string(b), "a refused write must not touch the file")
}

// read_file is bounded too: an out-of-scope file is refused before any
// filesystem access, so its contents never reach the model and it is never
// marked as read.
func TestScopedRead_OutsideWorkspace_Refused(t *testing.T) {
	root := t.TempDir()
	outside := filepath.Join(t.TempDir(), "secret.txt")
	require.NoError(t, os.WriteFile(outside, []byte("secret-data"), 0o644))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	out, err := tools.Reader().Execute(ctx(), map[string]any{"path": outside})
	assert.ErrorIs(t, err, pathscope.ErrOutsideWorkspace)
	assert.Nil(t, out)
}

// The symlink escape is caught through the tool surface, not just the scope
// unit: a write through an in-workspace symlink dir pointing outside lands
// nothing outside.
func TestScopedWrite_SymlinkEscape_RefusedAndNotCreated(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	require.NoError(t, os.Symlink(outside, filepath.Join(root, "escape")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{
		"path": filepath.Join(root, "escape", "pwned.txt"), "content": "pwned",
	})
	assert.ErrorIs(t, err, pathscope.ErrOutsideWorkspace)

	_, statErr := os.Stat(filepath.Join(outside, "pwned.txt"))
	assert.True(t, os.IsNotExist(statErr), "nothing may be created outside the workspace")
}

// Inside the workspace the scoped bundle behaves exactly like the unscoped
// one: create, read, then overwrite all work, sharing one guard.
func TestScoped_InsideWorkspace_FullReadWriteCycle(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "notes.txt")

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "v1"})
	require.NoError(t, err)

	out, err := tools.Reader().Execute(ctx(), map[string]any{"path": path})
	require.NoError(t, err)
	assert.Equal(t, "v1", out)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "v2"})
	require.NoError(t, err)

	b, _ := os.ReadFile(path)
	assert.Equal(t, "v2", string(b))
}

// Inside the workspace the freshness guard still applies: scoping does not
// weaken the read-before-write invariant.
func TestScoped_InsideWorkspace_GuardStillEnforced(t *testing.T) {
	root := t.TempDir()
	path := filepath.Join(root, "main.go")
	require.NoError(t, os.WriteFile(path, []byte("original"), 0o644))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "overwrite"})
	assert.ErrorIs(t, err, fsguard.ErrNotRead)
}
