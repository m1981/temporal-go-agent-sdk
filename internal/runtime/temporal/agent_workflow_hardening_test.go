package temporal

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/testsuite"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/internal/types"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// --- Change 1: typed tool-result envelope (workflow path) ---

func TestAgentWorkflow_ToolResultReachesModelEnveloped(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	rt := testRuntimeForWorkflow(t)

	var llmCalls int
	var secondCallToolMsg *interfaces.Message
	env.RegisterWorkflow(rt.AgentWorkflow)
	env.OnActivity(rt.AgentLLMActivity, mock.Anything, mock.Anything).Return(func(ctx context.Context, in AgentLLMInput) (*AgentLLMResult, error) {
		llmCalls++
		if llmCalls == 1 {
			return &AgentLLMResult{
				Content:   "using tool",
				ToolCalls: []ToolCallRequest{testWorkflowToolCall("tc1", "echo", types.ToolKindNative, nil)},
			}, nil
		}
		for i := range in.Messages {
			if in.Messages[i].Role == interfaces.MessageRoleTool {
				m := in.Messages[i]
				secondCallToolMsg = &m
			}
		}
		return &AgentLLMResult{Content: "after tool"}, nil
	})
	env.OnActivity(rt.AgentToolExecuteActivity, mock.Anything, mock.Anything).Return("raw tool payload", nil)
	env.OnActivity(rt.AgentToolAuthorizeActivity, mock.Anything, mock.Anything).Return(AgentToolAuthorizeResult{Allowed: true}, nil)

	env.ExecuteWorkflow(rt.AgentWorkflow, AgentWorkflowInput{UserPrompt: "run"})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())
	require.NotNil(t, secondCallToolMsg, "second LLM call must include the tool message")
	require.Equal(t,
		base.RenderToolResultEnvelope("echo", base.ToolResultStatusOK, "raw tool payload"),
		secondCallToolMsg.Content,
		"tool output must reach the model only inside the typed envelope")
}

// --- Change 2: static model-facing error text (workflow path) ---

func TestAgentWorkflow_ToolErrorIsStaticText_NoRawError(t *testing.T) {
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	rt := testRuntimeForWorkflow(t)

	var llmCalls int
	var secondCallToolMsg *interfaces.Message
	env.RegisterWorkflow(rt.AgentWorkflow)
	env.OnActivity(rt.AgentLLMActivity, mock.Anything, mock.Anything).Return(func(ctx context.Context, in AgentLLMInput) (*AgentLLMResult, error) {
		llmCalls++
		if llmCalls == 1 {
			return &AgentLLMResult{
				Content:   "using tool",
				ToolCalls: []ToolCallRequest{testWorkflowToolCall("tc1", "bad", types.ToolKindNative, nil)},
			}, nil
		}
		for i := range in.Messages {
			if in.Messages[i].Role == interfaces.MessageRoleTool {
				m := in.Messages[i]
				secondCallToolMsg = &m
			}
		}
		return &AgentLLMResult{Content: "after tool"}, nil
	})
	env.OnActivity(rt.AgentToolExecuteActivity, mock.Anything, mock.Anything).Return("", fmt.Errorf("secret-raw-boom: token=abc123"))
	env.OnActivity(rt.AgentToolAuthorizeActivity, mock.Anything, mock.Anything).Return(AgentToolAuthorizeResult{Allowed: true}, nil)

	env.ExecuteWorkflow(rt.AgentWorkflow, AgentWorkflowInput{UserPrompt: "run"})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())
	require.NotNil(t, secondCallToolMsg)
	require.Contains(t, secondCallToolMsg.Content, base.MsgToolFailed)
	require.NotContains(t, secondCallToolMsg.Content, "secret-raw-boom",
		"raw activity error text must never reach the model")
	require.NotContains(t, secondCallToolMsg.Content, "abc123")
}

func TestAgentWorkflow_ParallelToolHardErrorIsStaticText(t *testing.T) {
	// Authorization activity failure → hard branch error → synthetic tool message must be static.
	var suite testsuite.WorkflowTestSuite
	env := suite.NewTestWorkflowEnvironment()
	rt := testRuntimeForWorkflow(t)

	var llmCalls int
	var secondCallToolMsgs []interfaces.Message
	env.RegisterWorkflow(rt.AgentWorkflow)
	env.OnActivity(rt.AgentLLMActivity, mock.Anything, mock.Anything).Return(func(ctx context.Context, in AgentLLMInput) (*AgentLLMResult, error) {
		llmCalls++
		if llmCalls == 1 {
			return &AgentLLMResult{
				Content:   "using tool",
				ToolCalls: []ToolCallRequest{testWorkflowToolCall("tc1", "bad", types.ToolKindNative, nil)},
			}, nil
		}
		for i := range in.Messages {
			if in.Messages[i].Role == interfaces.MessageRoleTool {
				secondCallToolMsgs = append(secondCallToolMsgs, in.Messages[i])
			}
		}
		return &AgentLLMResult{Content: "after tool"}, nil
	})
	env.OnActivity(rt.AgentToolAuthorizeActivity, mock.Anything, mock.Anything).Return(AgentToolAuthorizeResult{}, fmt.Errorf("secret-auth-backend-down at 10.1.2.3"))

	env.ExecuteWorkflow(rt.AgentWorkflow, AgentWorkflowInput{UserPrompt: "run"})

	require.True(t, env.IsWorkflowCompleted())
	require.NoError(t, env.GetWorkflowError())
	require.Len(t, secondCallToolMsgs, 1)
	require.NotContains(t, secondCallToolMsgs[0].Content, "secret-auth-backend-down")
	require.NotContains(t, secondCallToolMsgs[0].Content, "10.1.2.3")
}

// --- Change 4: uuid.New only inside workflow.SideEffect (AP-04, tr-166b071c) ---

// TestWorkflowCode_UUIDNewOnlyInsideSideEffect scans the files containing workflow
// (non-activity, replayed) code and requires that every uuid.New() call is wrapped in
// workflow.SideEffect. Client-side files (runtime.go etc.) run outside replay and are exempt.
func TestWorkflowCode_UUIDNewOnlyInsideSideEffect(t *testing.T) {
	workflowFiles := []string{"agent_workflow.go", "event_workflow.go", "subagent.go"}
	for _, name := range workflowFiles {
		path := filepath.Join(".", name)
		f, err := os.Open(path)
		require.NoError(t, err)

		var lines []string
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 1024*1024), 1024*1024)
		for sc.Scan() {
			lines = append(lines, sc.Text())
		}
		require.NoError(t, sc.Err())
		require.NoError(t, f.Close())

		for i, line := range lines {
			if !strings.Contains(line, "uuid.New(") {
				continue
			}
			wrapped := false
			for j := i - 2; j < i; j++ {
				if j >= 0 && strings.Contains(lines[j], "workflow.SideEffect") {
					wrapped = true
				}
			}
			require.True(t, wrapped,
				"%s:%d: uuid.New() in workflow code must be wrapped in workflow.SideEffect (AP-04)", name, i+1)
		}
	}
}
