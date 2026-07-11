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
	"strings"
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

	// ErrConcurrentCreate means the guard verified that a path did not exist,
	// but another process created it in the gap before the write; the create
	// was refused, so the concurrently created file survives untouched. It is
	// distinct from ErrStale, which presumes a prior read of the file — a
	// raced create was never read at all, and the corrective action is a
	// first read, not a re-read.
	ErrConcurrentCreate = errors.New("file was created concurrently by another process; read it first before writing to it")
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

	// CreateExclusive writes data to a path that must not exist yet
	// (O_CREATE|O_EXCL semantics). If the path already exists — including one
	// created by another process a moment earlier — it returns an error
	// satisfying errors.Is(err, fs.ErrExist) and leaves the existing file
	// untouched. CommitWrite uses it for new-file creates so a racing
	// external create is refused rather than clobbered.
	CreateExclusive(path string, data []byte, perm fs.FileMode) error

	// WriteFileAtomic replaces the content of path in one atomic step, so a
	// concurrent reader observes either the old content or the new in full,
	// never a torn intermediate (production: write a temp file in path's
	// directory, then rename over path). CommitWrite uses it for
	// existing-file overwrites.
	WriteFileAtomic(path string, data []byte, perm fs.FileMode) error
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

	// All filesystem I/O goes through the canonical key, not the raw path:
	// the raw spelling may traverse symlinks and ".." that the OS resolves to
	// a DIFFERENT location than the one this state is keyed (and any scope
	// decision was made) on. See wk-20a409b1.
	current, err := g.fsys.ReadFile(key)
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

	current, err := g.fsys.ReadFile(key) // canonical, not raw: see CheckEditable
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
// same ErrNotRead/ErrStale/filesystem errors as CheckWritable — plus
// ErrConcurrentCreate for a lost create race — and in every refusal case the
// on-disk file is left untouched.
//
// Against out-of-process writers it guarantees (ADR-010):
//   - A new-file create uses O_EXCL semantics (Filesystem.CreateExclusive), so
//     a file created externally between the existence check and the write is
//     refused with ErrConcurrentCreate, never clobbered.
//   - An existing-file overwrite replaces content atomically
//     (Filesystem.WriteFileAtomic, temp+rename in production), so a concurrent
//     reader observes complete old or complete new bytes, never a torn write.
//   - Freshness is re-verified from a re-read as late as the seam allows,
//     immediately before the write call, under writeMu.
//
// It does NOT close the TOCTOU window for existing files: an external
// modification landing after that final re-read but before the rename is still
// overwritten. A content-hash guard cannot eliminate that residual without an
// OS-level compare-and-swap; see ADR-010, "Residual risk".
func (g *Guard) CommitWrite(path string, content []byte, perm fs.FileMode) error {
	g.writeMu.Lock()
	defer g.writeMu.Unlock()

	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}

	// The freshness re-read happens here, immediately before the write call,
	// so the unavoidable check-to-write gap is as small as the seam allows.
	//
	// SECURITY (wk-20a409b1): every filesystem call below uses key — the
	// canonical, symlink-resolved path — never the raw path. The raw spelling
	// may traverse symlinks and ".." that the OS resolves to a location other
	// than the one the freshness state is keyed on (and that any pathscope
	// check approved), so writing the raw path could land bytes outside an
	// approved workspace. The path the caller's scope approved is exactly the
	// path written.
	current, err := g.fsys.ReadFile(key)
	switch {
	case errors.Is(err, fs.ErrNotExist):
		// Believed new: create exclusively, so a create that raced in after
		// the read above fails closed instead of being clobbered.
		if cerr := g.fsys.CreateExclusive(key, content, perm); cerr != nil {
			if errors.Is(cerr, fs.ErrExist) {
				return ErrConcurrentCreate
			}
			return cerr
		}
	case err != nil:
		return err // fail closed: an unreadable file is never written
	default:
		g.mu.Lock()
		observed, seen := g.reads[key]
		g.mu.Unlock()
		if !seen {
			return ErrNotRead
		}
		if observed != hashBytes(current) {
			return ErrStale
		}
		// Atomic replace: readers see old or new content, never torn. A
		// modification landing between the re-read above and the rename inside
		// WriteFileAtomic is still overwritten — the ADR-010 residual.
		if werr := g.fsys.WriteFileAtomic(key, content, perm); werr != nil {
			return werr
		}
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

// Canonical resolves path to an absolute, symlink-resolved key by walking it
// component by component exactly as the kernel would: each symlink is resolved
// where it is encountered, and each ".." applies to the already-RESOLVED
// prefix — never lexically to an unresolved symlink.
//
// This ordering is a security invariant (wk-20a409b1): cleaning ".." lexically
// first (as filepath.Abs/Clean do) judges "<root>/link/../x" as "<root>/x",
// while the kernel resolves link to its target BEFORE applying "..", so the
// raw path lands outside the root. Canonical must agree with the kernel, and
// the Guard then operates on this canonical path (see CommitWrite), so the
// location that scope checks approve is the location that gets written.
//
// For a not-yet-existing suffix (a fresh create) the existing prefix is fully
// resolved and the remaining components are appended; below a nonexistent
// component nothing on disk can be a symlink, so lexical ".." handling there
// matches what the kernel would do if the directories were created first. Any
// other resolution failure (permissions, I/O, a symlink loop) is returned as
// an error — fail closed, never a guessed key.
func (OSFilesystem) Canonical(path string) (string, error) {
	abs := path
	if !filepath.IsAbs(abs) {
		wd, err := os.Getwd()
		if err != nil {
			return "", err
		}
		// Plain concatenation, NOT filepath.Join: Join would clean ".."
		// segments lexically before the symlink-aware walk sees them.
		abs = wd + string(filepath.Separator) + abs
	}
	return resolveSymlinkAware(abs)
}

// maxSymlinkHops bounds symlink chains during resolution, mirroring the
// kernel's ELOOP limit (40 on Linux).
const maxSymlinkHops = 40

// resolveSymlinkAware resolves the absolute path abs with kernel-order
// semantics: symlinks first, ".." against the resolved prefix. See the
// Canonical doc comment for why the order matters.
func resolveSymlinkAware(abs string) (string, error) {
	vol := filepath.VolumeName(abs)
	resolved := vol + string(filepath.Separator)
	pending := splitPathComponents(abs[len(vol):])
	var missing []string // lexical tail below the first nonexistent component
	hops := 0

	for len(pending) > 0 {
		c := pending[0]
		pending = pending[1:]

		if len(missing) > 0 {
			// Below a nonexistent component nothing can be a symlink, so
			// ".." here safely pops the pending tail (or falls through to
			// the resolved prefix once the tail is empty).
			if c == ".." {
				missing = missing[:len(missing)-1]
			} else {
				missing = append(missing, c)
			}
			continue
		}
		if c == ".." {
			// resolved is fully symlink-free by induction, so its lexical
			// parent IS its kernel parent. Dir of a root is itself.
			resolved = filepath.Dir(resolved)
			continue
		}
		next := filepath.Join(resolved, c)
		fi, err := os.Lstat(next)
		if err != nil {
			if errors.Is(err, fs.ErrNotExist) {
				missing = append(missing, c)
				continue
			}
			return "", err // fail closed on any other resolution error
		}
		if fi.Mode()&fs.ModeSymlink == 0 {
			resolved = next
			continue
		}
		hops++
		if hops > maxSymlinkHops {
			return "", &fs.PathError{Op: "canonical", Path: abs, Err: errors.New("too many levels of symbolic links")}
		}
		target, err := os.Readlink(next)
		if err != nil {
			return "", err
		}
		if filepath.IsAbs(target) {
			tvol := filepath.VolumeName(target)
			resolved = tvol + string(filepath.Separator)
			target = target[len(tvol):]
		}
		// A relative target resolves against the link's directory, which is
		// exactly the current resolved prefix. Prepend the target's components
		// so any ".." or nested symlink inside it is walked, not cleaned.
		pending = append(splitPathComponents(target), pending...)
	}
	if len(missing) > 0 {
		return filepath.Join(append([]string{resolved}, missing...)...), nil
	}
	return resolved, nil
}

// splitPathComponents splits a path suffix into its components, dropping empty
// segments and "." (both lexically neutral); ".." is preserved for the walk.
func splitPathComponents(p string) []string {
	parts := strings.FieldsFunc(p, func(r rune) bool {
		return r == '/' || r == filepath.Separator
	})
	comps := parts[:0]
	for _, c := range parts {
		if c != "." {
			comps = append(comps, c)
		}
	}
	return comps
}

// CreateExclusive writes data to path with O_CREATE|O_EXCL semantics: it fails
// with an error satisfying errors.Is(err, fs.ErrExist) if path already exists.
// The exclusivity is enforced by the kernel at open time, so two processes
// racing to create the same path cannot both succeed.
func (OSFilesystem) CreateExclusive(path string, data []byte, perm fs.FileMode) error {
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, perm)
	if err != nil {
		return err
	}
	_, werr := f.Write(data)
	cerr := f.Close()
	if werr != nil {
		return werr
	}
	return cerr
}

