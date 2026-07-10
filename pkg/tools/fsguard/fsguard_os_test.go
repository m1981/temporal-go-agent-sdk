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

// Regression: the canonical key must not change when a file comes into
// existence, or a create-then-edit sequence orphans the recorded read state and
// the edit spuriously fails as "not read". Uses an explicit symlinked parent so
// the case reproduces on any platform, not just where the temp root is a link.
func TestOSFilesystem_Canonical_StableAcrossFileCreation(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symlink semantics differ on Windows")
	}
	root := t.TempDir()
	realDir := filepath.Join(root, "real")
	require.NoError(t, os.Mkdir(realDir, 0o755))
	linkDir := filepath.Join(root, "link")
	require.NoError(t, os.Symlink(realDir, linkDir))

	var osfs OSFilesystem
	target := filepath.Join(linkDir, "file.go")

	before, err := osfs.Canonical(target)
	require.NoError(t, err)
	require.NoError(t, os.WriteFile(target, []byte("x"), 0o600))
	after, err := osfs.Canonical(target)
	require.NoError(t, err)

	assert.Equal(t, after, before, "canonical key must be stable across file creation")
}

func TestOSFilesystem_Canonical_NonexistentCleansAndResolvesParent(t *testing.T) {
	dir := t.TempDir()
	resolvedDir, err := filepath.EvalSymlinks(dir)
	require.NoError(t, err)

	var osfs OSFilesystem
	got, err := osfs.Canonical(filepath.Join(dir, "sub", "..", "created-later.go"))
	require.NoError(t, err)
	assert.Equal(t, filepath.Join(resolvedDir, "created-later.go"), got,
		"a missing target cleans .. segments and resolves its parent directory")
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

// CommitWrite over a real filesystem: it creates a new file, records it, and a
// stale target is refused without clobbering the on-disk change.
func TestGuard_CommitWrite_WithOSFilesystem_EndToEnd(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "out.go")
	g := New(OSFilesystem{})

	require.NoError(t, g.CommitWrite(path, []byte("created"), 0o644))
	got, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "created", string(got))

	// External change after the guard's last observation must block the commit.
	require.NoError(t, os.WriteFile(path, []byte("changed-externally"), 0o644))
	assert.ErrorIs(t, g.CommitWrite(path, []byte("v2"), 0o644), ErrStale)

	got, err = os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "changed-externally", string(got), "refused commit must not clobber the external change")
}
