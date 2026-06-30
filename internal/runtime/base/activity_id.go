package base

import (
	"fmt"
	"strings"
)

// GenerateActivityID creates a deterministic activity ID from the given components.
// Format: prefix_runID_iteration[_extra]
// This enables better debugging and idempotency compared to UUID-based IDs.
func GenerateActivityID(prefix, runID string, iteration int, extra string) string {
	// Sanitize runID to remove characters that might cause issues
	sanitizedRunID := strings.ReplaceAll(runID, " ", "_")

	if extra != "" {
		return fmt.Sprintf("%s_%s_%d_%s", prefix, sanitizedRunID, iteration, extra)
	}
	return fmt.Sprintf("%s_%s_%d", prefix, sanitizedRunID, iteration)
}

// GenerateToolActivityID creates a deterministic activity ID for tool execution.
// Format: Tool_runID_iteration_toolIndex[_toolName]
func GenerateToolActivityID(runID string, iteration, toolIndex int, toolName string) string {
	// Sanitize toolName to remove characters that might cause issues
	sanitizedToolName := strings.ReplaceAll(toolName, " ", "_")

	return fmt.Sprintf("Tool_%s_%d_%d_%s", runID, iteration, toolIndex, sanitizedToolName)
}

// GenerateLLMActivityID creates a deterministic activity ID for LLM calls.
func GenerateLLMActivityID(runID string, iteration int) string {
	return GenerateActivityID("AgentLLM", runID, iteration, "")
}

// GenerateStreamActivityID creates a deterministic activity ID for streaming LLM calls.
func GenerateStreamActivityID(runID string, iteration int) string {
	return GenerateActivityID("AgentLLMStream", runID, iteration, "")
}

// GenerateEventActivityID creates a deterministic activity ID for event publishing.
func GenerateEventActivityID(runID string, iteration int) string {
	return GenerateActivityID("SendAgentEvent", runID, iteration, "")
}

// GenerateConversationActivityID creates a deterministic activity ID for conversation operations.
func GenerateConversationActivityID(runID string, iteration int) string {
	return GenerateActivityID("Conversation", runID, iteration, "")
}

// GenerateRetrieverActivityID creates a deterministic activity ID for retriever operations.
func GenerateRetrieverActivityID(runID string, iteration int) string {
	return GenerateActivityID("AgentRetriever", runID, iteration, "")
}

// GenerateMemoryActivityID creates a deterministic activity ID for memory operations.
func GenerateMemoryActivityID(runID string, iteration int) string {
	return GenerateActivityID("AgentMemory", runID, iteration, "")
}
