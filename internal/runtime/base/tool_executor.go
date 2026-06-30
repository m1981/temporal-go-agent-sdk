package base

import (
	"fmt"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/internal/types"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// Message constants for tool execution outcomes.
const (
	MsgToolRejected            = "Tool execution was rejected by the user."
	MsgToolApprovalUnavailable = "Tool approval could not be completed because no approval handler is configured; continuing without running the tool."
	MsgToolUnauthorized        = "Tool execution was denied by authorization policy."
)

// BuildToolResultMessage constructs a tool-role message from tool execution result.
// This is shared between local and temporal runtimes to ensure consistent message format.
// If maxOutputTokens > 0, the content is truncated to fit within the limit.
func BuildToolResultMessage(toolCallID, toolName, content string) interfaces.Message {
	return BuildToolResultMessageWithLimit(toolCallID, toolName, content, 0)
}

// BuildToolResultMessageWithLimit constructs a tool-role message with optional output truncation.
// If maxOutputTokens > 0, the content is truncated to fit within the limit.
func BuildToolResultMessageWithLimit(toolCallID, toolName, content string, maxOutputTokens int) interfaces.Message {
	truncatedContent := content
	if maxOutputTokens > 0 {
		truncatedContent = TruncateToolOutput(content, maxOutputTokens)
	}
	return interfaces.Message{
		Role:       interfaces.MessageRoleTool,
		Content:    truncatedContent,
		ToolName:   toolName,
		ToolCallID: toolCallID,
	}
}

// GetApprovalStatusMessage returns the user-facing message for an approval status.
// Returns empty string for approved status (no message needed).
func GetApprovalStatusMessage(status types.ApprovalStatus) string {
	switch status {
	case types.ApprovalStatusRejected:
		return MsgToolRejected
	case types.ApprovalStatusUnavailable:
		return MsgToolApprovalUnavailable
	case types.ApprovalStatusApproved:
		return ""
	default:
		return ""
	}
}

// FormatAuthorizationDeniedMessage formats a denial message with optional reason.
func FormatAuthorizationDeniedMessage(reason string) string {
	msg := MsgToolUnauthorized
	if strings.TrimSpace(reason) != "" {
		msg = fmt.Sprintf("%s Reason: %s", msg, reason)
	}
	return msg
}

// CheckSubAgentDepth validates whether sub-agent delegation is allowed at the current depth.
// Returns (true, "") if delegation is allowed, (false, message) if depth limit exceeded.
func CheckSubAgentDepth(currentDepth, maxDepth int) (bool, string) {
	if currentDepth >= maxDepth {
		return false, fmt.Sprintf("Sub-agent delegation refused: maximum nesting depth (%d) reached.", maxDepth)
	}
	return true, ""
}

// BuildSubAgentRefusedMessage constructs the message when sub-agent delegation is refused.
func BuildSubAgentRefusedMessage(maxDepth int) string {
	return fmt.Sprintf("Sub-agent delegation refused: maximum nesting depth (%d) reached.", maxDepth)
}
