package base_test

import (
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestTruncateToolOutput_UnicodeChars tests truncation with unicode characters.
func TestTruncateToolOutput_UnicodeChars(t *testing.T) {
	// Japanese characters (3 bytes each in UTF-8)
	content := strings.Repeat("日本語テスト", 100) // ~600 bytes
	truncated := base.TruncateToolOutput(content, 10) // ~40 chars

	if len(truncated) >= len(content) {
		t.Error("should truncate unicode content")
	}
	if !strings.HasSuffix(truncated, "...") {
		t.Error("should end with truncation marker")
	}
}

// TestTruncateToolOutput_ExactBoundary tests truncation at exact token boundary.
func TestTruncateToolOutput_ExactBoundary(t *testing.T) {
	// Create content that's exactly at the boundary
	// 10 tokens * 4 chars per token = 40 chars
	// But minTruncationLength is 100, so we need more content
	content := strings.Repeat("word ", 100) // 500 chars, ~125 tokens
	truncated := base.TruncateToolOutput(content, 100) // 400 chars

	// Should truncate if over boundary
	if truncated == content {
		t.Errorf("should truncate when over boundary")
	}
}

// TestTruncateToolOutput_VeryLongWord tests truncation with very long word.
func TestTruncateToolOutput_VeryLongWord(t *testing.T) {
	// One very long word (no spaces)
	content := strings.Repeat("a", 1000)
	truncated := base.TruncateToolOutput(content, 10)

	if len(truncated) >= len(content) {
		t.Error("should truncate long word")
	}
	if !strings.HasSuffix(truncated, "...") {
		t.Error("should end with truncation marker")
	}
}

// TestTruncateToolOutput_MultipleSpaces tests truncation with multiple spaces.
func TestTruncateToolOutput_MultipleSpaces(t *testing.T) {
	content := strings.Repeat("word  ", 100) // 600 chars
	truncated := base.TruncateToolOutput(content, 10) // 40 tokens

	if len(truncated) >= len(content) {
		t.Error("should truncate")
	}
}

// TestTruncateToolOutput_Newlines tests truncation with newlines.
func TestTruncateToolOutput_Newlines(t *testing.T) {
	content := strings.Repeat("line with content\n", 100) // ~1800 chars
	truncated := base.TruncateToolOutput(content, 10) // 40 tokens

	if len(truncated) >= len(content) {
		t.Error("should truncate")
	}
}

// TestTruncateToolOutput_Tabs tests truncation with tabs.
func TestTruncateToolOutput_Tabs(t *testing.T) {
	content := strings.Repeat("column\t", 100) // ~700 chars
	truncated := base.TruncateToolOutput(content, 10) // 40 tokens

	if len(truncated) >= len(content) {
		t.Error("should truncate")
	}
}

// TestTruncateToolOutput_SpecialChars tests truncation with special characters.
func TestTruncateToolOutput_SpecialChars(t *testing.T) {
	content := strings.Repeat("!@#$%^&*()_+-=[]{}|;':\",./<>? ", 100) // ~3000 chars
	truncated := base.TruncateToolOutput(content, 10) // 40 tokens

	if len(truncated) >= len(content) {
		t.Error("should truncate special chars")
	}
}

// TestEstimateTokens_Unicode tests token estimation with unicode.
func TestEstimateTokens_Unicode(t *testing.T) {
	tests := []struct {
		name  string
		input string
		min   int
		max   int
	}{
		{
			name:  "ascii",
			input: "hello world",
			min:   2,
			max:   4,
		},
		{
			name:  "japanese",
			input: "日本語テスト",
			min:   1,
			max:   10,
		},
		{
			name:  "emoji",
			input: "😀🎉🚀",
			min:   1,
			max:   10,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tokens := base.EstimateTokens(tt.input)
			if tokens < tt.min || tokens > tt.max {
				t.Errorf("EstimateTokens() = %v, want between %v and %v", tokens, tt.min, tt.max)
			}
		})
	}
}

// TestTruncateToolOutputWithWarning_WithTruncation tests warning generation.
func TestTruncateToolOutputWithWarning_WithTruncation(t *testing.T) {
	content := strings.Repeat("word ", 1000)
	truncated, warning := base.TruncateToolOutputWithWarning(content, 10)

	if !strings.HasSuffix(truncated, "...") {
		t.Error("should truncate")
	}
	if warning == "" {
		t.Error("should generate warning")
	}
	if !strings.Contains(warning, "truncated") {
		t.Error("warning should mention truncation")
	}
}

// TestTruncateToolOutputWithWarning_NoTruncation tests no warning when not truncated.
func TestTruncateToolOutputWithWarning_NoTruncation(t *testing.T) {
	content := "short content"
	truncated, warning := base.TruncateToolOutputWithWarning(content, 100)

	if truncated != content {
		t.Error("should not truncate")
	}
	if warning != "" {
		t.Error("should not generate warning")
	}
}

// TestTruncateToolOutput_MinTruncationLength tests minimum truncation length.
func TestTruncateToolOutput_MinTruncationLength(t *testing.T) {
	// Very small maxTokens
	content := strings.Repeat("a", 1000)
	truncated := base.TruncateToolOutput(content, 1) // 1 token = 4 chars, but min is 100

	if len(truncated) < 100+len("...") {
		t.Errorf("should keep at least 100 chars, got %d", len(truncated)-len("..."))
	}
}
