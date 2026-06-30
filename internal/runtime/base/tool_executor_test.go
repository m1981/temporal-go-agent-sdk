package base_test

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/events"
	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/internal/types"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// mockToolForExecutor is a test tool that implements Tool interface.
type mockToolForExecutor struct {
	name        string
	displayName string
	description string
	execResult  any
	execError   error
}

func (t *mockToolForExecutor) Name() string        { return t.name }
func (t *mockToolForExecutor) DisplayName() string  { return t.displayName }
func (t *mockToolForExecutor) Description() string  { return t.description }
func (t *mockToolForExecutor) Parameters() interfaces.JSONSchema { return nil }
func (t *mockToolForExecutor) Execute(ctx context.Context, args map[string]any) (any, error) {
	return t.execResult, t.execError
}

// TestToolExecutor_BuildToolResultMessage tests message construction from tool result.
func TestToolExecutor_BuildToolResultMessage(t *testing.T) {
	tests := []struct {
		name       string
		toolCallID string
		toolName   string
		content    string
		failed     bool
		wantRole   interfaces.MessageRole
	}{
		{
			name:       "successful tool result",
			toolCallID: "call-123",
			toolName:   "search",
			content:    "search results here",
			failed:     false,
			wantRole:   interfaces.MessageRoleTool,
		},
		{
			name:       "failed tool result",
			toolCallID: "call-456",
			toolName:   "calculator",
			content:    "Tool execution failed: division by zero",
			failed:     true,
			wantRole:   interfaces.MessageRoleTool,
		},
		{
			name:       "rejected tool",
			toolCallID: "call-789",
			toolName:   "deploy",
			content:    "Tool execution was rejected by the user.",
			failed:     false,
			wantRole:   interfaces.MessageRoleTool,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg := base.BuildToolResultMessage(tt.toolCallID, tt.toolName, tt.content)
			if msg.Role != tt.wantRole {
				t.Errorf("Role = %v, want %v", msg.Role, tt.wantRole)
			}
			if msg.ToolCallID != tt.toolCallID {
				t.Errorf("ToolCallID = %v, want %v", msg.ToolCallID, tt.toolCallID)
			}
			if msg.ToolName != tt.toolName {
				t.Errorf("ToolName = %v, want %v", msg.ToolName, tt.toolName)
			}
			if msg.Content != tt.content {
				t.Errorf("Content = %v, want %v", msg.Content, tt.content)
			}
		})
	}
}

// TestToolExecutor_BuildToolCallEvents tests event generation for tool calls.
func TestToolExecutor_BuildToolCallEvents(t *testing.T) {
	tc := base.ToolCallRequest{
		ToolCallID:      "call-abc",
		ToolName:        "calculator",
		ToolDisplayName: "Calculator",
		ToolKind:        types.ToolKindNative,
		Args:            map[string]any{"expression": "2+2"},
		NeedsApproval:   false,
	}
	messageID := "msg-123"

	// Test TOOL_CALL_START event
	startEvent := events.NewAgentToolCallStartEvent(tc.ToolCallID, tc.ToolName, messageID)
	if startEvent.Type() != events.AgentEventTypeToolCallStart {
		t.Errorf("start event type = %v, want %v", startEvent.Type(), events.AgentEventTypeToolCallStart)
	}

	// Test TOOL_CALL_ARGS event
	argsJSON, _ := json.Marshal(tc.Args)
	argsEvent := events.NewAgentToolCallArgsEvent(tc.ToolCallID, string(argsJSON))
	if argsEvent.Type() != events.AgentEventTypeToolCallArgs {
		t.Errorf("args event type = %v, want %v", argsEvent.Type(), events.AgentEventTypeToolCallArgs)
	}

	// Test TOOL_CALL_END event
	endEvent := events.NewAgentToolCallEndEvent(tc.ToolCallID)
	if endEvent.Type() != events.AgentEventTypeToolCallEnd {
		t.Errorf("end event type = %v, want %v", endEvent.Type(), events.AgentEventTypeToolCallEnd)
	}

	// Test TOOL_CALL_RESULT event
	resultContent := "4"
	resultEvent := events.NewAgentToolCallResultEvent(messageID, tc.ToolCallID, resultContent, string(interfaces.MessageRoleTool))
	if resultEvent.Type() != events.AgentEventTypeToolCallResult {
		t.Errorf("result event type = %v, want %v", resultEvent.Type(), events.AgentEventTypeToolCallResult)
	}
}

