package base_test

import (
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// TestValidateJSONOutput_DeeplyNested tests deeply nested JSON.
func TestValidateJSONOutput_DeeplyNested(t *testing.T) {
	// Build deeply nested JSON
	json := `{"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": "value"}}}}}}}}}}`
	err := base.ValidateJSONOutput(json)
	if err != nil {
		t.Errorf("deeply nested JSON should be valid: %v", err)
	}
}

// TestValidateJSONOutput_LargeJSON tests large JSON.
func TestValidateJSONOutput_LargeJSON(t *testing.T) {
	// Build large JSON array
	items := make([]string, 1000)
	for i := range items {
		items[i] = `{"id": ` + string(rune('0'+i%10)) + `}`
	}
	json := "[" + strings.Join(items, ",") + "]"

	err := base.ValidateJSONOutput(json)
	if err != nil {
		t.Errorf("large JSON should be valid: %v", err)
	}
}

// TestValidateJSONOutput_NullValues tests JSON with null values.
func TestValidateJSONOutput_NullValues(t *testing.T) {
	tests := []struct {
		name    string
		json    string
		wantErr bool
	}{
		{
			name:    "null value",
			json:    `{"key": null}`,
			wantErr: false,
		},
		{
			name:    "null array",
			json:    `[null, null, null]`,
			wantErr: false,
		},
		{
			name:    "null object",
			json:    `null`,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateJSONOutput(tt.json)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONOutput() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestValidateJSONOutput_EscapedChars tests JSON with escaped characters.
func TestValidateJSONOutput_EscapedChars(t *testing.T) {
	tests := []struct {
		name    string
		json    string
		wantErr bool
	}{
		{
			name:    "escaped quotes",
			json:    `{"key": "value with \"quotes\""}`,
			wantErr: false,
		},
		{
			name:    "escaped newlines",
			json:    `{"key": "line1\nline2"}`,
			wantErr: false,
		},
		{
			name:    "escaped unicode",
			json:    `{"key": "\u0048\u0065\u006c\u006c\u006f"}`,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateJSONOutput(tt.json)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONOutput() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestValidateJSONOutput_MalformedJSON tests various malformed JSON.
func TestValidateJSONOutput_MalformedJSON(t *testing.T) {
	tests := []struct {
		name string
		json string
	}{
		{
			name: "missing closing brace",
			json: `{"key": "value"`,
		},
		{
			name: "missing opening brace",
			json: `"key": "value"}`,
		},
		{
			name: "trailing comma",
			json: `{"key": "value",}`,
		},
		{
			name: "single quotes",
			json: `{'key': 'value'}`,
		},
		{
			name: "unquoted key",
			json: `{key: "value"}`,
		},
		{
			name: "extra comma",
			json: `{"a": 1,, "b": 2}`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateJSONOutput(tt.json)
			if err == nil {
				t.Error("malformed JSON should return error")
			}
		})
	}
}

// TestValidateStructuredOutput_ResponseFormats tests different response formats.
func TestValidateStructuredOutput_ResponseFormats(t *testing.T) {
	tests := []struct {
		name    string
		content string
		format  *interfaces.ResponseFormat
		wantErr bool
	}{
		{
			name:    "nil format",
			content: "any content",
			format:  nil,
			wantErr: false,
		},
		{
			name:    "text format with any content",
			content: "not json at all",
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatText,
			},
			wantErr: false,
		},
		{
			name:    "json format with valid json",
			content: `{"valid": true}`,
			format: &interfaces.ResponseFormat{
				Type: interfaces.ResponseFormatJSON,
			},
			wantErr: false,
		},
		{
			name:    "json format with invalid json",
			content: "not json",
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

// TestValidateJSONOutputWithSchema_RequiredFields tests schema validation with required fields.
func TestValidateJSONOutputWithSchema_RequiredFields(t *testing.T) {
	tests := []struct {
		name    string
		content string
		schema  interfaces.JSONSchema
		wantErr bool
	}{
		{
			name:    "all required fields present",
			content: `{"name": "test", "age": 25}`,
			schema: interfaces.JSONSchema{
				"required": []any{"name", "age"},
			},
			wantErr: false,
		},
		{
			name:    "missing required field",
			content: `{"name": "test"}`,
			schema: interfaces.JSONSchema{
				"required": []any{"name", "age"},
			},
			wantErr: true,
		},
		{
			name:    "no schema",
			content: `{"any": "value"}`,
			schema:  nil,
			wantErr: false,
		},
		{
			name:    "empty schema",
			content: `{"any": "value"}`,
			schema:  interfaces.JSONSchema{},
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.ValidateJSONOutputWithSchema(tt.content, tt.schema)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateJSONOutputWithSchema() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

// TestOutputValidationError_ErrorMessages tests error message formatting.
func TestOutputValidationError_ErrorMessages(t *testing.T) {
	tests := []struct {
		name    string
		content string
		reason  string
		want    string
	}{
		{
			name:    "empty content",
			content: "",
			reason:  "invalid JSON",
			want:    "output validation failed: invalid JSON",
		},
		{
			name:    "with content",
			content: "not json",
			reason:  "unexpected token",
			want:    "output validation failed: unexpected token",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := base.NewOutputValidationError(tt.content, tt.reason)
			if err.Error() != tt.want {
				t.Errorf("Error() = %q, want %q", err.Error(), tt.want)
			}
		})
	}
}
