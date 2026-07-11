// Package fsguard implements a session-scoped read-before-write precondition for
// file-mutating agent tools (Write/Edit).
//
// It enforces one invariant: a tool may only overwrite a file whose current
// on-disk content matches what was most recently *observed* for that file via a
// Read (or a prior guarded Write). This prevents an agent from editing a file
// from a stale or hallucinated view of its contents, and detects the file being
// changed out from under the agent between the read and the write.
//
// On top of freshness, the guard can optionally track WHICH lines of a file
// were observed (MarkReadRange) and require an edit's target span to fall
// within them (CheckEditable), so a partial read — a Read with offset/limit —
// does not authorize rewriting lines it never surfaced. A plain MarkRead keeps
// its meaning: whole file observed, any span editable. See ADR-009.
//
// Freshness is compared by content hash rather than mtime: mtime is
// attacker-controllable (touch -t / os.Chtimes) and therefore not an integrity
// signal, whereas a content hash detects any change regardless of timestamp.
//
// The Guard talks to the filesystem only through the Filesystem seam, so its
// logic is exercised in tests against an in-memory fake with no real disk I/O.
package fsguard

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"sync"
)

// Sentinel errors returned by CheckWritable. Callers match with errors.Is.
//
// These messages are the stable, model-facing contract text. They MUST remain
// static and MUST NOT be built from untrusted input (the file path or its
// content): tool-result text is fed back into the model, so interpolating
// attacker-influenced data here would open a prompt-injection channel.
var (
	// ErrNotRead means the file exists but was never observed via a Read in
	// this session, so writing it would risk a blind overwrite.
	ErrNotRead = errors.New("file has not been read yet; read it first before writing to it")

	// ErrStale means the file's on-disk content changed since it was read, so
	// the agent's view of it is out of date.
	ErrStale = errors.New("file has been modified since read; read it again before writing to it")

	// ErrRegionNotRead means the file is fresh, but the edit targets lines that
	// were never observed via a Read in this session (only part of the file was
	// read), so editing there would rewrite unseen content.
	ErrRegionNotRead = errors.New("edit targets lines that have not been read; read that region first before editing it")

	// ErrInvalidRange means a supplied LineRange is malformed (Start < 1 or
	// End < Start).
	ErrInvalidRange = errors.New("invalid line range: start must be >= 1 and end must be >= start")
)

// LineRange is a closed, 1-based interval of lines: Start is the first line
// observed and End the last, inclusive. Start must be >= 1 and End >= Start.
//
// Coverage is tracked in lines rather than bytes because that is the unit the
// surrounding tools speak: a partial Read is expressed as a line offset/limit,
// and an Edit targets a line span. See ADR-009 for the trade-off against byte
// ranges.
type LineRange struct {
	Start int `json:"start"`
	End   int `json:"end"`
}

// valid reports whether r is a well-formed range.
func (r LineRange) valid() bool { return r.Start >= 1 && r.End >= r.Start }

// Filesystem is the seam through which a Guard observes file state. Production
// wiring uses OSFilesystem; tests inject an in-memory fake.
type Filesystem interface {
	// ReadFile returns the current bytes at path, or an error satisfying
	// errors.Is(err, fs.ErrNotExist) if the path does not exist.
	ReadFile(path string) ([]byte, error)

	// Canonical returns a stable identity key for path, so different spellings
	// of the same file (relative, symlinked, case-variant) collapse to one
	// entry. Getting this wrong is a correctness AND a security bug: an
	// unresolved alias can skip the freshness check.
	Canonical(path string) (string, error)

	// WriteFile writes data to path, creating it or truncating an existing
	// file. It is used only by CommitWrite.
	WriteFile(path string, data []byte, perm fs.FileMode) error
}

// Guard tracks, per session, the content hash observed for each file that has
// been read, and validates writes against current on-disk state. A Guard is
// safe for concurrent use by multiple goroutines.
type Guard struct {
	fsys Filesystem

	// writeMu serializes CommitWrite so its verify-then-write sequence is
	// atomic against other guarded writes. It is separate from mu (which only
	// guards the reads map) so it can be held across filesystem I/O without
	// blocking MarkRead/Snapshot or deadlocking on the map lock.
	writeMu sync.Mutex

	mu    sync.Mutex
	reads map[string]string // canonical path -> observed content hash

	// ranges holds, for files observed only partially (MarkReadRange), the
	// merged 1-based line ranges seen so far — sorted, disjoint, and
	// non-adjacent. A path present in reads but ABSENT here was observed in
	// full; that absence encoding is what keeps MarkRead's semantics and old
	// snapshots unchanged. Guarded by mu, like reads.
	ranges map[string][]LineRange
}

// New returns a Guard backed by fsys.
func New(fsys Filesystem) *Guard {
	return &Guard{
		fsys:   fsys,
		reads:  make(map[string]string),
		ranges: make(map[string][]LineRange),
	}
}

