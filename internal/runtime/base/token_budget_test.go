package base_test

import (
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// TestTokenBudget_Tracking tests token budget tracking.
func TestTokenBudget_Tracking(t *testing.T) {
	tests := []struct {
		name           string
		maxTokens      int64
		usage          *base.TokenUsage
		wantExceeded   bool
		wantRemaining  int64
	}{
		{
			name:          "no limit",
			maxTokens:     0,
			usage:         &base.TokenUsage{TotalTokens: 1000},
			wantExceeded:  false,
			wantRemaining: 0,
		},
		{
			name:          "within budget",
			maxTokens:     1000,
			usage:         &base.TokenUsage{TotalTokens: 500},
			wantExceeded:  false,
			wantRemaining: 500,
		},
		{
			name:          "at budget",
			maxTokens:     1000,
			usage:         &base.TokenUsage{TotalTokens: 1000},
			wantExceeded:  false,
			wantRemaining: 0,
		},
		{
			name:          "exceeded budget",
			maxTokens:     1000,
			usage:         &base.TokenUsage{TotalTokens: 1500},
			wantExceeded:  true,
			wantRemaining: 0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			budget := base.NewTokenBudget(tt.maxTokens)
			budget.AddUsage(tt.usage)

			if got := budget.IsExceeded(); got != tt.wantExceeded {
				t.Errorf("IsExceeded() = %v, want %v", got, tt.wantExceeded)
			}
			if got := budget.Remaining(); got != tt.wantRemaining {
				t.Errorf("Remaining() = %v, want %v", got, tt.wantRemaining)
			}
		})
	}
}

// TestTokenBudget_MultipleUpdates tests cumulative token tracking.
func TestTokenBudget_MultipleUpdates(t *testing.T) {
	budget := base.NewTokenBudget(1000)

	// First update
	budget.AddUsage(&base.TokenUsage{TotalTokens: 300})
	if budget.IsExceeded() {
		t.Error("budget should not be exceeded after first update")
	}
	if budget.Remaining() != 700 {
		t.Errorf("Remaining() = %v, want %v", budget.Remaining(), 700)
	}

	// Second update
	budget.AddUsage(&base.TokenUsage{TotalTokens: 400})
	if budget.IsExceeded() {
		t.Error("budget should not be exceeded after second update")
	}
	if budget.Remaining() != 300 {
		t.Errorf("Remaining() = %v, want %v", budget.Remaining(), 300)
	}

	// Third update - exceed budget
	budget.AddUsage(&base.TokenUsage{TotalTokens: 500})
	if !budget.IsExceeded() {
		t.Error("budget should be exceeded after third update")
	}
	if budget.Remaining() != 0 {
		t.Errorf("Remaining() = %v, want %v", budget.Remaining(), 0)
	}
}

// TestTokenBudget_ZeroUsage tests zero usage handling.
func TestTokenBudget_ZeroUsage(t *testing.T) {
	budget := base.NewTokenBudget(1000)
	if budget.IsExceeded() {
		t.Error("budget should not be exceeded with zero usage")
	}
	if budget.Remaining() != 1000 {
		t.Errorf("Remaining() = %v, want %v", budget.Remaining(), 1000)
	}
}

// TestTokenBudget_NilUsage tests nil usage handling.
func TestTokenBudget_NilUsage(t *testing.T) {
	budget := base.NewTokenBudget(1000)
	budget.AddUsage(nil) // Should not panic
	if budget.IsExceeded() {
		t.Error("budget should not be exceeded with nil usage")
	}
}

// TestTokenUsage_ConvertFromLLMUsage tests conversion from LLMUsage.
func TestTokenUsage_ConvertFromLLMUsage(t *testing.T) {
	tests := []struct {
		name      string
		input     *interfaces.LLMUsage
		wantTotal int64
	}{
		{
			name:      "nil usage",
			input:     nil,
			wantTotal: 0,
		},
		{
			name: "with total",
			input: &interfaces.LLMUsage{
				TotalTokens: 500,
			},
			wantTotal: 500,
		},
		{
			name: "with prompt and completion",
			input: &interfaces.LLMUsage{
				PromptTokens:     200,
				CompletionTokens: 300,
				TotalTokens:      500,
			},
			wantTotal: 500,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			usage := base.ConvertFromLLMUsage(tt.input)
			if usage.TotalTokens != tt.wantTotal {
				t.Errorf("TotalTokens = %v, want %v", usage.TotalTokens, tt.wantTotal)
			}
		})
	}
}

// TestTokenBudget_String tests string representation.
func TestTokenBudget_String(t *testing.T) {
	budget := base.NewTokenBudget(1000)
	budget.AddUsage(&base.TokenUsage{TotalTokens: 300})

	str := budget.String()
	if str == "" {
		t.Error("String() should not be empty")
	}
}
