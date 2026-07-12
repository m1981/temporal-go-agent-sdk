package base

import (
	"context"
	"fmt"
	"log/slog"
	"runtime/debug"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// DefaultToolExecutionTimeout bounds one in-process tool execution when
// [runtime.AgentLimits].ToolExecutionTimeout is unset. The Temporal backend bounds tool
// execution with activity StartToClose timeouts instead and does not use this value.
const DefaultToolExecutionTimeout = 5 * time.Minute

// ExecuteToolGuarded runs [Runtime.ExecuteTool] with panic recovery and a per-tool
// deadline (AP-08). It is the execution path for in-process (local) runtimes, where a
// panicking tool would otherwise crash the process and a hung tool would stall the run.
//
//   - A panic is recovered and converted to an error wrapping [ErrToolPanicked]. The
//     panic value and stack trace go to the logger ONLY — they are never carried on the
//     returned error, so they can never reach model-facing content.
//   - When the deadline elapses the call returns an error wrapping
//     [context.DeadlineExceeded]. The tool goroutine is signalled via context
//     cancellation; a tool that ignores its context leaks a goroutine until it returns,
//     but the run continues.
//
// Callers turn the returned error into a static model-facing message via
// [ModelFacingToolErrorText] / [ToolFailureContent].
func (rt *Runtime) ExecuteToolGuarded(ctx context.Context, input ExecuteToolInput, memScope interfaces.MemoryScope, timeout time.Duration) (string, error) {
	if timeout <= 0 {
		timeout = DefaultToolExecutionTimeout
	}
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	type toolOutcome struct {
		content string
		err     error
	}
	done := make(chan toolOutcome, 1)
	go func() {
		defer func() {
			if r := recover(); r != nil {
				// Harness-only: the panic value and stack are logged, never returned.
				input.Logger.Error(execCtx, "runtime: tool execution panicked",
					slog.String("scope", "runtime"),
					slog.String("tool", input.ToolName),
					slog.String("toolCallID", input.ToolCallID),
					slog.Any("panic", r),
					slog.String("stack", string(debug.Stack())),
				)
				done <- toolOutcome{err: fmt.Errorf("tool %q: %w", input.ToolName, ErrToolPanicked)}
			}
		}()
		content, err := rt.ExecuteTool(execCtx, input, memScope)
		done <- toolOutcome{content: content, err: err}
	}()

	select {
	case out := <-done:
		return out.content, out.err
	case <-execCtx.Done():
		return "", fmt.Errorf("tool %q: %w", input.ToolName, execCtx.Err())
	}
}
