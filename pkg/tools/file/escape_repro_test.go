//go:build escape_repro

// Build-tagged so the normal suite stays green while the bug is open. Run with
//   go test -tags escape_repro -run TestScopedWrite ./pkg/tools/file/
// The fix (pathscope canonicalizing before the "prefix" check, or the write
// path refusing symlink-traversing targets) should move this into the normal
// suite as a permanent regression guard and flip it to assert refusal.

package file

// REVIEW REPRO (wk pending) — a symlink inside the workspace root followed by
// ".." escapes the scope. pathscope.Check canonicalizes the path, which cleans
// ".." LEXICALLY (so "<root>/link/../pwned" is judged as in-root "<root>/pwned"
// and approved). But CommitWrite writes to the ORIGINAL, un-cleaned path via
// os.OpenFile, where the kernel resolves link -> outside first and ".." after,
// landing the bytes at "<outside>/../pwned" == "<tmp>/pwned", OUTSIDE the root.
//
// The path is built by raw string concatenation on purpose: filepath.Join would
// clean the ".." away before the tool ever saw it, hiding the bug.
//
// PASSES only when the escape is CLOSED (write refused, nothing lands outside).

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestScopedWrite_SymlinkThenDotDot_EscapesRoot(t *testing.T) {
	tmp := t.TempDir()
	root := filepath.Join(tmp, "work")
	outside := filepath.Join(tmp, "outside")
	require.NoError(t, os.MkdirAll(root, 0o755))
	require.NoError(t, os.MkdirAll(outside, 0o755))
	require.NoError(t, os.Symlink(outside, filepath.Join(root, "link")))

	tools, err := NewOSInWorkspace(root)
	require.NoError(t, err)

	// RAW path — no filepath.Join, so ".." survives to the syscall.
	escapePath := root + string(os.PathSeparator) + "link" + string(os.PathSeparator) +
		".." + string(os.PathSeparator) + "pwned"
	_, execErr := tools.Writer().Execute(context.Background(),
		map[string]any{"path": escapePath, "content": "PWNED"})

	landed := filepath.Join(tmp, "pwned")
	if b, statErr := os.ReadFile(landed); statErr == nil {
		t.Fatalf("ESCAPE CONFIRMED: scoped write landed at %s = %q, OUTSIDE root %s (Execute err=%v)",
			landed, string(b), root, execErr)
	}
	require.Error(t, execErr, "a write resolving outside the workspace root must be refused")
}
