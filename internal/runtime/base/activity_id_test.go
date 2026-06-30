package base_test

import (
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestGenerateActivityID tests deterministic activity ID generation.
func TestGenerateActivityID(t *testing.T) {
	tests := []struct {
		name      string
		prefix    string
		runID     string
		iteration int
		extra     string
		want      string
	}{
		{
			name:      "basic",
			prefix:    "AgentLLM",
			runID:     "run-123",
			iteration: 0,
			want:      "AgentLLM_run-123_0",
		},
		{
			name:      "with extra",
			prefix:    "Tool",
			runID:     "run-456",
			iteration: 2,
			extra:     "search",
			want:      "Tool_run-456_2_search",
		},
		{
			name:      "empty extra",
			prefix:    "LLM",
			runID:     "run-789",
			iteration: 1,
			extra:     "",
			want:      "LLM_run-789_1",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := base.GenerateActivityID(tt.prefix, tt.runID, tt.iteration, tt.extra)
			if got != tt.want {
				t.Errorf("GenerateActivityID() = %v, want %v", got, tt.want)
			}
		})
	}
}

// TestGenerateActivityID_Uniqueness tests that different inputs produce different IDs.
func TestGenerateActivityID_Uniqueness(t *testing.T) {
	id1 := base.GenerateActivityID("LLM", "run-1", 0, "")
	id2 := base.GenerateActivityID("LLM", "run-2", 0, "")
	id3 := base.GenerateActivityID("LLM", "run-1", 1, "")
	id4 := base.GenerateActivityID("Tool", "run-1", 0, "")

	if id1 == id2 {
		t.Errorf("IDs should differ for different runIDs: %v == %v", id1, id2)
	}
	if id1 == id3 {
		t.Errorf("IDs should differ for different iterations: %v == %v", id1, id3)
	}
	if id1 == id4 {
		t.Errorf("IDs should differ for different prefixes: %v == %v", id1, id4)
	}
}

// TestGenerateToolActivityID tests tool-specific activity ID generation.
func TestGenerateToolActivityID(t *testing.T) {
	tests := []struct {
		name       string
		runID      string
		iteration  int
		toolIndex  int
		toolName   string
		wantPrefix string
	}{
		{
			name:       "first tool",
			runID:      "run-123",
			iteration:  0,
			toolIndex:  0,
			toolName:   "search",
			wantPrefix: "Tool_run-123_0_0_search",
		},
		{
			name:       "second tool",
			runID:      "run-123",
			iteration:  0,
			toolIndex:  1,
			toolName:   "calculator",
			wantPrefix: "Tool_run-123_0_1_calculator",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := base.GenerateToolActivityID(tt.runID, tt.iteration, tt.toolIndex, tt.toolName)
			if got != tt.wantPrefix {
				t.Errorf("GenerateToolActivityID() = %v, want %v", got, tt.wantPrefix)
			}
		})
	}
}

// TestGenerateActivityID_ShortRunID tests that short run IDs are handled.
func TestGenerateActivityID_ShortRunID(t *testing.T) {
	id := base.GenerateActivityID("LLM", "r", 0, "")
	if id != "LLM_r_0" {
		t.Errorf("unexpected ID: %v", id)
	}
}
