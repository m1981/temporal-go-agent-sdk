package fsguard

import (
	"errors"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// A fresh create through CommitWrite lands on disk and records the new content,
// so a follow-up edit is allowed without a separate MarkRead.
func TestCommitWrite_NewFile_WritesAndRecords(t *testing.T) {
	g, ff := newGuard(t)

	require.NoError(t, g.CommitWrite("/repo/new.go", []byte("hello"), 0o644))

	b, err := ff.ReadFile("/repo/new.go")
	require.NoError(t, err)
	assert.Equal(t, "hello", string(b))

	assert.NoError(t, g.CommitWrite("/repo/new.go", []byte("hello2"), 0o644),
		"content recorded by the first commit should authorize the second")
}

// An existing-but-unread file is refused, and the file is left untouched.
func TestCommitWrite_UnreadExistingFile_RefusedNoWrite(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "original")

	assert.ErrorIs(t, g.CommitWrite("/repo/main.go", []byte("overwrite"), 0o644), ErrNotRead)

	b, _ := ff.ReadFile("/repo/main.go")
	assert.Equal(t, "original", string(b), "a refused write must not touch the file")
}

// A file that changed on disk after being read is refused, and the external
// change is preserved rather than clobbered.
func TestCommitWrite_StaleFile_RefusedNoWrite(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "v1")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("v1")))
	ff.putFile(t, "/repo/main.go", "v2-external")

	assert.ErrorIs(t, g.CommitWrite("/repo/main.go", []byte("v3"), 0o644), ErrStale)

	b, _ := ff.ReadFile("/repo/main.go")
	assert.Equal(t, "v2-external", string(b), "a stale write must not clobber the external change")
}

// Read then commit succeeds, writes the new bytes, and refreshes state.
func TestCommitWrite_ReadThenCommit_Succeeds(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "v1")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("v1")))

	require.NoError(t, g.CommitWrite("/repo/main.go", []byte("v2"), 0o644))

	b, _ := ff.ReadFile("/repo/main.go")
	assert.Equal(t, "v2", string(b))
	assert.NoError(t, g.CheckWritable("/repo/main.go"), "state must be refreshed to the written content")
}

// A filesystem write error propagates, is not misreported as a guard verdict,
// and leaves the recorded state uncorrupted.
func TestCommitWrite_WriteError_PropagatesAndKeepsState(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "v1")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("v1")))
	ff.setWriteErr(t, "/repo/main.go", errors.New("disk full"))

	err := g.CommitWrite("/repo/main.go", []byte("v2"), 0o644)
	require.Error(t, err)
	assert.NotErrorIs(t, err, ErrNotRead)
	assert.NotErrorIs(t, err, ErrStale)

	// Disk is unchanged and the original read is still valid.
	assert.NoError(t, g.CheckWritable("/repo/main.go"))
}

// A racing external CREATE landing between CommitWrite's existence check and
// its write must be refused with ErrConcurrentCreate, and the externally
// created file must survive untouched — the write may not clobber it
// (wk-2f8c87bf). The fake's writeHook plants the file in exactly that gap.
func TestCommitWrite_NewFile_RacingExternalCreate_RefusedNotClobbered(t *testing.T) {
	g, ff := newGuard(t)
	ff.setWriteHook(t, func() { ff.putFile(t, "/repo/new.go", "external-content") })

	err := g.CommitWrite("/repo/new.go", []byte("agent-content"), 0o644)

	assert.ErrorIs(t, err, ErrConcurrentCreate)
	b, rerr := ff.ReadFile("/repo/new.go")
	require.NoError(t, rerr)
	assert.Equal(t, "external-content", string(b), "the racing create must survive, not be clobbered")
	assert.ErrorIs(t, g.CheckWritable("/repo/new.go"), ErrNotRead,
		"the refused write must not record any observed state for the file")
}

// The concurrent-create refusal is model-facing text: static, path-free.
func TestCommitWrite_ConcurrentCreate_ErrorTextStaticAndPathFree(t *testing.T) {
	g, ff := newGuard(t)
	const secret = "/repo/very-secret-marker-path.go"
	ff.setWriteHook(t, func() { ff.putFile(t, secret, "x") })

	err := g.CommitWrite(secret, []byte("y"), 0o644)
	require.ErrorIs(t, err, ErrConcurrentCreate)
	assert.NotContains(t, err.Error(), "secret")
	assert.NotContains(t, err.Error(), secret)
}

// A non-ErrExist failure of the exclusive create (e.g. disk full) propagates
// as itself, not misreported as a concurrent create or a guard verdict.
func TestCommitWrite_NewFile_CreateError_Propagates(t *testing.T) {
	g, ff := newGuard(t)
	sentinel := errors.New("disk full")
	ff.setWriteErr(t, "/repo/new.go", sentinel)

	err := g.CommitWrite("/repo/new.go", []byte("x"), 0o644)
	require.ErrorIs(t, err, sentinel)
	assert.NotErrorIs(t, err, ErrConcurrentCreate)
}

// CommitWrite propagates canonicalization failures and unexpected read errors
// (fail-closed), same as CheckWritable.
func TestCommitWrite_CanonicalAndReadErrors_FailClosed(t *testing.T) {
	t.Run("canonical error", func(t *testing.T) {
		g, ff := newGuard(t)
		sentinel := errors.New("cannot canonicalize")
		ff.canonFn = func(string) (string, error) { return "", sentinel }
		assert.ErrorIs(t, g.CommitWrite("/repo/x.go", []byte("a"), 0o644), sentinel)
	})
	t.Run("read error", func(t *testing.T) {
		g, ff := newGuard(t)
		ff.putFile(t, "/repo/x.go", "v1")
		require.NoError(t, g.MarkRead("/repo/x.go", []byte("v1")))
		sentinel := errors.New("permission denied")
		ff.setReadErr(t, "/repo/x.go", sentinel)

		err := g.CommitWrite("/repo/x.go", []byte("v2"), 0o644)
		require.ErrorIs(t, err, sentinel)
		assert.NotErrorIs(t, err, ErrNotRead)
		assert.NotErrorIs(t, err, ErrStale)
	})
}

// DOCUMENTED RESIDUAL (ADR-010): an external MODIFICATION of an existing file
// that lands after CommitWrite's final freshness re-read but before the atomic
// replace is still overwritten — the content-hash model cannot close this last
// window without OS-level compare-and-swap. This test pins the residual as
// executable documentation: if it ever starts failing, the window was closed
// and ADR-010 must be updated alongside it.
func TestCommitWrite_ExistingFile_RaceAfterFinalVerify_ResidualOverwrite(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/main.go", "v1")
	require.NoError(t, g.MarkRead("/repo/main.go", []byte("v1")))
	ff.setWriteHook(t, func() { ff.putFile(t, "/repo/main.go", "external-v2") })

	require.NoError(t, g.CommitWrite("/repo/main.go", []byte("agent-v2"), 0o644))

	b, _ := ff.ReadFile("/repo/main.go")
	assert.Equal(t, "agent-v2", string(b),
		"the residual window per ADR-010: a modify after the last re-read is overwritten")
}

// Concurrent commits must be race-free (run with -race).
func TestCommitWrite_Concurrent_RaceFree(t *testing.T) {
	g, _ := newGuard(t)
	paths := make([]string, 10)
	for i := range paths {
		paths[i] = "/repo/f" + string(rune('a'+i)) + ".go"
	}

	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(1)
		go func(p string) {
			defer wg.Done()
			_ = g.CommitWrite(p, []byte("x"), 0o644)
		}(paths[i%len(paths)])
	}
	wg.Wait()
}
