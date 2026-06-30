package base_test

import (
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// TestValidateStructuredOutput tests structured output validation.
func TestValidateStructuredOutput(t *testing.T) {
	tests := []struct {
		name    string
		content string
		format  *interfaces.ResponseFormat
		wantErr bool
	}{
		{
			name:    "no format",
			content: "any content",
			format:  nil,
			wantErr: false,
		},
		{
			name:    "text format",
			content: "any content",
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatText,
			},
			wantErr: false,
		},
		{
			name:    "json format valid",
			content: `{"key": "value"}`,
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatJSON,
			},
			wantErr: false,
		},
		{
			name:    "json format invalid",
			content: "not json",
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatJSON,
			},
			wantErr: true,
		},
		{
			name:    "json format empty",
			content: "",
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatJSON,
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateStructuredOutput(tt.content, tt.format)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateStructuredOutput() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestValidateJSONOutput tests JSON validation.
func TestValidateJSONOutput(t *testing.T) {
	tests := []struct {
		name    string
		content string
		wantErr bool
	}{
		{
			name:    "valid object",
			content: `{"key": "value"}`,
			wantErr: false,
		},
		{
			name:    "valid array",
			content: `[1, 2, 3]`,
			wantErr: false,
		},
		{
			name:    "invalid json",
			content: `{key: value}`,
			wantErr: true,
		},
		{
			name:    "empty",
			content: "",
			wantErr: true,
		},
		{
			name:    "just text",
			content: "hello",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateJSONOutput(tt.content)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONOutput() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestOutputValidationError tests the error type.
func TestOutputValidationError(t *testing.T) {
	err := base.NewOutputValidationError("not valid json", "invalid character 'n' at start")

	if err.Content != "not valid json" {
		t.Errorf("Content = %v, want %v", err.Content, "not valid json")
	}
	if err.Reason != "invalid character 'n' at start" {
		t.Errorf("Reason = %v, want %v", err.Reason, "invalid character 'n' at start")
	}
	if err.Error() == "" {
		t.Error("Error() should not be empty")
	}
}
