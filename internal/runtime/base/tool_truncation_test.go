package base_test

import (
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestTruncateToolOutput tests tool output truncation.
func TestTruncateToolOutput(t *testing.T) {
	tests := []struct {
		name      string
		content   string
		maxTokens int
		wantTrunc bool
	}{
		{
			name:      "no limit",
			content:   "short content",
			maxTokens: 0,
			wantTrunc: false,
		},
		{
			name:      "within limit",
			content:   "short content",
			maxTokens: 100,
			wantTrunc: false,
		},
		{
			name:      "exceeds limit",
			content:   strings.Repeat("word ", 1000),
			maxTokens: 10,
			wantTrunc: true,
		},
		{
			name:      "empty content",
			content:   "",
			maxTokens: 100,
			wantTrunc: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := base.TruncateToolOutput(tt.content, tt.maxTokens)
			if tt.wantTrunc {
				if !strings.HasSuffix(result, "...") {
					t.Error("truncated content should end with ...")
				}
				if len(result) >= len(tt.content) {
					t.Error("truncated content should be shorter")
				}
			} else {
				if result != tt.content {
					t.Errorf("content should not be modified")
				}
			}
		})
	}
}

// TestEstimateTokens tests token estimation.
func TestEstimateTokens(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  int
	}{
		{
			name:  "empty",
			input: "",
			want:  0,
		},
		{
			name:  "short",
			input: "hello",
			want:  2, // ~5 chars / 4
		},
		{
			name:  "longer",
			input: "This is a longer sentence with multiple words.",
			want:  12, // ~48 chars / 4
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := base.EstimateTokens(tt.input)
			// Allow some variance in estimation
			if got < tt.want-2 || got > tt.want+2 {
				t.Errorf("EstimateTokens() = %v, want ~%v", got, tt.want)
			}
		})
	}
}

// TestTruncateToolOutput_PreservesContent tests that truncation preserves important content.
func TestTruncateToolOutput_PreservesContent(t *testing.T) {
	original := strings.Repeat("important data ", 100)
	truncated := base.TruncateToolOutput(original, 10)

	// Should contain the beginning of the content
	if !strings.HasPrefix(truncated, "important data") {
		t.Error("truncated content should preserve beginning")
	}

	// Should have truncation marker
	if !strings.Contains(truncated, "...") {
		t.Error("truncated content should contain truncation marker")
	}
}
