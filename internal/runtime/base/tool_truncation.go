package base

import (
	"fmt"
	"strings"
)

const (
	// charsPerToken is the approximate number of characters per token.
	// This is a rough estimate; actual tokenization varies by model.
	charsPerToken = 4

	// truncationMarker is appended to truncated content.
	truncationMarker = "..."

	// minTruncationLength is the minimum content length to keep when truncating.
	minTruncationLength = 100
)

// EstimateTokens estimates the number of tokens in a string.
// This is a rough approximation; actual tokenization varies by model.
func EstimateTokens(s string) int {
	if len(s) == 0 {
		return 0
	}
	return len(s) / charsPerToken
}

// TruncateToolOutput truncates tool output to fit within the specified token limit.
// If maxTokens is 0 or the content is within limits, it returns the original content.
// When truncating, it preserves the beginning of the content and adds a truncation marker.
func TruncateToolOutput(content string, maxTokens int) string {
	if maxTokens <= 0 {
		return content
	}

	estimatedTokens := EstimateTokens(content)
	if estimatedTokens <= maxTokens {
		return content
	}

	// Calculate max characters to keep
	maxChars := maxTokens * charsPerToken

	// Ensure we keep at least minTruncationLength characters
	if maxChars < minTruncationLength {
		maxChars = minTruncationLength
	}

	// Truncate and add marker
	truncated := content[:maxChars]

	// Try to break at a word boundary
	if lastSpace := strings.LastIndex(truncated, " "); lastSpace > maxChars/2 {
		truncated = truncated[:lastSpace]
	}

	return truncated + truncationMarker
}

// TruncateToolOutputWithWarning truncates tool output and returns a warning if truncation occurred.
func TruncateToolOutputWithWarning(content string, maxTokens int) (string, string) {
	if maxTokens <= 0 {
		return content, ""
	}

	originalTokens := EstimateTokens(content)
	if originalTokens <= maxTokens {
		return content, ""
	}

	truncated := TruncateToolOutput(content, maxTokens)
	warning := fmt.Sprintf("Tool output truncated from ~%d to ~%d tokens", originalTokens, EstimateTokens(truncated))

	return truncated, warning
}
