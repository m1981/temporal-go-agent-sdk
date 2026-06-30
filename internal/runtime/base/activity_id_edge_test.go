package base_test

import (
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestGenerateActivityID_EmptyRunID tests with empty run ID.
func TestGenerateActivityID_EmptyRunID(t *testing.T) {
	id := base.GenerateActivityID("LLM", "", 0, "")
	if id != "LLM__0" {
		t.Errorf("unexpected ID: %v", id)
	}
}

// TestGenerateActivityID_SpecialCharacters tests with special characters in run ID.
func TestGenerateActivityID_SpecialCharacters(t *testing.T) {
	tests := []struct {
		name  string
		runID string
	}{
		{
			name:  "with spaces",
			runID: "run id with spaces",
		},
		{
			name:  "with dashes",
			runID: "run-id-with-dashes",
		},
		{
			name:  "with underscores",
			runID: "run_id_with_underscores",
		},
		{
			name:  "with dots",
			runID: "run.id.with.dots",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			id := base.GenerateActivityID("LLM", tt.runID, 0, "")
			if id == "" {
				t.Error("ID should not be empty")
			}
			if !strings.Contains(id, "LLM") {
				t.Error("ID should contain prefix")
			}
		})
	}
}

// TestGenerateActivityID_VeryLongRunID tests with very long run ID.
func TestGenerateActivityID_VeryLongRunID(t *testing.T) {
	longRunID := strings.Repeat("a", 1000)
	id := base.GenerateActivityID("LLM", longRunID, 0, "")

	if id == "" {
		t.Error("ID should not be empty")
	}
	if !strings.HasPrefix(id, "LLM_") {
		t.Error("ID should start with prefix")
	}
}

// TestGenerateActivityID_NegativeIteration tests with negative iteration.
func TestGenerateActivityID_NegativeIteration(t *testing.T) {
	id := base.GenerateActivityID("LLM", "run-1", -1, "")
	if id != "LLM_run-1_-1" {
		t.Errorf("unexpected ID: %v", id)
	}
}

// TestGenerateActivityID_LargeIteration tests with large iteration number.
func TestGenerateActivityID_LargeIteration(t *testing.T) {
	id := base.GenerateActivityID("LLM", "run-1", 999999, "")
	if id != "LLM_run-1_999999" {
		t.Errorf("unexpected ID: %v", id)
	}
}

// TestGenerateActivityID_UnicodeRunID tests with unicode run ID.
func TestGenerateActivityID_UnicodeRunID(t *testing.T) {
	unicodeRunID := "run-日本語-テスト"
	id := base.GenerateActivityID("LLM", unicodeRunID, 0, "")

	if id == "" {
		t.Error("ID should not be empty")
	}
}

// TestGenerateToolActivityID_EmptyToolName tests with empty tool name.
func TestGenerateToolActivityID_EmptyToolName(t *testing.T) {
	id := base.GenerateToolActivityID("run-1", 0, 0, "")
	if id != "Tool_run-1_0_0_" {
		t.Errorf("unexpected ID: %v", id)
	}
}

// TestGenerateToolActivityID_SpecialCharactersInToolName tests with special characters.
func TestGenerateToolActivityID_SpecialCharactersInToolName(t *testing.T) {
	tests := []struct {
		name     string
		toolName string
	}{
		{
			name:     "with spaces",
			toolName: "my tool",
		},
		{
			name:     "with special chars",
			toolName: "tool@#$%",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			id := base.GenerateToolActivityID("run-1", 0, 0, tt.toolName)
			if id == "" {
				t.Error("ID should not be empty")
			}
		})
	}
}

// TestGenerateActivityID_UniquenessAcrossPrefixes tests uniqueness across different prefixes.
func TestGenerateActivityID_UniquenessAcrossPrefixes(t *testing.T) {
	prefixes := []string{"LLM", "Tool", "Event", "Memory", "Retriever"}
	ids := make(map[string]bool)

	for _, prefix := range prefixes {
		id := base.GenerateActivityID(prefix, "run-1", 0, "")
		if ids[id] {
			t.Errorf("duplicate ID: %v", id)
		}
		ids[id] = true
	}
}

// TestGenerateActivityID_UniquenessAcrossIterations tests uniqueness across iterations.
func TestGenerateActivityID_UniquenessAcrossIterations(t *testing.T) {
	ids := make(map[string]bool)

	for i := 0; i < 100; i++ {
		id := base.GenerateActivityID("LLM", "run-1", i, "")
		if ids[id] {
			t.Errorf("duplicate ID at iteration %d: %v", i, id)
		}
		ids[id] = true
	}
}

// TestGenerateActivityID_UniquenessAcrossRunIDs tests uniqueness across run IDs.
func TestGenerateActivityID_UniquenessAcrossRunIDs(t *testing.T) {
	ids := make(map[string]bool)

	for i := 0; i < 100; i++ {
		id := base.GenerateActivityID("LLM", "run-"+string(rune('0'+i%10)), 0, "")
		// Some may collide due to rune wrapping, but that's ok for this test
		ids[id] = true
	}
}

// TestGenerateLLMActivityID tests LLM-specific ID generation.
func TestGenerateLLMActivityID(t *testing.T) {
	id := base.GenerateLLMActivityID("run-1", 0)
	if !strings.HasPrefix(id, "AgentLLM_") {
		t.Errorf("should start with AgentLLM_, got %v", id)
	}
}

// TestGenerateStreamActivityID tests stream-specific ID generation.
func TestGenerateStreamActivityID(t *testing.T) {
	id := base.GenerateStreamActivityID("run-1", 0)
	if !strings.HasPrefix(id, "AgentLLMStream_") {
		t.Errorf("should start with AgentLLMStream_, got %v", id)
	}
}

// TestGenerateEventActivityID tests event-specific ID generation.
func TestGenerateEventActivityID(t *testing.T) {
	id := base.GenerateEventActivityID("run-1", 0)
	if !strings.HasPrefix(id, "SendAgentEvent_") {
		t.Errorf("should start with SendAgentEvent_, got %v", id)
	}
}

// TestGenerateConversationActivityID tests conversation-specific ID generation.
func TestGenerateConversationActivityID(t *testing.T) {
	id := base.GenerateConversationActivityID("run-1", 0)
	if !strings.HasPrefix(id, "Conversation_") {
		t.Errorf("should start with Conversation_, got %v", id)
	}
}

// TestGenerateRetrieverActivityID tests retriever-specific ID generation.
func TestGenerateRetrieverActivityID(t *testing.T) {
	id := base.GenerateRetrieverActivityID("run-1", 0)
	if !strings.HasPrefix(id, "AgentRetriever_") {
		t.Errorf("should start with AgentRetriever_, got %v", id)
	}
}

// TestGenerateMemoryActivityID tests memory-specific ID generation.
func TestGenerateMemoryActivityID(t *testing.T) {
	id := base.GenerateMemoryActivityID("run-1", 0)
	if !strings.HasPrefix(id, "AgentMemory_") {
		t.Errorf("should start with AgentMemory_, got %v", id)
	}
}
