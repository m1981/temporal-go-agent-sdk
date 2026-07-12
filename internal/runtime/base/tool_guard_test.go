package base

import (
	"context"
	"testing"
	"time"

	sdkruntime "github.com/m1981/temporal-go-agent-sdk/internal/runtime"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/stretchr/testify/require"
)

// guardStubTool is a minimal tool whose Execute behavior is injectable.
type guardStubTool struct {
	name string
	exec func(ctx context.Context, args map[string]any) (any, error)
}

func (t guardStubTool) Name() string                      { return t.name }
func (t guardStubTool) DisplayName() string               { return t.name }
func (t guardStubTool) Description() string               { return "" }
func (t guardStubTool) Parameters() interfaces.JSONSchema { return nil }
func (t guardStubTool) Execute(ctx context.Context, args map[string]any) (any, error) {
	return t.exec(ctx, args)
}

func guardInput(tool interfaces.Tool) ExecuteToolInput {
	return ExecuteToolInput{
		Logger:     noopLog(),
		Tools:      []interfaces.Tool{tool},
		ToolName:   tool.Name(),
		ToolCallID: "tc-guard",
	}
}

func TestExecuteToolGuarded_SuccessPassthrough(t *testing.T) {
	tool := guardStubTool{name: "ok-tool", exec: func(context.Context, map[string]any) (any, error) {
		return "fine", nil
	}}
	rt := newTestRuntime(sdkruntime.AgentConfig{})

	got, err := rt.ExecuteToolGuarded(context.Background(), guardInput(tool), interfaces.MemoryScope{}, time.Second)
	require.NoError(t, err)
	require.Equal(t, "fine", got)
}

func TestExecuteToolGuarded_PanicIsRecoveredAndNeverForwarded(t *testing.T) {
	// AP-08 / ADK-go mistake: a panicking tool must not crash the process and the
	// panic value must not appear in the returned error (it would reach the model).
	tool := guardStubTool{name: "boom-tool", exec: func(context.Context, map[string]any) (any, error) {
		panic("SECRET-PANIC-VALUE at /home/user/creds.txt")
	}}
	rt := newTestRuntime(sdkruntime.AgentConfig{})

	var err error
	require.NotPanics(t, func() {
		_, err = rt.ExecuteToolGuarded(context.Background(), guardInput(tool), interfaces.MemoryScope{}, time.Second)
	})
	require.Error(t, err)
	require.ErrorIs(t, err, ErrToolPanicked)
	require.NotContains(t, err.Error(), "SECRET-PANIC-VALUE")
	require.NotContains(t, err.Error(), "creds.txt")
	require.Equal(t, MsgToolPanicked, ModelFacingToolErrorText(err))
}

func TestExecuteToolGuarded_TimeoutYieldsDeadlineExceeded(t *testing.T) {
	block := make(chan struct{})
	t.Cleanup(func() { close(block) })
	tool := guardStubTool{name: "slow-tool", exec: func(ctx context.Context, _ map[string]any) (any, error) {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-block:
			return "too late", nil
		}
	}}
	rt := newTestRuntime(sdkruntime.AgentConfig{})

	start := time.Now()
	_, err := rt.ExecuteToolGuarded(context.Background(), guardInput(tool), interfaces.MemoryScope{}, 30*time.Millisecond)
	require.Error(t, err)
	require.ErrorIs(t, err, context.DeadlineExceeded)
	require.Less(t, time.Since(start), 5*time.Second, "timeout must fire near the configured deadline")
	require.Equal(t, MsgToolTimedOut, ModelFacingToolErrorText(err))
}

func TestExecuteToolGuarded_ZeroTimeoutUsesDefault(t *testing.T) {
	tool := guardStubTool{name: "quick", exec: func(context.Context, map[string]any) (any, error) {
		return "v", nil
	}}
	rt := newTestRuntime(sdkruntime.AgentConfig{})

	got, err := rt.ExecuteToolGuarded(context.Background(), guardInput(tool), interfaces.MemoryScope{}, 0)
	require.NoError(t, err)
	require.Equal(t, "v", got)
	require.Greater(t, DefaultToolExecutionTimeout, time.Duration(0))
}
