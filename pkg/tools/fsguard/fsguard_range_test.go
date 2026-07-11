package fsguard

import (
	"encoding/json"
	"errors"
	"io/fs"
	"strings"
	"sync"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// ---------------------------------------------------------------------------
// Spec: edit-region / read-range coverage (wk-3c9b615d).
//
// A partial Read (offset/limit) must not authorize an edit outside the lines
// it observed. MarkReadRange records which 1-based line ranges of a file were
// surfaced; CheckEditable verifies an edit's target span falls inside the
// union of observed ranges, ON TOP OF the existing freshness (hash) check.
// A plain MarkRead keeps its meaning: whole file observed, any span editable.
// ---------------------------------------------------------------------------

// content20 builds a file body with n numbered lines, so tests can talk about
// line positions concretely.
func linesBody(n int) []byte {
	var b strings.Builder
	for i := 1; i <= n; i++ {
		b.WriteString("line\n")
	}
	return []byte(b.String())
}

// Backward compatibility: a full-file MarkRead authorizes an edit at ANY span,
// exactly as today a full read authorizes any write.
func TestCheckEditable_FullRead_AuthorizesAnySpan(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))
	require.NoError(t, g.MarkRead("/repo/big.go", body))

	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 1, End: 1}))
	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 500, End: 510}))
}

// The motivating gap: observe lines 1-20, then try to rewrite line 500. The
// file is fresh (hash matches), but the target span was never seen.
func TestCheckEditable_SpanOutsideObservedRange_ReturnsErrRegionNotRead(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/big.go", body, LineRange{Start: 1, End: 20}))

	assert.ErrorIs(t, g.CheckEditable("/repo/big.go", LineRange{Start: 500, End: 500}), ErrRegionNotRead)
}

// A span inside the observed range is editable, including exactly at the
// boundaries and a single-line span.
func TestCheckEditable_SpanWithinObservedRange_Allowed(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/big.go", body, LineRange{Start: 10, End: 30}))

	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 10, End: 30}), "exact range")
	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 15, End: 25}), "interior")
	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 10, End: 10}), "single line at start boundary")
	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 30, End: 30}), "single line at end boundary")
}

// A span that straddles the edge of the observed range is refused: part of it
// was never seen.
func TestCheckEditable_SpanPartiallyOutside_ReturnsErrRegionNotRead(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/big.go", body, LineRange{Start: 10, End: 30}))

	assert.ErrorIs(t, g.CheckEditable("/repo/big.go", LineRange{Start: 25, End: 35}), ErrRegionNotRead, "overhangs the end")
	assert.ErrorIs(t, g.CheckEditable("/repo/big.go", LineRange{Start: 5, End: 15}), ErrRegionNotRead, "overhangs the start")
	assert.ErrorIs(t, g.CheckEditable("/repo/big.go", LineRange{Start: 9, End: 9}), ErrRegionNotRead, "one line before")
	assert.ErrorIs(t, g.CheckEditable("/repo/big.go", LineRange{Start: 31, End: 31}), ErrRegionNotRead, "one line after")
}

// The freshness check still runs FIRST: an unread file is ErrNotRead, a stale
// file is ErrStale — never ErrRegionNotRead, which would misdescribe the
// failure to the model.
func TestCheckEditable_FreshnessStillEnforced(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))

	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 1, End: 5}), ErrNotRead,
		"never observed at all")

	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 50}))
	ff.putFile(t, "/repo/a.go", "changed underneath us\n")
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 1, End: 5}), ErrStale,
		"changed since observed")
}

// A file that does not exist yet is editable, mirroring CheckWritable's
// fresh-create rule: there is no unseen content to clobber.
func TestCheckEditable_NewFile_Allowed(t *testing.T) {
	g, _ := newGuard(t)
	assert.NoError(t, g.CheckEditable("/repo/new.go", LineRange{Start: 1, End: 10}))
}