// MarkRead records that content was the observed state of path (call this after
// a successful Read).
func (g *Guard) MarkRead(path string, content []byte) error {
	return g.observe(path, content)
}

// MarkWritten records content as the new observed state of path (call this after
// a successful Write/Edit), so a tool may perform successive edits to its own
// output without an intervening Read.
func (g *Guard) MarkWritten(path string, content []byte) error {
	return g.observe(path, content)
}

// MarkReadRange records that content is the observed state of path, but that
// only the given 1-based line ranges of it were actually surfaced (call this
// after a partial Read, e.g. one with a line offset/limit). Ranges from
// successive calls against unchanged content accumulate, with overlapping and
// adjacent ranges merged; if the content hash differs from the previous
// observation, previously recorded ranges described a different file body and
// are discarded. Calling it with no ranges records freshness only. A malformed
// range is rejected with ErrInvalidRange and nothing is recorded.
//
// The ranges are caller-asserted: the Guard does not verify them against
// content's actual line count, the same trust it already extends to content
// itself (see ADR-009).
func (g *Guard) MarkReadRange(path string, content []byte, ranges ...LineRange) error {
	for _, r := range ranges {
		if !r.valid() {
			return ErrInvalidRange
		}
	}
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}
	h := hashBytes(content)

	g.mu.Lock()
	defer g.mu.Unlock()
	prev, seen := g.reads[key]
	existing, partial := g.ranges[key]
	if seen && prev == h && !partial {
		// Already observed in full and unchanged: a partial re-read adds no
		// information and must not downgrade coverage.
		return nil
	}
	if !seen || prev != h {
		// First observation, or the content changed since the last one: any
		// previously recorded ranges belong to a different body.
		existing = nil
	}
	g.reads[key] = h
	g.ranges[key] = mergeRanges(existing, ranges)
	return nil
}

// CheckEditable reports whether the given line span of path may be edited now.
// It first applies the same freshness check as CheckWritable (nil for a file
// that does not exist yet; ErrNotRead / ErrStale / a propagated filesystem
// error otherwise), then verifies coverage: the span must fall within the
// union of the line ranges observed for the file. A file observed in full
// (MarkRead, MarkWritten, or a CommitWrite) covers every span; a partially
// observed file yields ErrRegionNotRead for a span not fully inside its
// observed ranges. A malformed span is rejected with ErrInvalidRange.
//
// CheckWritable is unchanged and remains the whole-file-overwrite check;
// CheckEditable is the stricter precondition for region edits.
func (g *Guard) CheckEditable(path string, span LineRange) error {
	if !span.valid() {
		return ErrInvalidRange
	}
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}

	current, err := g.fsys.ReadFile(path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil
		}
		return err
	}
	currentHash := hashBytes(current)

	g.mu.Lock()
	defer g.mu.Unlock()
	observed, seen := g.reads[key]
	switch {
	case !seen:
		return ErrNotRead
	case observed != currentHash:
		return ErrStale
	}
	rs, partial := g.ranges[key]
	if !partial {
		return nil // observed in full
	}
	// rs is sorted, disjoint, and non-adjacent, so a span covered by the union
	// must sit entirely inside a single merged range.
	for _, r := range rs {
		if r.Start <= span.Start && span.End <= r.End {
			return nil
		}
	}
	return ErrRegionNotRead
}

// mergeRanges returns the union of the two range sets as a sorted, disjoint,
// non-adjacent list (adjacent ranges like 1-10 and 11-20 combine to 1-20). It
// builds a fresh slice and never mutates its inputs, so stored range slices
// stay immutable once published.
func mergeRanges(a, b []LineRange) []LineRange {
	all := make([]LineRange, 0, len(a)+len(b))
	all = append(all, a...)
	all = append(all, b...)
	sort.Slice(all, func(i, j int) bool { return all[i].Start < all[j].Start })

	merged := make([]LineRange, 0, len(all))
	for _, r := range all {
		if n := len(merged); n > 0 && r.Start <= merged[n-1].End+1 {
			if r.End > merged[n-1].End {
				merged[n-1].End = r.End
			}
			continue
		}
		merged = append(merged, r)
	}
	return merged
}

// observe stores the content hash of path under its canonical key. MarkRead and
// MarkWritten are the same operation from the Guard's perspective: both assert
// "this is what the file contains as far as the agent knows". A full
// observation supersedes any partial-range record for the file.
func (g *Guard) observe(path string, content []byte) error {
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}
	h := hashBytes(content)

	g.mu.Lock()
	defer g.mu.Unlock()
	g.reads[key] = h
	delete(g.ranges, key) // whole file observed: absence in ranges = full coverage
	return nil
}

