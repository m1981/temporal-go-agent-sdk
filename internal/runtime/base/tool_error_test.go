package base_test

import (
	"errors"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestToolExecutionError tests the ToolExecutionError type.
func TestToolExecutionError(t *testing.T) {
	tests := []struct {
		name      string
		err       *base.ToolExecutionError
		wantMsg   string
		wantFatal bool
	}{
		{
			name: "infrastructure error",
			err: &base.ToolExecutionError{
				ToolName:  "search",
				CallID:    "call-123",
				Message:   "connection timeout",
				IsFatal:   true,
				Wrapped:   errors.New("dial tcp: i/o timeout"),
			},
			wantMsg:   "tool execution error: search: connection timeout",
			wantFatal: true,
		},
		{
			name: "business error",
			err: &base.ToolExecutionError{
				ToolName:  "calculator",
				CallID:    "call-456",
				Message:   "division by zero",
				IsFatal:   false,
			},
			wantMsg:   "tool execution error: calculator: division by zero",
			wantFatal: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.err.Error(); got != tt.wantMsg {
				t.Errorf("Error() = %v, want %v", got, tt.wantMsg)
			}
			if got := tt.err.IsFatal; got != tt.wantFatal {
				t.Errorf("IsFatal = %v, want %v", got, tt.wantFatal)
			}
		})
	}
}

// TestToolExecutionError_Unwrap tests error unwrapping.
func TestToolExecutionError_Unwrap(t *testing.T) {
	inner := errors.New("inner error")
	err := &base.ToolExecutionError{
		ToolName: "test",
		Message:  "outer error",
		Wrapped:  inner,
	}

	if !errors.Is(err, inner) {
		t.Error("errors.Is should match inner error")
	}
}

// TestToolExecutionError_IsFatalClassification tests fatal vs non-fatal classification.
func TestToolExecutionError_IsFatalClassification(t *testing.T) {
	tests := []struct {
		name    string
		err     *base.ToolExecutionError
		isFatal bool
	}{
		{
			name: "connection error is fatal",
			err: &base.ToolExecutionError{
				ToolName: "api",
				Message:  "connection refused",
				IsFatal:  true,
			},
			isFatal: true,
		},
		{
			name: "validation error is not fatal",
			err: &base.ToolExecutionError{
				ToolName: "validator",
				Message:  "invalid input format",
				IsFatal:  false,
			},
			isFatal: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.err.IsFatal; got != tt.isFatal {
				t.Errorf("IsFatal = %v, want %v", got, tt.isFatal)
			}
		})
	}
}

// TestNewToolExecutionError tests error construction.
func TestNewToolExecutionError(t *testing.T) {
	err := base.NewToolExecutionError("test-tool", "call-1", "something went wrong", true, nil)
	if err.ToolName != "test-tool" {
		t.Errorf("ToolName = %v, want %v", err.ToolName, "test-tool")
	}
	if err.CallID != "call-1" {
		t.Errorf("CallID = %v, want %v", err.CallID, "call-1")
	}
	if err.Message != "something went wrong" {
		t.Errorf("Message = %v, want %v", err.Message, "something went wrong")
	}
	if !err.IsFatal {
		t.Error("IsFatal should be true")
	}
}

// TestClassifyToolError tests automatic error classification.
func TestClassifyToolError(t *testing.T) {
	tests := []struct {
		name      string
		inputErr  error
		wantFatal bool
	}{
		{
			name:      "nil error",
			inputErr:  nil,
			wantFatal: false,
		},
		{
			name:      "timeout is fatal",
			inputErr:  errors.New("context deadline exceeded"),
			wantFatal: true,
		},
		{
			name:      "connection refused is fatal",
			inputErr:  errors.New("dial tcp: connection refused"),
			wantFatal: true,
		},
		{
			name:      "validation is not fatal",
			inputErr:  errors.New("invalid parameter: name is required"),
			wantFatal: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.inputErr == nil {
				return
			}
			classified := base.ClassifyToolError("test", "call-1", tt.inputErr)
			if classified.IsFatal != tt.wantFatal {
				t.Errorf("ClassifyToolError().IsFatal = %v, want %v", classified.IsFatal, tt.wantFatal)
			}
		})
	}
}