// WriteFileAtomic replaces path's content by staging a temp file in the same
// directory (rename is only atomic within one filesystem) and renaming it over
// path. A concurrent reader therefore observes either the old or the new
// content in full, never a torn intermediate, and the path never transiently
// disappears. An existing file keeps its current permission bits; a fresh file
// gets perm. The staged file is fsynced before the rename so a crash cannot
// publish an empty rename target. Trade-offs (inode change breaks hardlinks;
// extra syscalls) are recorded in ADR-010.
func (OSFilesystem) WriteFileAtomic(path string, data []byte, perm fs.FileMode) error {
	mode := perm
	if fi, err := os.Stat(path); err == nil {
		mode = fi.Mode().Perm()
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".tmp-*")
	if err != nil {
		return err
	}
	name := tmp.Name()
	err = fillAndClose(tmp, data, mode)
	if err == nil {
		err = os.Rename(name, path)
	}
	if err != nil {
		os.Remove(name) // best-effort cleanup of the staged file
		return err
	}
	return nil
}

// fillAndClose writes data to the staged temp file, applies mode, syncs, and
// closes it, returning the first error encountered (Close always runs).
func fillAndClose(f *os.File, data []byte, mode fs.FileMode) error {
	_, err := f.Write(data)
	if err == nil {
		err = f.Chmod(mode)
	}
	if err == nil {
		err = f.Sync()
	}
	if cerr := f.Close(); err == nil {
		err = cerr
	}
	return err
}
