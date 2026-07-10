package file

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/fsguard"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// The tools satisfy the SDK Tool interface.
var (
	_ interfaces.Tool = (*ReadTool)(nil)
	_ interfaces.Tool = (*WriteTool)(nil)
)

func ctx() context.Context { return context.Background() }

// Acceptance (wk-8d3834f9): a write to an existing file that was NOT read this
// session is refused, and the file is left untouched.
func TestWrite_UnreadExistingFile_Refused(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.go")
	require.NoError(t, os.WriteFile(path, []byte("original"), 0o644))

	tools := NewOS()
	_, err := tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "overwrite"})
	assert.ErrorIs(t, err, fsguard.ErrNotRead)

	b, _ := os.ReadFile(path)
	assert.Equal(t, "original", string(b), "a refused write must not touch the file")
}

// Reading first, through the same bundle, authorizes the write.
func TestReadThenWrite_Succeeds(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.go")
	require.NoError(t, os.WriteFile(path, []byte("v1"), 0o644))

	tools := NewOS()
	_, err := tools.Reader().Execute(ctx(), map[string]any{"path": path})
	require.NoError(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "v2"})
	require.NoError(t, err)

	b, _ := os.ReadFile(path)
	assert.Equal(t, "v2", string(b))
}

// Creating a new file needs no prior read.
func TestWrite_NewFile_Succeeds(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "created.go")

	tools := NewOS()
	_, err := tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "hello"})
	require.NoError(t, err)

	b, _ := os.ReadFile(path)
	assert.Equal(t, "hello", string(b))
}

// The read tool returns the file's content to the caller.
func TestRead_ReturnsContent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "doc.txt")
	require.NoError(t, os.WriteFile(path, []byte("the contents"), 0o644))

	out, err := NewOS().Reader().Execute(ctx(), map[string]any{"path": path})
	require.NoError(t, err)
	assert.Equal(t, "the contents", out)
}

// Reading a missing file errors rather than silently marking it read.
func TestRead_MissingFile_Errors(t *testing.T) {
	out, err := NewOS().Reader().Execute(ctx(), map[string]any{"path": filepath.Join(t.TempDir(), "nope")})
	require.Error(t, err)
	assert.Nil(t, out)
}

// A read from one bundle must NOT authorize a write from a different bundle:
// the guard is shared only within a Tools value.
func TestSeparateBundles_DoNotShareReadState(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.go")
	require.NoError(t, os.WriteFile(path, []byte("v1"), 0o644))

	a, b := NewOS(), NewOS()
	_, err := a.Reader().Execute(ctx(), map[string]any{"path": path})
	require.NoError(t, err)

	_, err = b.Writer().Execute(ctx(), map[string]any{"path": path, "content": "v2"})
	assert.ErrorIs(t, err, fsguard.ErrNotRead, "a read in bundle a must not authorize a write in bundle b")
}

// The tool contract the LLM depends on: names and required parameters.
func TestToolContract(t *testing.T) {
	tools := NewOS()
	r, w := tools.Reader(), tools.Writer()

	assert.Equal(t, "read_file", r.Name())
	assert.Equal(t, "Read File", r.DisplayName())
	assert.NotEmpty(t, r.Description())
	assert.Equal(t, []string{"path"}, r.Parameters()["required"])

	assert.Equal(t, "write_file", w.Name())
	assert.Equal(t, "Write File", w.DisplayName())
	assert.NotEmpty(t, w.Description())
	assert.ElementsMatch(t, []string{"path", "content"}, w.Parameters()["required"])
}

// Missing or mistyped arguments are rejected before any filesystem access.
func TestExecute_BadArgs_Rejected(t *testing.T) {
	tools := NewOS()

	_, err := tools.Reader().Execute(ctx(), map[string]any{})
	assert.Error(t, err)

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": "/x"})
	assert.Error(t, err, "missing content must be rejected")

	_, err = tools.Writer().Execute(ctx(), map[string]any{"content": "x"})
	assert.Error(t, err, "missing path must be rejected")
}

// If the file changes on disk between the read and the write, the write is
// refused as stale (the guard's freshness check, surfaced through the tool).
func TestWrite_StaleAfterExternalChange_Refused(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.go")
	require.NoError(t, os.WriteFile(path, []byte("v1"), 0o644))

	tools := NewOS()
	_, err := tools.Reader().Execute(ctx(), map[string]any{"path": path})
	require.NoError(t, err)
	require.NoError(t, os.WriteFile(path, []byte("changed-externally"), 0o644))

	_, err = tools.Writer().Execute(ctx(), map[string]any{"path": path, "content": "v2"})
	assert.ErrorIs(t, err, fsguard.ErrStale)

	b, _ := os.ReadFile(path)
	assert.Equal(t, "changed-externally", string(b))
}
