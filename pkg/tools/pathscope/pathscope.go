// Package pathscope bounds where file-tool paths may resolve: a Scope is
// configured with a workspace root, and Check refuses any path that, once
// canonicalized (absolute, symlinks resolved, ".." cleaned), lands outside
// that root.
//
// It is the destination-bounds sibling of pkg/tools/fsguard (ADR-007 drew this
// boundary explicitly): fsguard answers "is the agent's view of this file
// fresh?", pathscope answers "is the agent allowed to touch this location at
// all?". Neither subsumes the other.
//
// Canonicalization happens through the Canonicalizer seam, so the boundary
// logic is unit-tested against an in-memory fake; production wiring reuses
// fsguard.OSFilesystem's Canonical (which resolves the parent directory for a
// not-yet-existing target, so a fresh create under a symlinked parent is still
// resolved — and therefore still bounded — correctly).
package pathscope

import (
	"errors"
	"path/filepath"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/fsguard"
)

// ErrOutsideWorkspace is returned by Check for any path resolving outside the
// workspace root. Callers match with errors.Is.
//
// The message is the stable, model-facing contract text. It MUST remain static
// and MUST NOT embed the offending path (or the root): tool-result text is fed
// back into the model, so interpolating attacker-influenced data here would
// open a prompt-injection channel.
var ErrOutsideWorkspace = errors.New("path is outside the allowed workspace; only paths inside the workspace may be accessed")

// Canonicalizer is the seam through which a Scope resolves paths. It is the
// minimal slice of fsguard.Filesystem that pathscope needs: a Scope must never
// read or write file contents, only resolve identities, and the narrow
// interface makes that impossible by construction (and keeps test fakes tiny).
// fsguard.OSFilesystem satisfies it.
type Canonicalizer interface {
	// Canonical resolves path to an absolute, symlink-resolved, cleaned form.
	// For a not-yet-existing target it must resolve the parent directory and
	// rejoin the base name (see fsguard.OSFilesystem.Canonical), so the result
	// reflects where a create would actually land.
	Canonical(path string) (string, error)
}

// Scope refuses paths resolving outside a workspace root. The zero value is
// unusable; construct with New or NewOS. A Scope is immutable after
// construction and safe for concurrent use.
type Scope struct {
	c    Canonicalizer
	root string // canonical form of the workspace root
}

// New returns a Scope rooted at root, resolving paths through c. The root
// itself is canonicalized once here, so a root reached via symlinks (e.g. a
// macOS /var temp dir) compares correctly against resolved paths.
func New(root string, c Canonicalizer) (*Scope, error) {
	canonRoot, err := c.Canonical(root)
	if err != nil {
		return nil, err
	}
	return &Scope{c: c, root: canonRoot}, nil
}

// NewOS returns a Scope rooted at root, backed by the real filesystem
// (fsguard.OSFilesystem's canonicalization).
func NewOS(root string) (*Scope, error) {
	return New(root, fsguard.OSFilesystem{})
}

// Check returns nil when path canonicalizes to the workspace root or to a
// location strictly inside it, ErrOutsideWorkspace when it resolves anywhere
// else, and the canonicalization error itself if resolution fails
// (fail-closed: an unresolvable path is never reported as in scope).
func (s *Scope) Check(path string) error {
	resolved, err := s.c.Canonical(path)
	if err != nil {
		return err
	}
	if resolved == s.root {
		return nil
	}
	// Compare against the root with a trailing separator, so a sibling that
	// merely shares the root's name as a string prefix ("/w/app" vs
	// "/w/app-evil") is correctly outside.
	prefix := s.root
	if !strings.HasSuffix(prefix, string(filepath.Separator)) {
		prefix += string(filepath.Separator)
	}
	if strings.HasPrefix(resolved, prefix) {
		return nil
	}
	return ErrOutsideWorkspace
}