// Overlapping observed ranges merge: 1-10 and 5-20 together cover 1-20.
func TestCheckEditable_OverlappingRangesMerge(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 5, End: 20}))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 3, End: 18}),
		"a span across both observed ranges must pass once they merge")
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 3, End: 21}), ErrRegionNotRead,
		"one line past the merged union still fails")
}

// Adjacent ranges (10 then 11) merge too: reading 1-10 and 11-20 in two calls
// covers 1-20 with no artificial seam.
func TestCheckEditable_AdjacentRangesMerge(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 11, End: 20}))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 5, End: 15}))
}

// A one-line gap between observed ranges does NOT merge: a span crossing the
// gap contains an unobserved line and must be refused, while each side alone
// remains editable.
func TestCheckEditable_GapBetweenRanges_DoesNotMerge(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 12, End: 20}))

	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 5, End: 15}), ErrRegionNotRead,
		"span crosses the unobserved line 11")
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 11, End: 11}), ErrRegionNotRead,
		"the gap line itself is unobserved")
	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 1, End: 10}))
	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 12, End: 20}))
}

// Multiple ranges may arrive unsorted in a single call.
func TestMarkReadRange_UnsortedRangesInOneCall(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body,
		LineRange{Start: 30, End: 40}, LineRange{Start: 1, End: 10}))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 35, End: 38}))
	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 2, End: 9}))
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 15, End: 20}), ErrRegionNotRead)
}

// If the content changed between two partial reads (different hash), the old
// ranges described a different file body and are discarded: only the ranges
// observed against the CURRENT content count.
func TestMarkReadRange_ContentChanged_ResetsCoverage(t *testing.T) {
	g, ff := newGuard(t)
	v1 := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(v1))
	require.NoError(t, g.MarkReadRange("/repo/a.go", v1, LineRange{Start: 1, End: 10}))

	v2 := append([]byte("// new header\n"), v1...)
	ff.putFile(t, "/repo/a.go", string(v2))
	require.NoError(t, g.MarkReadRange("/repo/a.go", v2, LineRange{Start: 20, End: 30}))

	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 5, End: 5}), ErrRegionNotRead,
		"range observed against the old content must not survive")
	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 20, End: 30}))
}

// A later full read upgrades a partially-observed file to full coverage.
func TestMarkRead_AfterPartialRead_UpgradesToFullCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))
	require.NoError(t, g.MarkRead("/repo/a.go", body))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 40, End: 45}))
}

// A partial read after a full read of the SAME content adds no information and
// must not downgrade full coverage.
func TestMarkReadRange_AfterFullReadSameContent_KeepsFullCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkRead("/repo/a.go", body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 2}))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 40, End: 45}))
}

// MarkReadRange with no ranges records freshness only: the file may be
// re-created wholesale (CheckWritable) but no line span was observed.
func TestMarkReadRange_NoRanges_FreshOnlyNoCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(10)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body))

	assert.NoError(t, g.CheckWritable("/repo/a.go"), "freshness is recorded")
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 1, End: 1}), ErrRegionNotRead,
		"no span was observed")
}

// CheckWritable keeps its current, freshness-only meaning: a partial read
// still authorizes a whole-file overwrite. Region coverage is CheckEditable's
// job, orthogonal to freshness (documented in ADR-009).
func TestCheckWritable_AfterPartialRead_StillFreshnessOnly(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))

	assert.NoError(t, g.CheckWritable("/repo/a.go"))
}

// A guarded write observes the full new content: after CommitWrite (or
// MarkWritten) the whole file is covered, so successive edits anywhere pass.
func TestCommitWrite_AfterPartialRead_UpgradesToFullCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))

	next := linesBody(60)
	require.NoError(t, g.CommitWrite("/repo/a.go", next, 0o644))
	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 55, End: 58}),
		"the committed content was written in full, so any span is covered")
}

