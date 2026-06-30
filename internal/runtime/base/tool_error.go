package base

import (
	"fmt"
	"strings"
)

// ToolExecutionError represents an error that occurred during tool execution.
// It distinguishes between infrastructure failures (fatal) and business errors (non-fatal).
type ToolExecutionError struct {
	// ToolName is the name of the tool that failed.
	ToolName string
	// CallID is the tool call ID from the LLM.
	CallID string
	// Message is a human-readable error description.
	Message string
	// IsFatal indicates whether this is an infrastructure failure (true) or business error (false).
	// Fatal errors: connection timeouts, network failures, service unavailable.
	// Non-fatal errors: validation failures, business rule violations, invalid input.
	IsFatal bool
	// Wrapped is the underlying error, if any.
	Wrapped error
}

// Error implements the error interface.
func (e *ToolExecutionError) Error() string {
	return fmt.Sprintf("tool execution error: %s: %s", e.ToolName, e.Message)
}

// Unwrap implements the errors.Unwrap interface.
func (e *ToolExecutionError) Unwrap() error {
	return e.Wrapped
}

// NewToolExecutionError creates a new ToolExecutionError.
func NewToolExecutionError(toolName, callID, message string, isFatal bool, wrapped error) *ToolExecutionError {
	return &ToolExecutionError{
		ToolName: toolName,
		CallID:   callID,
		Message:  message,
		IsFatal:  isFatal,
		Wrapped:  wrapped,
	}
}

// ClassifyToolError creates a ToolExecutionError with automatic classification.
// It analyzes the error message to determine if it's fatal (infrastructure) or non-fatal (business).
func ClassifyToolError(toolName, callID string, err error) *ToolExecutionError {
	if err == nil {
		return nil
	}

	msg := err.Error()
	isFatal := isInfrastructureError(msg)

	return &ToolExecutionError{
		ToolName: toolName,
		CallID:   callID,
		Message:  msg,
		IsFatal:  isFatal,
		Wrapped:  err,
	}
}

// WrapToolError wraps an error as a ToolExecutionError with automatic classification.
// If err is already a *ToolExecutionError, it returns it as-is.
// Returns nil if err is nil.
func WrapToolError(toolName, callID string, err error) error {
	if err == nil {
		return nil
	}
	if te, ok := err.(*ToolExecutionError); ok {
		return te
	}
	return ClassifyToolError(toolName, callID, err)
}

// isInfrastructureError determines if an error message indicates an infrastructure failure.
func isInfrastructureError(msg string) bool {
	msg = strings.ToLower(msg)

	// Network and connection errors
	fatalPatterns := []string{
		"connection refused",
		"connection reset",
		"connection timeout",
		"dial tcp",
		"i/o timeout",
		"network unreachable",
		"unreachable",
		"no route to host",
		"broken pipe",
		"eof",
		"context deadline exceeded",
		"context canceled",
		"service unavailable",
		"bad gateway",
		"gateway timeout",
		"502",
		"503",
		"504",
	}

	for _, pattern := range fatalPatterns {
		if strings.Contains(msg, pattern) {
			return true
		}
	}

	return false
}
