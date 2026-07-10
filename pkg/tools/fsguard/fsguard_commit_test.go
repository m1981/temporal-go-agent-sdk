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