// CheckWritable reports whether path may be written now. It returns nil when the
// file does not exist (a fresh create, nothing to clobber), or when it was
// observed and its on-disk content is unchanged since. It returns ErrNotRead or
// ErrStale for the two guarded conditions, and propagates any other filesystem
// error (fail-closed: an unreadable file is never reported as writable).
func (g *Guard) CheckWritable(path string) error {
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}

	current, err := g.fsys.ReadFile(path)
	if err != nil {
		if errors.Is(err, fs.ErrNotExist) {
			return nil
		}
		return err
	}
	currentHash := hashBytes(current)

	g.mu.Lock()
	observed, seen := g.reads[key]
	g.mu.Unlock()

	switch {
	case !seen:
		return ErrNotRead
	case observed != currentHash:
		return ErrStale
	default:
		return nil
	}
}

// CommitWrite verifies the write precondition and performs the write as one
// operation, then records the new content as the observed state. It returns the
// same ErrNotRead/ErrStale/filesystem errors as CheckWritable, in which case the
// file is left untouched. Compared with a separate CheckWritable-then-write, it
// re-verifies freshness immediately before writing and holds a lock across the
// sequence, shrinking (though, against out-of-process writers, not eliminating)
// the time-of-check/time-of-use window.
func (g *Guard) CommitWrite(path string, content []byte, perm fs.FileMode) error {
	g.writeMu.Lock()
	defer g.writeMu.Unlock()

	if err := g.CheckWritable(path); err != nil {
		return err
	}
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}
	if err := g.fsys.WriteFile(path, content, perm); err != nil {
		return err
	}

	g.mu.Lock()
	g.reads[key] = hashBytes(content)
	delete(g.ranges, key) // the full content was written, so it is fully observed
	g.mu.Unlock()
	return nil
}

// Snapshot is a serializable copy of a Guard's observed-read state. It exists so
// the state can live in durable, deterministic workflow state (e.g. a Temporal
// workflow) and be restored on replay, rather than being trapped in the memory
// of a single worker. It is a plain map of canonical path to content hash and
// carries no clock or timestamp, so it is stable across replays.
type Snapshot struct {
	Reads map[string]string `json:"reads"`

	// Ranges holds, for files that were only partially observed, the merged
	// line ranges seen so far. A path present in Reads but absent here was
	// observed in full (the pre-range semantics), so snapshots taken before
	// this field existed restore with their original meaning.
	Ranges map[string][]LineRange `json:"ranges,omitempty"`
}

// Snapshot returns an independent copy of the Guard's current observed state.
// Mutating the result does not affect the Guard, and vice versa.
func (g *Guard) Snapshot() Snapshot {
	g.mu.Lock()
	defer g.mu.Unlock()
	reads := make(map[string]string, len(g.reads))
	for k, v := range g.reads {
		reads[k] = v
	}
	var ranges map[string][]LineRange
	if len(g.ranges) > 0 {
		ranges = make(map[string][]LineRange, len(g.ranges))
		for k, v := range g.ranges {
			ranges[k] = append([]LineRange(nil), v...)
		}
	}
	return Snapshot{Reads: reads, Ranges: ranges}
}

// Restore replaces the Guard's observed state with a deep copy of s. Any state
// recorded before the call is discarded. A snapshot taken before range
// tracking existed carries no Ranges, so every restored file counts as fully
// observed — its original meaning.
func (g *Guard) Restore(s Snapshot) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.reads = make(map[string]string, len(s.Reads))
	for k, v := range s.Reads {
		g.reads[k] = v
	}
	g.ranges = make(map[string][]LineRange, len(s.Ranges))
	for k, v := range s.Ranges {
		g.ranges[k] = append([]LineRange(nil), v...)
	}
}

// hashBytes returns the stable content hash used for freshness comparison.
func hashBytes(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

// OSFilesystem is the production Filesystem backed by the real OS. It is
// plumbing rather than guard logic, so it is implemented up front; the behavior
// under test lives entirely in Guard.
type OSFilesystem struct{}

// ReadFile reads path from disk.
func (OSFilesystem) ReadFile(path string) ([]byte, error) {
	return os.ReadFile(path)
}

// Canonical resolves path to an absolute, symlink-resolved key. For a
// not-yet-existing file (a fresh create) it falls back to the cleaned absolute
// path, since EvalSymlinks requires the target to exist.
func (OSFilesystem) Canonical(path string) (string, error) {
	abs, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	if resolved, err := filepath.EvalSymlinks(abs); err == nil {
		return resolved, nil
	}
	// The target does not exist yet (a fresh create). Resolve the parent
	// directory instead and rejoin the base name, so the key matches what
	// EvalSymlinks returns once the file exists. Without this, a
	// create-then-edit sequence keys its two operations differently (e.g. when
	// a parent is a symlink, as /var is on macOS) and orphans recorded state.
	dir, base := filepath.Split(abs)
	if resolvedDir, err := filepath.EvalSymlinks(filepath.Clean(dir)); err == nil {
		return filepath.Join(resolvedDir, base), nil
	}
	return filepath.Clean(abs), nil
}

// WriteFile writes data to path on disk.
func (OSFilesystem) WriteFile(path string, data []byte, perm fs.FileMode) error {
	return os.WriteFile(path, data, perm)
}
