package fsguard

import (
	"errors"
	"io/fs"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// ---------------------------------------------------------------------------
// Test harness
//
// fakeFS is an in-memory Filesystem that lets a test drive Guard behavior with
// no real disk I/O. It can:
//   - hold file content (putFile), and mutate it mid-test to simulate the file
//     changing between read and write,
//   - force ReadFile to fail (setReadErr) to exercise fail-closed behavior,
//   - swap its canonicalization (canonFn) to simulate case-insensitive or
//     symlink-collapsing filesystems.
// Files are keyed by their canonical path, mirroring how the Guard keys state.
// ---------------------------------------------------------------------------

type fakeFS struct {
	mu       sync.Mutex
	files    map[string][]byte
	readErr  map[string]error
	writeErr map[string]error
	canonFn  func(string) (string, error)

	// writeHook, when set, runs at the start of every write-side seam call
	// (CreateExclusive, WriteFileAtomic), BEFORE the fake mutates anything.
	// It simulates a racing external writer landing in the gap between the
	// Guard's freshness check and its write. It is invoked without f.mu
	// held, so the hook may call putFile.
	writeHook func()
}

func newFakeFS() *fakeFS {
	return &fakeFS{
		files:    make(map[string][]byte),
		readErr:  make(map[string]error),
		writeErr: make(map[string]error),
		canonFn:  defaultCanon,
	}
}

// defaultCanon cleans a path and makes it absolute-looking, so that "./a/b" and
// "/a/b" collapse to a single key without touching the real filesystem.
func defaultCanon(p string) (string, error) {
	c := filepath.Clean(p)
	if !strings.HasPrefix(c, "/") {
		c = "/" + c
	}
	return c, nil
}

func (f *fakeFS) Canonical(path string) (string, error) { return f.canonFn(path) }

func (f *fakeFS) ReadFile(path string) ([]byte, error) {
	key, err := f.canonFn(path)
	if err != nil {
		return nil, err
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if e, ok := f.readErr[key]; ok {
		return nil, e
	}
	b, ok := f.files[key]
	if !ok {
		return nil, fs.ErrNotExist
	}
	return append([]byte(nil), b...), nil
}

// CreateExclusive mirrors O_CREATE|O_EXCL: it refuses with fs.ErrExist when
// the path already holds a file — including one the writeHook just planted.
func (f *fakeFS) CreateExclusive(path string, data []byte, _ fs.FileMode) error {
	key, err := f.canonFn(path)
	if err != nil {
		return err
	}
	f.runWriteHook()
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, exists := f.files[key]; exists {
		return fs.ErrExist
	}
	if e, ok := f.writeErr[key]; ok {
		return e
	}
	f.files[key] = append([]byte(nil), data...)
	return nil
}

// WriteFileAtomic models rename atomicity: the content is replaced in a single
// mutex-guarded step, so no torn intermediate is ever observable.
func (f *fakeFS) WriteFileAtomic(path string, data []byte, _ fs.FileMode) error {
	key, err := f.canonFn(path)
	if err != nil {
		return err
	}
	f.runWriteHook()
	f.mu.Lock()
	defer f.mu.Unlock()
	if e, ok := f.writeErr[key]; ok {
		return e
	}
	f.files[key] = append([]byte(nil), data...)
	return nil
}

func (f *fakeFS) runWriteHook() {
	f.mu.Lock()
	hook := f.writeHook
	f.mu.Unlock()
	if hook != nil {
		hook()
	}
}

func (f *fakeFS) setWriteHook(t *testing.T, hook func()) {
	t.Helper()
	f.mu.Lock()
	defer f.mu.Unlock()
	f.writeHook = hook
}

func (f *fakeFS) putFile(t *testing.T, path, content string) {
	t.Helper()
	key, err := f.canonFn(path)
	require.NoError(t, err)
	f.mu.Lock()
	defer f.mu.Unlock()
	f.files[key] = []byte(content)
}

func (f *fakeFS) setReadErr(t *testing.T, path string, e error) {
	t.Helper()
	key, err := f.canonFn(path)
	require.NoError(t, err)
	f.mu.Lock()
	defer f.mu.Unlock()
	f.readErr[key] = e
}

func (f *fakeFS) setWriteErr(t *testing.T, path string, e error) {
	t.Helper()
	key, err := f.canonFn(path)
	require.NoError(t, err)
	f.mu.Lock()
	defer f.mu.Unlock()
	f.writeErr[key] = e
}

func newGuard(t *testing.T) (*Guard, *fakeFS) {
	t.Helper()
	ff := newFakeFS()
	return New(ff), ff
}

// ---------------------------------------------------------------------------
// Spec: the behavior matrix the implementation must satisfy.
// ---------------------------------------------------------------------------

// A brand-new file (nothing on disk) may be created without a prior Read —
// you cannot read what does not exist yet.
func TestCheckWritable_NewFile_AllowedWithoutRead(t *testing.T) {
	g, _ := newGuard(t)
	assert.NoError(t, g.CheckWritable("/repo/new_file.go"))
}

// An existing file that was never read must be refused: writing it would be a
// blind overwrite.
func TestCheckWritable_ExistingUnreadFile_ReturnsErrNotRead(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "package main")

	assert.ErrorIs(t, g.CheckWritable("/repo/main.go"), ErrNotRead)
}

// Read then unchanged => allowed.
func TestCheckWritable_ReadThenUnchanged_Allowed(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "package main")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("package main")))

	assert.NoError(t, g.CheckWritable("/repo/main.go"))
}

