package base

import (
	"encoding/json"
	"fmt"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// OutputValidationError represents a validation error for structured output.
type OutputValidationError struct {
	// Content is the content that failed validation.
	Content string
	// Reason describes why validation failed.
	Reason string
}

// Error implements the error interface.
func (e *OutputValidationError) Error() string {
	return fmt.Sprintf("output validation failed: %s", e.Reason)
}

// NewOutputValidationError creates a new OutputValidationError.
func NewOutputValidationError(content, reason string) *OutputValidationError {
	return &OutputValidationError{
		Content: content,
		Reason:  reason,
	}
}

// ValidateStructuredOutput validates LLM output against the requested response format.
// Returns nil if validation passes or no format is specified.
func ValidateStructuredOutput(content string, format *interfaces.ResponseFormat) error {
	if format == nil {
		return nil
	}

	switch format.Type {
	case interfaces.ResponseFormatJSON:
		return ValidateJSONOutput(content)
	case interfaces.ResponseFormatText:
		// Text format doesn't need validation
		return nil
	default:
		return nil
	}
}

// ValidateJSONOutput validates that the content is valid JSON.
func ValidateJSONOutput(content string) error {
	if content == "" {
		return NewOutputValidationError(content, "empty content is not valid JSON")
	}

	var js json.RawMessage
	if err := json.Unmarshal([]byte(content), &js); err != nil {
		return NewOutputValidationError(content, fmt.Sprintf("invalid JSON: %v", err))
	}

	return nil
}

// ValidateJSONOutputWithSchema validates JSON output against a JSON schema.
// This is a basic validation; full schema validation would require a JSON Schema library.
func ValidateJSONOutputWithSchema(content string, schema interfaces.JSONSchema) error {
	// First validate it's valid JSON
	if err := ValidateJSONOutput(content); err != nil {
		return err
	}

	// If no schema, just validate JSON
	if len(schema) == 0 {
		return nil
	}

	// Parse the content
	var parsed map[string]any
	if err := json.Unmarshal([]byte(content), &parsed); err != nil {
		return NewOutputValidationError(content, "content is not a JSON object")
	}

	// Check required fields if specified
	if required, ok := schema["required"]; ok {
		if requiredList, ok := required.([]any); ok {
			for _, field := range requiredList {
				if fieldName, ok := field.(string); ok {
					if _, exists := parsed[fieldName]; !exists {
						return NewOutputValidationError(content, fmt.Sprintf("required field '%s' is missing", fieldName))
					}
				}
			}
		}
	}

	return nil
}
