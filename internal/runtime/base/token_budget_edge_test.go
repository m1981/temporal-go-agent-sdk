package base_test

import (
	"sync"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// TestTokenBudget_ConcurrentAccess tests thread safety under concurrent load.
func TestTokenBudget_ConcurrentAccess(t *testing.T) {
	budget := base.NewTokenBudget(10000)
	var wg sync.WaitGroup

	// Simulate 100 concurrent LLM calls
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			budget.AddUsage(&base.TokenUsage{TotalTokens: 100})
		}()
	}

	wg.Wait()

	if budget.CurrentUsage().TotalTokens != 10000 {
		t.Errorf("TotalTokens = %v, want 10000", budget.CurrentUsage().TotalTokens)
	}
	// Budget is exceeded when TotalTokens > maxTokens, not at exactly maxTokens
	if budget.IsExceeded() {
		t.Error("budget should not be exceeded at exactly 10000")
	}
	if budget.Remaining() != 0 {
		t.Errorf("Remaining() = %v, want 0", budget.Remaining())
	}
}

// TestTokenBudget_ConcurrentReadWrite tests concurrent reads and writes.
func TestTokenBudget_ConcurrentReadWrite(t *testing.T) {
	budget := base.NewTokenBudget(1000)
	var wg sync.WaitGroup
	done := make(chan struct{})

	// Writer goroutine
	wg.Add(1)
	go func() {
		defer wg.Done()
		for i := 0; i < 100; i++ {
			budget.AddUsage(&base.TokenUsage{TotalTokens: 10})
		}
		close(done)
	}()

	// Reader goroutines
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-done:
					return
				default:
					_ = budget.IsExceeded()
					_ = budget.Remaining()
					_ = budget.CurrentUsage()
				}
			}
		}()
	}

	wg.Wait()
}

// TestTokenBudget_NegativeMaxTokens tests behavior with negative limit.
func TestTokenBudget_NegativeMaxTokens(t *testing.T) {
	budget := base.NewTokenBudget(-100)

	// Negative limit should behave like 0 (no limit)
	budget.AddUsage(&base.TokenUsage{TotalTokens: 1000})
	if budget.IsExceeded() {
		t.Error("negative maxTokens should mean no limit")
	}
	if budget.Remaining() != 0 {
		t.Errorf("Remaining() = %v, want 0 (no limit)", budget.Remaining())
	}
}

// TestTokenBudget_VeryLargeTokens tests behavior with very large token counts.
func TestTokenBudget_VeryLargeTokens(t *testing.T) {
	budget := base.NewTokenBudget(1000000) // 1M tokens

	budget.AddUsage(&base.TokenUsage{TotalTokens: 500000})
	if budget.IsExceeded() {
		t.Error("should not be exceeded with half max")
	}

	// Add enough to exceed
	budget.AddUsage(&base.TokenUsage{TotalTokens: 600000})
	if !budget.IsExceeded() {
		t.Error("should be exceeded when total exceeds max")
	}
}

// TestTokenBudget_ZeroMaxTokens tests behavior with zero limit.
func TestTokenBudget_ZeroMaxTokens(t *testing.T) {
	budget := base.NewTokenBudget(0)

	// Zero means no limit
	budget.AddUsage(&base.TokenUsage{TotalTokens: 1000000})
	if budget.IsExceeded() {
		t.Error("zero maxTokens should mean no limit")
	}
	if budget.Remaining() != 0 {
		t.Errorf("Remaining() = %v, want 0 (no limit)", budget.Remaining())
	}
}

// TestTokenBudget_RapidUpdates tests rapid sequential updates.
func TestTokenBudget_RapidUpdates(t *testing.T) {
	budget := base.NewTokenBudget(1000)

	for i := 0; i < 1001; i++ {
		budget.AddUsage(&base.TokenUsage{TotalTokens: 1})
	}

	if budget.CurrentUsage().TotalTokens != 1001 {
		t.Errorf("TotalTokens = %v, want 1001", budget.CurrentUsage().TotalTokens)
	}
	if !budget.IsExceeded() {
		t.Error("should be exceeded after 1001 tokens")
	}
}

// TestTokenBudget_UsageFields tests that all usage fields are tracked.
func TestTokenBudget_UsageFields(t *testing.T) {
	budget := base.NewTokenBudget(10000)

	budget.AddUsage(&base.TokenUsage{
		PromptTokens:     100,
		CompletionTokens: 200,
		TotalTokens:      300,
	})

	usage := budget.CurrentUsage()
	if usage.PromptTokens != 100 {
		t.Errorf("PromptTokens = %v, want 100", usage.PromptTokens)
	}
	if usage.CompletionTokens != 200 {
		t.Errorf("CompletionTokens = %v, want 200", usage.CompletionTokens)
	}
	if usage.TotalTokens != 300 {
		t.Errorf("TotalTokens = %v, want 300", usage.TotalTokens)
	}
}

// TestTokenBudget_ConvertFromLLMUsage_EdgeCases tests edge cases for conversion.
func TestTokenBudget_ConvertFromLLMUsage_EdgeCases(t *testing.T) {
	tests := []struct {
		name string
		usage *interfaces.LLMUsage
		wantTotal int64
	}{
		{
			name:      "nil usage",
			usage:     nil,
			wantTotal: 0,
		},
		{
			name:      "zero values",
			usage:     &interfaces.LLMUsage{},
			wantTotal: 0,
		},
		{
			name: "negative tokens",
			usage: &interfaces.LLMUsage{
				TotalTokens: -100,
			},
			wantTotal: -100,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			usage := base.ConvertFromLLMUsage(tt.usage)
			if usage.TotalTokens != tt.wantTotal {
				t.Errorf("TotalTokens = %v, want %v", usage.TotalTokens, tt.wantTotal)
			}
		})
	}
}

// TestTokenBudget_String_EdgeCases tests string representation edge cases.
func TestTokenBudget_String_EdgeCases(t *testing.T) {
	tests := []struct {
		name     string
		maxTokens int64
		usage    *base.TokenUsage
		contains string
	}{
		{
			name:      "no limit",
			maxTokens: 0,
			usage:     &base.TokenUsage{TotalTokens: 100},
			contains:  "unlimited",
		},
		{
			name:      "exceeded",
			maxTokens: 100,
			usage:     &base.TokenUsage{TotalTokens: 200},
			contains:  "remaining: 0",
		},
		{
			name:      "exactly at limit",
			maxTokens: 100,
			usage:     &base.TokenUsage{TotalTokens: 100},
			contains:  "remaining: 0",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			budget := base.NewTokenBudget(tt.maxTokens)
			budget.AddUsage(tt.usage)
			str := budget.String()
			if str == "" {
				t.Error("String() should not be empty")
			}
		})
	}
}
