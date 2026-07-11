package fsguard

import (
	"bytes"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"sync"
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

// CreateExclusive on the real OS: creates a missing file with the given
// content, and refuses an existing one with fs.ErrExist, leaving it untouched.
func TestOSFilesystem_CreateExclusive_NewAndExisting(t *testing.T) {
	var osfs OSFilesystem
	dir := t.TempDir()
	path := filepath.Join(dir, "new.txt")

	require.NoError(t, osfs.CreateExclusive(path, []byte("first"), 0o644))
	got, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "first", string(got))

	err = osfs.CreateExclusive(path, []byte("second"), 0o644)
	assert.ErrorIs(t, err, fs.ErrExist, "an existing file must refuse an exclusive create")
	got, err = os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "first", string(got), "a refused exclusive create must not touch the file")
}

// WriteFileAtomic replaces content and leaves no temp-file litter behind.
func TestOSFilesystem_WriteFileAtomic_ReplacesContentNoLitter(t *testing.T) {
	var osfs OSFilesystem
	dir := t.TempDir()
	path := filepath.Join(dir, "f.txt")
	require.NoError(t, os.WriteFile(path, []byte("old"), 0o644))

	require.NoError(t, osfs.WriteFileAtomic(path, []byte("new"), 0o644))

	got, err := os.ReadFile(path)
	require.NoError(t, err)
	assert.Equal(t, "new", string(got))
	entries, err := os.ReadDir(dir)
	require.NoError(t, err)
	require.Len(t, entries, 1, "no temp files may be left behind")
	assert.Equal(t, "f.txt", entries[0].Name())
}

// WriteFileAtomic preserves an existing file's mode (temp+rename would
// otherwise silently reset it), and applies perm when creating fresh.
func TestOSFilesystem_WriteFileAtomic_Permissions(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("POSIX permission semantics")
	}
	var osfs OSFilesystem
	dir := t.TempDir()

	existing := filepath.Join(dir, "tight.txt")
	require.NoError(t, os.WriteFile(existing, []byte("old"), 0o600))
	require.NoError(t, osfs.WriteFileAtomic(existing, []byte("new"), 0o644))
	fi, err := os.Stat(existing)
	require.NoError(t, err)
	assert.Equal(t, fs.FileMode(0o600), fi.Mode().Perm(), "an existing file keeps its mode")

	fresh := filepath.Join(dir, "fresh.txt")
	require.NoError(t, osfs.WriteFileAtomic(fresh, []byte("new"), 0o640))
	fi, err = os.Stat(fresh)
	require.NoError(t, err)
	assert.Equal(t, fs.FileMode(0o640), fi.Mode().Perm(), "a fresh file gets the requested perm")
}

// A missing parent directory fails cleanly (the temp file cannot be staged).
func TestOSFilesystem_WriteFileAtomic_MissingDirFails(t *testing.T) {
	var osfs OSFilesystem
	err := osfs.WriteFileAtomic(filepath.Join(t.TempDir(), "no-such-dir", "f.txt"), []byte("x"), 0o644)
	assert.Error(t, err)
}

// Rename atomicity: a concurrent reader must always observe one complete
// payload — never a torn mix, a truncated file, or a missing path. A
// truncate-then-write implementation fails this probabilistically; rename
// guarantees it.
func TestOSFilesystem_WriteFileAtomic_ConcurrentReaderNeverTorn(t *testing.T) {
	var osfs OSFilesystem
	dir := t.TempDir()
	path := filepath.Join(dir, "big.txt")

	const size = 128 * 1024
	payloadA := bytes.Repeat([]byte{'a'}, size)
	payloadB := bytes.Repeat([]byte{'b'}, size)
	require.NoError(t, os.WriteFile(path, payloadA, 0o644))

	done := make(chan struct{})
	var readerErr error
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		for {
			select {
			case <-done:
				return
			default:
			}
			b, err := os.ReadFile(path)
			if err != nil {
				readerErr = fmt.Errorf("reader saw error (path must always exist): %w", err)
				return
			}
			if len(b) != size || b[0] != b[size-1] || !bytes.Equal(b, bytes.Repeat(b[:1], size)) {
				readerErr = fmt.Errorf("reader saw a torn write: len=%d first=%q last=%q", len(b), b[0], b[len(b)-1])
				return
			}
		}
	}()

	for i := 0; i < 150; i++ {
		p := payloadA
		if i%2 == 0 {
			p = payloadB
		}
		require.NoError(t, osfs.WriteFileAtomic(path, p, 0o644))
	}
	close(done)
	wg.Wait()
	require.NoError(t, readerErr)
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