// Read, then the on-disk content changes (formatter, user, another process) =>
// stale. This is content-hash based, so it fires even though a mtime-restore
// attack would defeat a timestamp check.
func TestCheckWritable_ModifiedSinceRead_ReturnsErrStale(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "package main")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("package main")))

	ff.putFile(t, "/repo/main.go", "package main // changed underneath us")

	assert.ErrorIs(t, g.CheckWritable("/repo/main.go"), ErrStale)
}

// After a guarded write, the new content becomes the observed state, so the
// tool can make a second edit without re-reading its own output.
func TestCheckWritable_AfterMarkWritten_AllowsSuccessiveEdit(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "v1")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("v1")))

	ff.putFile(t, "/repo/main.go", "v2") // the tool wrote v2 to disk
	require.NoError(t, g.MarkWritten("/repo/main.go", []byte("v2")))

	assert.NoError(t, g.CheckWritable("/repo/main.go"))
}

// A read via one spelling authorizes a write via another spelling of the same
// file (relative vs absolute), because the Guard keys on the canonical path.
func TestCheckWritable_PathAliases_ResolveToSameFile(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/pkg/f.go", "x")
	require.NoError(t, g.MarkRead("./repo/pkg/f.go", []byte("x")))

	assert.NoError(t, g.CheckWritable("/repo/pkg/f.go"))
}

// On a case-insensitive filesystem, Foo.go and foo.go are the same file; the
// Guard must honor whatever identity the Filesystem's Canonical reports.
func TestCheckWritable_CaseInsensitiveCanonical_TreatsAliasAsSameFile(t *testing.T) {
	g, ff := newGuard(t)
	ff.canonFn = func(p string) (string, error) {
		c, _ := defaultCanon(p)
		return strings.ToLower(c), nil
	}
	ff.putFile(t, "/repo/Foo.go", "x")
	require.NoError(t, g.MarkRead("/repo/Foo.go", []byte("x")))

	assert.NoError(t, g.CheckWritable("/repo/foo.go"))
}

// If the filesystem returns an unexpected error while checking freshness (e.g.
// permission denied), the Guard must fail closed: refuse the write, and not
// misreport it as "not read" or "stale".
func TestCheckWritable_UnexpectedFSError_FailsClosed(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "package main")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("package main")))
	ff.setReadErr(t, "/repo/main.go", errors.New("permission denied"))

	err := g.CheckWritable("/repo/main.go")
	require.Error(t, err)
	assert.NotErrorIs(t, err, ErrNotRead)
	assert.NotErrorIs(t, err, ErrStale)
}

// The model-facing error text must be static and must not embed the file path.
// Tool results are fed back to the model, so interpolating untrusted path data
// would be a prompt-injection channel.
func TestCheckWritable_ErrorText_IsStaticAndLeaksNoPath(t *testing.T) {
	g, ff := newGuard(t)
	const secret = "/repo/very-secret-marker-path.go"
	ff.putFile(t, secret, "data")

	err := g.CheckWritable(secret)
	require.ErrorIs(t, err, ErrNotRead)
	assert.NotContains(t, err.Error(), "secret")
	assert.NotContains(t, err.Error(), secret)
}

// A failure to canonicalize a path must propagate from both the recording and
// the checking paths, never be swallowed into a silent allow.
func TestGuard_CanonicalError_Propagates(t *testing.T) {
	g, ff := newGuard(t)
	sentinel := errors.New("cannot canonicalize")
	ff.canonFn = func(string) (string, error) { return "", sentinel }

	assert.ErrorIs(t, g.MarkRead("/repo/x.go", []byte("a")), sentinel)
	assert.ErrorIs(t, g.MarkWritten("/repo/x.go", []byte("a")), sentinel)
	assert.ErrorIs(t, g.CheckWritable("/repo/x.go"), sentinel)
}

// The Guard must be safe under concurrent tool executions. Run with -race.
func TestGuard_ConcurrentAccess_IsRaceFree(t *testing.T) {
	g, ff := newGuard(t)
	paths := make([]string, 26)
	for i := range paths {
		paths[i] = "/repo/f" + string(rune('a'+i)) + ".go"
		ff.putFile(t, paths[i], "x")
	}

	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(1)
		go func(p string) {
			defer wg.Done()
			_ = g.MarkRead(p, []byte("x"))
			_ = g.CheckWritable(p)
			_ = g.MarkWritten(p, []byte("y"))
		}(paths[i%len(paths)])
	}
	wg.Wait()
}