// TestToolExecutor_AuthorizationResult tests authorization result handling.
func TestToolExecutor_AuthorizationResult(t *testing.T) {
	tests := []struct {
		name        string
		authResult  *base.AuthorizeResult
		wantMsg     string
		wantAllowed bool
	}{
		{
			name:        "allowed",
			authResult:  &base.AuthorizeResult{Allowed: true},
			wantAllowed: true,
		},
		{
			name:        "denied without reason",
			authResult:  &base.AuthorizeResult{Allowed: false},
			wantAllowed: false,
			wantMsg:     "Tool execution was denied by authorization policy.",
		},
		{
			name:        "denied with reason",
			authResult:  &base.AuthorizeResult{Allowed: false, Reason: "insufficient permissions"},
			wantAllowed: false,
			wantMsg:     "Tool execution was denied by authorization policy. Reason: insufficient permissions",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.authResult.Allowed != tt.wantAllowed {
				t.Errorf("Allowed = %v, want %v", tt.authResult.Allowed, tt.wantAllowed)
			}
		})
	}
}

// TestToolExecutor_ApprovalStatusMessages tests approval status message constants.
func TestToolExecutor_ApprovalStatusMessages(t *testing.T) {
	// Verify the message constants exist and have expected values
	expectedMessages := map[types.ApprovalStatus]string{
		types.ApprovalStatusRejected:    "Tool execution was rejected by the user.",
		types.ApprovalStatusUnavailable: "Tool approval could not be completed because no approval handler is configured; continuing without running the tool.",
	}

	for status, expected := range expectedMessages {
		msg := base.GetApprovalStatusMessage(status)
		if msg != expected {
			t.Errorf("status %v: message = %q, want %q", status, msg, expected)
		}
	}
}

// TestToolExecutor_SubAgentDepthCheck tests sub-agent depth limiting.
func TestToolExecutor_SubAgentDepthCheck(t *testing.T) {
	tests := []struct {
		name           string
		currentDepth   int
		maxDepth       int
		wantDelegation bool
		wantMessage    string
	}{
		{
			name:           "within depth limit",
			currentDepth:   0,
			maxDepth:       3,
			wantDelegation: true,
		},
		{
			name:           "at depth limit",
			currentDepth:   3,
			maxDepth:       3,
			wantDelegation: false,
			wantMessage:    "Sub-agent delegation refused: maximum nesting depth (3) reached.",
		},
		{
			name:           "exceeded depth limit",
			currentDepth:   5,
			maxDepth:       3,
			wantDelegation: false,
			wantMessage:    "Sub-agent delegation refused: maximum nesting depth (3) reached.",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			canDelegate, msg := base.CheckSubAgentDepth(tt.currentDepth, tt.maxDepth)
			if canDelegate != tt.wantDelegation {
				t.Errorf("canDelegate = %v, want %v", canDelegate, tt.wantDelegation)
			}
			if !canDelegate && msg != tt.wantMessage {
				t.Errorf("message = %v, want %v", msg, tt.wantMessage)
			}
		})
	}
}

// TestToolExecutor_FormatAuthorizationDeniedMessage tests authorization denied message formatting.
func TestToolExecutor_FormatAuthorizationDeniedMessage(t *testing.T) {
	tests := []struct {
		name     string
		reason   string
		expected string
	}{
		{
			name:     "no reason",
			reason:   "",
			expected: "Tool execution was denied by authorization policy.",
		},
		{
			name:     "with reason",
			reason:   "insufficient permissions",
			expected: "Tool execution was denied by authorization policy. Reason: insufficient permissions",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			msg := base.FormatAuthorizationDeniedMessage(tt.reason)
			if msg != tt.expected {
				t.Errorf("message = %q, want %q", msg, tt.expected)
			}
		})
	}
}
