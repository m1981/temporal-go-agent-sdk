package pathscope

import (
	"errors"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// fakeCanon is an in-memory Canonicalizer. Paths listed in resolve map to a
// preset canonical form (simulating symlink resolution); paths listed in errs
// fail; everything else falls back to filepath.Clean, which is enough to
// simulate abs-path cleaning ("/w/app/../../etc" -> "/etc") without a disk.
type fakeCanon struct {
	resolve map[string]string
	errs    map[string]error
}

func (f *fakeCanon) Canonical(path string) (string, error) {
	if f.errs != nil {
		if err, ok := f.errs[path]; ok {
			return "", err
		}
	}
	if f.resolve != nil {
		if r, ok := f.resolve[path]; ok {
			return r, nil
		}
	}
	return filepath.Clean(path), nil
}

// newScope builds a Scope rooted at /w/app over a fakeCanon.
func newScope(t *testing.T, f *fakeCanon) *Scope {
	t.Helper()
	s, err := New("/w/app", f)
	require.NoError(t, err)
	return s
}

// A path strictly inside the root is in scope.
func TestCheck_InsideRoot_Allowed(t *testing.T) {
	s := newScope(t, &fakeCanon{})
	assert.NoError(t, s.Check("/w/app/src/main.go"))
	assert.NoError(t, s.Check("/w/app/file.txt"))
}

// The root itself is in scope, in any spelling that resolves to it.
func TestCheck_RootItself_Allowed(t *testing.T) {
	s := newScope(t, &fakeCanon{})
	assert.NoError(t, s.Check("/w/app"))
	assert.NoError(t, s.Check("/w/app/"))
	assert.NoError(t, s.Check("/w/app/src/.."))
}

// Escape vector: relative ".." traversal cleaning to a location outside root.
func TestCheck_DotDotTraversal_Refused(t *testing.T) {
	s := newScope(t, &fakeCanon{})
	assert.ErrorIs(t, s.Check("/w/app/../../etc/passwd"), ErrOutsideWorkspace)
}

// Escape vector: an absolute path outside the root.
func TestCheck_AbsoluteOutside_Refused(t *testing.T) {
	s := newScope(t, &fakeCanon{})
	assert.ErrorIs(t, s.Check("/etc/passwd"), ErrOutsideWorkspace)
	assert.ErrorIs(t, s.Check("/w/other/file"), ErrOutsideWorkspace)
}

// Boundary: a sibling directory sharing the root's name as a prefix is
// OUTSIDE. Naive strings.HasPrefix(path, root) gets this wrong.
func TestCheck_SiblingWithNamePrefix_Refused(t *testing.T) {
	s := newScope(t, &fakeCanon{})
	assert.ErrorIs(t, s.Check("/w/app-evil"), ErrOutsideWorkspace)
	assert.ErrorIs(t, s.Check("/w/app-evil/payload.sh"), ErrOutsideWorkspace)
	assert.ErrorIs(t, s.Check("/w/apple/x"), ErrOutsideWorkspace)
}

// Escape vector: a path inside the root that RESOLVES (symlink) outside it.
// The fake plays the role of the OS resolver; the real-disk variant lives in
// pathscope_os_test.go.
func TestCheck_SymlinkResolvingOutside_Refused(t *testing.T) {
	s := newScope(t, &fakeCanon{resolve: map[string]string{
		"/w/app/escape/pwned.txt": "/outside/pwned.txt",
	}})
	assert.ErrorIs(t, s.Check("/w/app/escape/pwned.txt"), ErrOutsideWorkspace)
}

// A symlink inside the root that resolves elsewhere INSIDE the root stays in
// scope: the decision is about the resolved location, not the spelling.
func TestCheck_SymlinkResolvingInside_Allowed(t *testing.T) {
	s := newScope(t, &fakeCanon{resolve: map[string]string{
		"/w/app/alias.txt": "/w/app/real/target.txt",
	}})
	assert.NoError(t, s.Check("/w/app/alias.txt"))
}

// The root given to New is itself canonicalized, so a root reached via a
// symlink (e.g. /var -> /private/var on macOS) compares correctly against
// resolved paths.
func TestNew_CanonicalizesRoot(t *testing.T) {
	f := &fakeCanon{resolve: map[string]string{
		"/var/ws": "/private/var/ws",
	}}
	s, err := New("/var/ws", f)
	require.NoError(t, err)

	assert.NoError(t, s.Check("/private/var/ws/file.txt"))
	assert.ErrorIs(t, s.Check("/private/var/other"), ErrOutsideWorkspace)
}

// A filesystem-root workspace must not trip over separator handling.
func TestCheck_FilesystemRootWorkspace_Allowed(t *testing.T) {
	s, err := New("/", &fakeCanon{})
	require.NoError(t, err)
	assert.NoError(t, s.Check("/etc/passwd"))
	assert.NoError(t, s.Check("/"))
}

// Fail-closed: a canonicalization failure propagates as-is and is never
// reported as in scope (nil) nor conflated with ErrOutsideWorkspace.
func TestCheck_CanonicalError_Propagates(t *testing.T) {
	sentinel := errors.New("cannot canonicalize")
	s := newScope(t, &fakeCanon{errs: map[string]error{"/w/app/x": sentinel}})

	err := s.Check("/w/app/x")
	assert.ErrorIs(t, err, sentinel)
	assert.NotErrorIs(t, err, ErrOutsideWorkspace)
}

// A canonicalization failure on the ROOT fails construction.
func TestNew_RootCanonicalError_Propagates(t *testing.T) {
	sentinel := errors.New("bad root")
	_, err := New("/w/app", &fakeCanon{errs: map[string]error{"/w/app": sentinel}})
	assert.ErrorIs(t, err, sentinel)
}

// The model-facing error text must be static and must not embed the offending
// path or the workspace root. Tool results are fed back to the model, so
// interpolating untrusted path data would be a prompt-injection channel.
func TestCheck_ErrorText_IsStaticAndLeaksNoPath(t *testing.T) {
	const secretRoot = "/w/very-secret-workspace-marker"
	s, err := New(secretRoot, &fakeCanon{})
	require.NoError(t, err)

	const secretPath = "/etc/very-secret-target-marker"
	checkErr := s.Check(secretPath)
	require.ErrorIs(t, checkErr, ErrOutsideWorkspace)
	assert.NotContains(t, checkErr.Error(), "secret")
	assert.NotContains(t, checkErr.Error(), secretPath)
	assert.NotContains(t, checkErr.Error(), secretRoot)
	assert.Equal(t, ErrOutsideWorkspace.Error(), checkErr.Error(),
		"the sentinel must be returned unwrapped and undecorated")
}
