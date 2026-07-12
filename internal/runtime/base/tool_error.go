package base

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

// Model-facing static tool-failure texts (PR-02: errors are instructions).
// These fixed corrective sentences are the ONLY strings the model may see for a failed
// tool call. The raw err.Error() rides harness-only channels (logs, telemetry, spans)
// and must never be interpolated into message content (AP-05).
const (
	// MsgToolFailed is the generic/business-error class.
	MsgToolFailed = "The tool failed to execute; check the arguments and try again."
	// MsgToolUnavailable is the infrastructure-error class (network, upstream outage).
	MsgToolUnavailable = "The tool could not be executed because of a temporary system problem; try again, or continue without this tool."
	// MsgToolTimedOut is the deadline class.
	MsgToolTimedOut = "The tool did not finish within its execution time limit; try again, narrowing the request if possible."
	// MsgToolPanicked is the internal-crash class. Panic values and stack traces are
	// harness-only (never forwarded to the model).
	MsgToolPanicked = "The tool encountered an internal error and could not complete; do not retry with the same arguments."
)

// ErrToolPanicked is the sentinel wrapped when a recovered tool panic is converted to an
// error. The panic value and stack trace are intentionally NOT carried on this error.
var ErrToolPanicked = errors.New("tool execution panicked")

// ModelFacingToolErrorText maps a tool-execution error to the static corrective sentence
// for its class. It classifies by sentinel first and falls back to message patterns so it
// also works for errors that crossed an activity boundary as strings.
func ModelFacingToolErrorText(err error) string {
	if err == nil {
		return ""
	}
	msg := strings.ToLower(err.Error())
	switch {
	case errors.Is(err, ErrToolPanicked) || strings.Contains(msg, ErrToolPanicked.Error()):
		return MsgToolPanicked
	case errors.Is(err, context.DeadlineExceeded) || strings.Contains(msg, "context deadline exceeded"):
		return MsgToolTimedOut
	case isInfrastructureError(msg):
		return MsgToolUnavailable
	case strings.Contains(msg, "timeout") || strings.Contains(msg, "timed out"):
		return MsgToolTimedOut
	default:
		return MsgToolFailed
	}
}

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
