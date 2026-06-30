package base_test

import (
	"errors"
	"fmt"
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestToolExecutionError_NilWrapped tests error with nil wrapped error.
func TestToolExecutionError_NilWrapped(t *testing.T) {
	err := base.NewToolExecutionError("test", "call-1", "error message", false, nil)
	if err.Unwrap() != nil {
		t.Error("Unwrap() should return nil")
	}
}

// TestToolExecutionError_EmptyMessage tests error with empty message.
func TestToolExecutionError_EmptyMessage(t *testing.T) {
	err := base.NewToolExecutionError("test", "call-1", "", false, nil)
	if err.Error() != "tool execution error: test: " {
		t.Errorf("Error() = %q, want %q", err.Error(), "tool execution error: test: ")
	}
}

// TestToolExecutionError_EmptyToolName tests error with empty tool name.
func TestToolExecutionError_EmptyToolName(t *testing.T) {
	err := base.NewToolExecutionError("", "call-1", "error", false, nil)
	if err.Error() != "tool execution error: : error" {
		t.Errorf("Error() = %q, want %q", err.Error(), "tool execution error: : error")
	}
}

// TestToolExecutionError_VeryLongMessage tests error with very long message.
func TestToolExecutionError_VeryLongMessage(t *testing.T) {
	longMsg := strings.Repeat("error ", 1000)
	err := base.NewToolExecutionError("test", "call-1", longMsg, false, nil)
	if !strings.Contains(err.Error(), "error") {
		t.Error("Error() should contain the message")
	}
}

// TestToolExecutionError_UnicodeMessage tests error with unicode message.
func TestToolExecutionError_UnicodeMessage(t *testing.T) {
	unicodeMsg := "错误: テスト 에러"
	err := base.NewToolExecutionError("test", "call-1", unicodeMsg, false, nil)
	if !strings.Contains(err.Error(), unicodeMsg) {
		t.Error("Error() should contain unicode message")
	}
}

// TestClassifyToolError_NilError tests classification with nil error.
func TestClassifyToolError_NilError(t *testing.T) {
	err := base.ClassifyToolError("test", "call-1", nil)
	if err != nil {
		t.Error("ClassifyToolError with nil should return nil")
	}
}

// TestClassifyToolError_EmptyMessage tests classification with empty message.
func TestClassifyToolError_EmptyMessage(t *testing.T) {
	err := base.ClassifyToolError("test", "call-1", errors.New(""))
	if err.IsFatal {
		t.Error("empty message should not be fatal")
	}
}

// TestClassifyToolError_FatalPatterns tests various fatal error patterns.
func TestClassifyToolError_FatalPatterns(t *testing.T) {
	fatalErrors := []string{
		"connection refused",
		"connection reset by peer",
		"dial tcp: i/o timeout",
		"network is unreachable",
		"no route to host",
		"broken pipe",
		"unexpected EOF",
		"context deadline exceeded",
		"context canceled",
		"service unavailable",
		"bad gateway",
		"gateway timeout",
		"HTTP 502",
		"HTTP 503",
		"HTTP 504",
	}

	for _, msg := range fatalErrors {
		t.Run(msg, func(t *testing.T) {
			err := base.ClassifyToolError("test", "call-1", errors.New(msg))
			if !err.IsFatal {
				t.Errorf("expected %q to be fatal", msg)
			}
		})
	}
}

// TestClassifyToolError_NonFatalPatterns tests various non-fatal error patterns.
func TestClassifyToolError_NonFatalPatterns(t *testing.T) {
	nonFatalErrors := []string{
		"invalid parameter",
		"validation failed",
		"not found",
		"permission denied",
		"unauthorized",
		"bad request",
		"HTTP 400",
		"HTTP 404",
	}

	for _, msg := range nonFatalErrors {
		t.Run(msg, func(t *testing.T) {
			err := base.ClassifyToolError("test", "call-1", errors.New(msg))
			if err.IsFatal {
				t.Errorf("expected %q to not be fatal", msg)
			}
		})
	}
}

// TestWrapToolError_NilError tests wrapping nil error.
func TestWrapToolError_NilError(t *testing.T) {
	err := base.WrapToolError("test", "call-1", nil)
	if err != nil {
		t.Error("WrapToolError with nil should return nil")
	}
}

// TestWrapToolError_AlreadyWrapped tests wrapping an already wrapped error.
func TestWrapToolError_AlreadyWrapped(t *testing.T) {
	original := base.NewToolExecutionError("test", "call-1", "original", true, nil)
	wrapped := base.WrapToolError("other", "call-2", original)
	if wrapped != original {
		t.Error("WrapToolError should return same error if already wrapped")
	}
}

// TestWrapToolError_RegularError tests wrapping a regular error.
func TestWrapToolError_RegularError(t *testing.T) {
	original := errors.New("regular error")
	wrapped := base.WrapToolError("test", "call-1", original)
	if wrapped == nil {
		t.Error("WrapToolError should not return nil")
	}
	// Wrapped error includes tool name prefix
	if !strings.Contains(wrapped.Error(), "regular error") {
		t.Errorf("wrapped error should contain original message, got %q", wrapped.Error())
	}
}

// TestToolExecutionError_ErrorChain tests error chain unwrapping.
func TestToolExecutionError_ErrorChain(t *testing.T) {
	inner := errors.New("inner error")
	middle := fmt.Errorf("middle: %w", inner)
	outer := base.NewToolExecutionError("test", "call-1", "outer", false, middle)

	if !errors.Is(outer, inner) {
		t.Error("should be able to unwrap to inner error")
	}
	if !errors.Is(outer, middle) {
		t.Error("should be able to unwrap to middle error")
	}
}

// TestClassifyToolError_CaseInsensitive tests case-insensitive pattern matching.
func TestClassifyToolError_CaseInsensitive(t *testing.T) {
	tests := []struct {
		name      string
		message   string
		wantFatal bool
	}{
		{
			name:      "uppercase CONNECTION REFUSED",
			message:   "CONNECTION REFUSED",
			wantFatal: true,
		},
		{
			name:      "mixed case Connection Refused",
			message:   "Connection Refused",
			wantFatal: true,
		},
		{
			name:      "uppercase TIMEOUT",
			message:   "CONTEXT DEADLINE EXCEEDED",
			wantFatal: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ClassifyToolError("test", "call-1", errors.New(tt.message))
			if err.IsFatal != tt.wantFatal {
				t.Errorf("IsFatal = %v, want %v", err.IsFatal, tt.wantFatal)
			}
		})
	}
}
