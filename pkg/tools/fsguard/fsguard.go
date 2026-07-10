// Package fsguard implements a session-scoped read-before-write precondition for
// file-mutating agent tools (Write/Edit).
//
// It enforces one invariant: a tool may only overwrite a file whose current
// on-disk content matches what was most recently *observed* for that file via a
// Read (or a prior guarded Write). This prevents an agent from editing a file
// from a stale or hallucinated view of its contents, and detects the file being
// changed out from under the agent between the read and the write.
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
)

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
}

// Guard tracks, per session, the content hash observed for each file that has
// been read, and validates writes against current on-disk state. A Guard is
// safe for concurrent use by multiple goroutines.
type Guard struct {
	fsys  Filesystem
	mu    sync.Mutex
	reads map[string]string // canonical path -> observed content hash
}

// New returns a Guard backed by fsys.
func New(fsys Filesystem) *Guard {
	return &Guard{fsys: fsys, reads: make(map[string]string)}
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

// observe stores the content hash of path under its canonical key. MarkRead and
// MarkWritten are the same operation from the Guard's perspective: both assert
// "this is what the file contains as far as the agent knows".
func (g *Guard) observe(path string, content []byte) error {
	key, err := g.fsys.Canonical(path)
	if err != nil {
		return err
	}
	h := hashBytes(content)

	g.mu.Lock()
	defer g.mu.Unlock()
	g.reads[key] = h
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

// Snapshot is a serializable copy of a Guard's observed-read state. It exists so
// the state can live in durable, deterministic workflow state (e.g. a Temporal
// workflow) and be restored on replay, rather than being trapped in the memory
// of a single worker. It is a plain map of canonical path to content hash and
// carries no clock or timestamp, so it is stable across replays.
type Snapshot struct {
	Reads map[string]string `json:"reads"`
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
	return Snapshot{Reads: reads}
}

// Restore replaces the Guard's observed state with a deep copy of s. Any state
// recorded before the call is discarded.
func (g *Guard) Restore(s Snapshot) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.reads = make(map[string]string, len(s.Reads))
	for k, v := range s.Reads {
		g.reads[k] = v
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
	return filepath.Clean(abs), nil
}
