package fsguard

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Snapshotting and restoring must preserve the exact freshness decisions the
// source Guard would have made: an unchanged file stays writable, and drift is
// still detected. This is what lets the guard survive a Temporal replay or a
// worker handoff, where the map cannot be carried in process memory.
func TestSnapshot_RoundTrip_PreservesFreshnessDecisions(t *testing.T) {
	src, ff := newGuard(t)
	ff.putFile(t, "/repo/a.go", "aaa")
	require.NoError(t, src.MarkRead("/repo/a.go", []byte("aaa")))

	dst := New(ff)
	dst.Restore(src.Snapshot())

	assert.NoError(t, dst.CheckWritable("/repo/a.go"),
		"unchanged file must remain writable after restore")

	ff.putFile(t, "/repo/a.go", "bbb")
	assert.ErrorIs(t, dst.CheckWritable("/repo/a.go"), ErrStale,
		"restored state must still detect drift")
}

// The snapshot must survive a JSON round-trip, since that is how it will be
// persisted in durable workflow state.
func TestSnapshot_JSONRoundTrip(t *testing.T) {
	src, ff := newGuard(t)
	ff.putFile(t, "/repo/a.go", "aaa")
	require.NoError(t, src.MarkRead("/repo/a.go", []byte("aaa")))

	data, err := json.Marshal(src.Snapshot())
	require.NoError(t, err)

	var snap Snapshot
	require.NoError(t, json.Unmarshal(data, &snap))

	dst := New(ff)
	dst.Restore(snap)
	assert.NoError(t, dst.CheckWritable("/repo/a.go"))
}

// A returned snapshot must be an independent copy in both directions: mutating
// it must not corrupt the Guard, and later Guard changes must not leak into an
// already-taken snapshot.
func TestSnapshot_IsDeepCopy(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/a.go", "aaa")
	require.NoError(t, g.MarkRead("/repo/a.go", []byte("aaa")))

	snap := g.Snapshot()
	require.Len(t, snap.Reads, 1)

	for k := range snap.Reads {
		snap.Reads[k] = "tampered"
	}
	assert.NoError(t, g.CheckWritable("/repo/a.go"),
		"guard state must be independent of a returned snapshot")

	require.NoError(t, g.MarkWritten("/repo/b.go", []byte("bbb")))
	assert.Len(t, snap.Reads, 1,
		"snapshot must be frozen at capture time")
}

// Restore replaces prior state wholesale rather than merging.
func TestRestore_ReplacesPriorState(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/old.go", "old")
	require.NoError(t, g.MarkRead("/repo/old.go", []byte("old")))

	ff.putFile(t, "/repo/new.go", "new")
	g.Restore(Snapshot{Reads: map[string]string{"/repo/new.go": hashBytes([]byte("new"))}})

	assert.ErrorIs(t, g.CheckWritable("/repo/old.go"), ErrNotRead,
		"restore should drop prior entries")
	assert.NoError(t, g.CheckWritable("/repo/new.go"),
		"restore should install snapshot entries")
}

// Restoring an empty/nil snapshot clears state without panicking.
func TestRestore_EmptySnapshot_ClearsState(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/a.go", "aaa")
	require.NoError(t, g.MarkRead("/repo/a.go", []byte("aaa")))

	g.Restore(Snapshot{})
	assert.ErrorIs(t, g.CheckWritable("/repo/a.go"), ErrNotRead)
}