func TestMarkWritten_AfterPartialRead_UpgradesToFullCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))

	next := linesBody(60)
	ff.putFile(t, "/repo/a.go", string(next))
	require.NoError(t, g.MarkWritten("/repo/a.go", next))

	assert.NoError(t, g.CheckEditable("/repo/a.go", LineRange{Start: 55, End: 58}))
}

// Malformed ranges are rejected loudly on both the recording and the checking
// side, never silently normalized into a grant or a denial.
func TestLineRange_Invalid_Rejected(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(10)
	ff.putFile(t, "/repo/a.go", string(body))

	assert.ErrorIs(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 0, End: 5}), ErrInvalidRange)
	assert.ErrorIs(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 5, End: 4}), ErrInvalidRange)

	require.NoError(t, g.MarkRead("/repo/a.go", body))
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 0, End: 5}), ErrInvalidRange)
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: -3, End: -1}), ErrInvalidRange)
}

// A rejected MarkReadRange must be all-or-nothing: no freshness or coverage
// may be recorded from a call that returned ErrInvalidRange.
func TestMarkReadRange_InvalidRange_RecordsNothing(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(10)
	ff.putFile(t, "/repo/a.go", string(body))

	require.ErrorIs(t, g.MarkReadRange("/repo/a.go", body,
		LineRange{Start: 1, End: 5}, LineRange{Start: 0, End: 3}), ErrInvalidRange)

	assert.ErrorIs(t, g.CheckWritable("/repo/a.go"), ErrNotRead,
		"the valid range in the same failed call must not have been recorded")
}

// The out-of-range error text is static and leaks neither the path nor the
// span, mirroring the ErrNotRead/ErrStale injection-channel rule: tool-result
// text is fed back to the model.
func TestCheckEditable_ErrorText_IsStaticAndLeaksNoPathOrSpan(t *testing.T) {
	g, ff := newGuard(t)
	const secret = "/repo/very-secret-marker-path.go"
	body := linesBody(600)
	ff.putFile(t, secret, string(body))
	require.NoError(t, g.MarkReadRange(secret, body, LineRange{Start: 1, End: 20}))

	err := g.CheckEditable(secret, LineRange{Start: 517, End: 523})
	require.ErrorIs(t, err, ErrRegionNotRead)
	assert.NotContains(t, err.Error(), "secret")
	assert.NotContains(t, err.Error(), secret)
	assert.NotContains(t, err.Error(), "517")
	assert.NotContains(t, err.Error(), "523")
}

// Canonicalization failures propagate from both new entry points, never a
// silent allow.
func TestRangeAPI_CanonicalError_Propagates(t *testing.T) {
	g, ff := newGuard(t)
	sentinel := errors.New("cannot canonicalize")
	ff.canonFn = func(string) (string, error) { return "", sentinel }

	assert.ErrorIs(t, g.MarkReadRange("/repo/x.go", []byte("a"), LineRange{Start: 1, End: 1}), sentinel)
	assert.ErrorIs(t, g.CheckEditable("/repo/x.go", LineRange{Start: 1, End: 1}), sentinel)
}

// An unexpected filesystem error during the freshness read fails closed, and
// is not misreported as one of the guard verdicts.
func TestCheckEditable_UnexpectedFSError_FailsClosed(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(10)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))
	ff.setReadErr(t, "/repo/a.go", errors.New("permission denied"))

	err := g.CheckEditable("/repo/a.go", LineRange{Start: 1, End: 5})
	require.Error(t, err)
	assert.NotErrorIs(t, err, ErrNotRead)
	assert.NotErrorIs(t, err, ErrStale)
	assert.NotErrorIs(t, err, ErrRegionNotRead)
	assert.NotErrorIs(t, err, fs.ErrNotExist)
}

// ---------------------------------------------------------------------------
// Snapshot / Restore: range coverage is session state and must survive a
// serialize/restore cycle (Temporal replay), including as JSON.
// ---------------------------------------------------------------------------

