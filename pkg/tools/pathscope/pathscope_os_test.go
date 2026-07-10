package pathscope

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Real-disk integration tests: the fake-backed unit tests prove the boundary
// math; these prove the OS canonicalization actually feeds that math the
// resolved locations — most importantly for the symlink-escape vector, which
// only a real symlink can demonstrate end to end.
//
// Note t.TempDir on macOS lives under /var (a symlink to /private/var), so
// these also exercise root canonicalization in NewOS for real.

// A symlinked DIRECTORY inside the workspace pointing outside it must not
// grant access to targets spelled through it — including a not-yet-existing
// file, whose parent (the symlink) is what gets resolved.
func TestOS_SymlinkDirEscape_Refused(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	require.NoError(t, os.Symlink(outside, filepath.Join(root, "escape")))

	s, err := NewOS(root)
	require.NoError(t, err)

	assert.ErrorIs(t, s.Check(filepath.Join(root, "escape", "pwned.txt")), ErrOutsideWorkspace,
		"a create through an escaping symlink dir would land outside the workspace")

	require.NoError(t, os.WriteFile(filepath.Join(outside, "data.txt"), []byte("x"), 0o644))
	assert.ErrorIs(t, s.Check(filepath.Join(root, "escape", "data.txt")), ErrOutsideWorkspace,
		"an existing file reached through an escaping symlink dir is outside")
}

// A symlinked FILE inside the workspace pointing at an outside file is
// outside.
func TestOS_SymlinkFileEscape_Refused(t *testing.T) {
	root := t.TempDir()
	outsideFile := filepath.Join(t.TempDir(), "secret.txt")
	require.NoError(t, os.WriteFile(outsideFile, []byte("s"), 0o644))
	require.NoError(t, os.Symlink(outsideFile, filepath.Join(root, "alias.txt")))

	s, err := NewOS(root)
	require.NoError(t, err)
	assert.ErrorIs(t, s.Check(filepath.Join(root, "alias.txt")), ErrOutsideWorkspace)
}

// In-scope paths on a real disk: the root, an existing file, and a
// not-yet-existing file (parent-dir resolution keeps a fresh create in scope).
func TestOS_InsidePaths_Allowed(t *testing.T) {
	root := t.TempDir()
	existing := filepath.Join(root, "a.txt")
	require.NoError(t, os.WriteFile(existing, []byte("x"), 0o644))

	s, err := NewOS(root)
	require.NoError(t, err)

	assert.NoError(t, s.Check(root))
	assert.NoError(t, s.Check(existing))
	assert.NoError(t, s.Check(filepath.Join(root, "not-yet-created.txt")))
}

// Real-disk ".." traversal out of the root is refused.
func TestOS_DotDotTraversal_Refused(t *testing.T) {
	parent := t.TempDir()
	root := filepath.Join(parent, "ws")
	require.NoError(t, os.Mkdir(root, 0o755))

	s, err := NewOS(root)
	require.NoError(t, err)
	assert.ErrorIs(t, s.Check(filepath.Join(root, "..", "loot.txt")), ErrOutsideWorkspace)
}
