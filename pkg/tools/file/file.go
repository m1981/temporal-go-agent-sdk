// Package file provides read_file and write_file agent tools that share a
// single read-before-write guard (pkg/tools/fsguard). A write to an existing
// file is refused unless the same session read that file first, so the model
// cannot overwrite a file from a stale or hallucinated view of its contents.
//
// The two tools MUST come from the same Tools value so they share one Guard;
// constructing them separately would give each its own empty read-state and
// defeat the guard.
package file

import (
	"context"
	"errors"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/fsguard"
)

var (
	_ interfaces.Tool = (*ReadTool)(nil)
	_ interfaces.Tool = (*WriteTool)(nil)
)

// defaultPerm is the mode used when creating a new file.
const defaultPerm = 0o644

// Tools bundles a reader and a writer sharing one read-before-write guard.
type Tools struct {
	fsys  fsguard.Filesystem
	guard *fsguard.Guard
}

// New builds a Tools over an arbitrary filesystem seam (tests inject a fake or
// a temp-dir-backed OSFilesystem).
func New(fsys fsguard.Filesystem) *Tools {
	return &Tools{fsys: fsys, guard: fsguard.New(fsys)}
}

// NewOS builds a Tools backed by the real filesystem.
func NewOS() *Tools { return New(fsguard.OSFilesystem{}) }

// Reader returns the read_file tool.
func (t *Tools) Reader() *ReadTool { return &ReadTool{t: t} }

// Writer returns the write_file tool.
func (t *Tools) Writer() *WriteTool { return &WriteTool{t: t} }

// ReadTool reads a file and records the observation with the shared guard.
type ReadTool struct{ t *Tools }

func (*ReadTool) Name() string        { return "read_file" }
func (*ReadTool) DisplayName() string { return "Read File" }
func (*ReadTool) Description() string {
	return "Read a text file's contents. You must read a file with this tool before you can write to it."
}
func (*ReadTool) Parameters() interfaces.JSONSchema {
	return tools.Params(
		map[string]interfaces.JSONSchema{
			"path": tools.ParamString("Path of the file to read"),
		},
		"path",
	)
}

// Execute reads args["path"] and records it as observed with the shared guard.
func (r *ReadTool) Execute(ctx context.Context, args map[string]any) (any, error) {
	path, ok := args["path"].(string)
	if !ok || path == "" {
		return nil, errors.New("read_file: 'path' is required")
	}
	content, err := r.t.fsys.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if err := r.t.guard.MarkRead(path, content); err != nil {
		return nil, err
	}
	return string(content), nil
}

// WriteTool writes a file through the shared guard's atomic CommitWrite.
type WriteTool struct{ t *Tools }

func (*WriteTool) Name() string        { return "write_file" }
func (*WriteTool) DisplayName() string { return "Write File" }
func (*WriteTool) Description() string {
	return "Write (create or overwrite) a text file. Overwriting an existing file requires that you read it first this session."
}
func (*WriteTool) Parameters() interfaces.JSONSchema {
	return tools.Params(
		map[string]interfaces.JSONSchema{
			"path":    tools.ParamString("Path of the file to write"),
			"content": tools.ParamString("Full new contents of the file"),
		},
		"path", "content",
	)
}

// Execute writes args["content"] to args["path"] via the guard, so an unread
// existing file is refused before any bytes are written.
func (w *WriteTool) Execute(ctx context.Context, args map[string]any) (any, error) {
	path, ok := args["path"].(string)
	if !ok || path == "" {
		return nil, errors.New("write_file: 'path' is required")
	}
	content, ok := args["content"].(string)
	if !ok {
		return nil, errors.New("write_file: 'content' is required")
	}
	if err := w.t.guard.CommitWrite(path, []byte(content), defaultPerm); err != nil {
		return nil, err
	}
	return map[string]any{"path": path, "bytes": len(content)}, nil
}