func TestSnapshot_PreservesRangeCoverage_JSONRoundTrip(t *testing.T) {
	src, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))
	require.NoError(t, src.MarkReadRange("/repo/big.go", body, LineRange{Start: 1, End: 20}))

	data, err := json.Marshal(src.Snapshot())
	require.NoError(t, err)
	var snap Snapshot
	require.NoError(t, json.Unmarshal(data, &snap))

	dst := New(ff)
	dst.Restore(snap)

	assert.NoError(t, dst.CheckEditable("/repo/big.go", LineRange{Start: 5, End: 15}),
		"observed span survives the round trip")
	assert.ErrorIs(t, dst.CheckEditable("/repo/big.go", LineRange{Start: 500, End: 500}), ErrRegionNotRead,
		"unobserved span is still refused after the round trip")
}

// Back-compat: a snapshot from before this feature (Reads only, no Ranges key
// in the JSON) restores with the original semantics — every recorded file
// counts as fully observed.
func TestRestore_LegacySnapshotWithoutRanges_MeansFullCoverage(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(600)
	ff.putFile(t, "/repo/big.go", string(body))

	legacy := []byte(`{"reads":{"/repo/big.go":"` + hashBytes(body) + `"}}`)
	var snap Snapshot
	require.NoError(t, json.Unmarshal(legacy, &snap))
	g.Restore(snap)

	assert.NoError(t, g.CheckWritable("/repo/big.go"))
	assert.NoError(t, g.CheckEditable("/repo/big.go", LineRange{Start: 500, End: 510}),
		"a pre-range snapshot recorded whole-file observations")
}

// A fully-observed file must not serialize a Ranges entry, so new snapshots of
// old-style state keep the old wire shape (and stay replay-stable).
func TestSnapshot_FullReadsProduceNoRangesEntry(t *testing.T) {
	g, ff := newGuard(t)
	ff.putFile(t, "/repo/a.go", "aaa")
	require.NoError(t, g.MarkRead("/repo/a.go", []byte("aaa")))

	snap := g.Snapshot()
	assert.Empty(t, snap.Ranges)

	data, err := json.Marshal(snap)
	require.NoError(t, err)
	assert.NotContains(t, string(data), `"ranges"`)
}

// Snapshot independence extends to the range state: mutating a returned
// snapshot's ranges must not affect the Guard, and vice versa.
func TestSnapshot_RangeState_IsDeepCopy(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(50)
	ff.putFile(t, "/repo/a.go", string(body))
	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 1, End: 10}))

	snap := g.Snapshot()
	require.Len(t, snap.Ranges, 1)
	for k := range snap.Ranges {
		snap.Ranges[k][0] = LineRange{Start: 1, End: 5000}
	}
	assert.ErrorIs(t, g.CheckEditable("/repo/a.go", LineRange{Start: 40, End: 40}), ErrRegionNotRead,
		"tampering with a returned snapshot must not widen the guard's coverage")

	require.NoError(t, g.MarkReadRange("/repo/a.go", body, LineRange{Start: 20, End: 30}))
	snap2 := g.Snapshot()
	g.Restore(Snapshot{})
	assert.Len(t, snap2.Ranges["/repo/a.go"], 2,
		"snapshot must be frozen at capture time")
}

// The range state must be safe under concurrent tool executions (run with
// -race), including snapshot/restore racing with reads and checks.
func TestRangeAPI_ConcurrentAccess_IsRaceFree(t *testing.T) {
	g, ff := newGuard(t)
	body := linesBody(100)
	paths := make([]string, 8)
	for i := range paths {
		paths[i] = "/repo/r" + string(rune('a'+i)) + ".go"
		ff.putFile(t, paths[i], string(body))
	}

	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(1)
		go func(i int, p string) {
			defer wg.Done()
			_ = g.MarkReadRange(p, body, LineRange{Start: 1 + i%50, End: 50 + i%50})
			_ = g.CheckEditable(p, LineRange{Start: 10, End: 20})
			if i%10 == 0 {
				g.Restore(g.Snapshot())
			}
		}(i, paths[i%len(paths)])
	}
	wg.Wait()
}
