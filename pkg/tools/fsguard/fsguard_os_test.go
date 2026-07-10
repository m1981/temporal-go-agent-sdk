package fsguard

import (
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// These tests exercise the production OSFilesystem seam and the Guard end to end
// against a real temporary directory, proving the contracts the Guard relies on:
// a missing file reports fs.ErrNotExist, and Canonical resolves symlinks to their
// target so a read via a link authorizes a write to the same underlying file
// (and not a different one swapped in behind the link).

func TestOSFilesystem_ReadFile_MissingReportsNotExist(t *testing.T) {
	var osfs OSFilesystem
	_, err := osfs.ReadFile(filepath.Join(t.TempDir(), "nope.txt"))
	assert.ErrorIs(t, err, fs.ErrNotExist)
}

func TestOSFilesystem_Canonical_ResolvesSymlinkToTarget(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink semantics differ on Windows")
	}
	dir := t.TempDir()
	target := filepath.Join(dir, "real.txt")
	require.NoError(t, os.WriteFile(target, []byte("hello"), 0o600))
	link := filepath.Join(dir, "link.txt")
	require.NoError(t, os.Symlink(target, link))

	var osfs OSFilesystem
	viaLink, err := osfs.Canonical(link)
	require.NoError(t, err)
	viaTarget, err := osfs.Canonical(target)
	require.NoError(t, err)

	assert.Equal(t, viaTarget, viaLink, "a symlink and its target must canonicalize to one key")
}

func TestOSFilesystem_Canonical_NonexistentFallsBackToCleanAbs(t *testing.T) {
	dir := t.TempDir()
	var osfs OSFilesystem
	got, err := osfs.Canonical(filepath.Join(dir, "sub", "..", "created-later.go"))
	require.NoError(t, err)
	assert.Equal(t, filepath.Join(dir, "created-later.go"), got)
}

// End-to-end: the full guarded lifecycle over a real file.
func TestGuard_WithOSFilesystem_EndToEnd(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.go")
	g := New(OSFilesystem{})

	// A file that does not exist yet may be created.
	assert.NoError(t, g.CheckWritable(path))

	// Once it exists but has not been read, writing is refused.
	require.NoError(t, os.WriteFile(path, []byte("v1"), 0o600))
	assert.ErrorIs(t, g.CheckWritable(path), ErrNotRead)

	// After observing it, an unchanged file is writable.
	content, err := os.ReadFile(path)
	require.NoError(t, err)
	require.NoError(t, g.MarkRead(path, content))
	assert.NoError(t, g.CheckWritable(path))

	// A change on disk between read and write is detected as stale.
	require.NoError(t, os.WriteFile(path, []byte("v2-tampered"), 0o600))
	assert.ErrorIs(t, g.CheckWritable(path), ErrStale)
}
