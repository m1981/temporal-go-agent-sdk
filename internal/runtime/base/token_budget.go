package base

import (
	"fmt"
	"sync"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// TokenUsage tracks cumulative token usage across LLM calls.
type TokenUsage struct {
	PromptTokens     int64
	CompletionTokens int64
	TotalTokens      int64
}

// TokenBudget enforces a cumulative token limit across multiple LLM calls.
// Thread-safe for concurrent use.
type TokenBudget struct {
	mu         sync.Mutex
	maxTokens  int64
	usage      TokenUsage
	exceeded   bool
}

// NewTokenBudget creates a new token budget with the specified limit.
// A maxTokens of 0 means no limit.
func NewTokenBudget(maxTokens int64) *TokenBudget {
	return &TokenBudget{
		maxTokens: maxTokens,
	}
}

// AddUsage adds token usage to the budget. Nil usage is ignored.
func (b *TokenBudget) AddUsage(usage *TokenUsage) {
	if usage == nil {
		return
	}

	b.mu.Lock()
	defer b.mu.Unlock()

	b.usage.PromptTokens += usage.PromptTokens
	b.usage.CompletionTokens += usage.CompletionTokens
	b.usage.TotalTokens += usage.TotalTokens

	if b.maxTokens > 0 && b.usage.TotalTokens > b.maxTokens {
		b.exceeded = true
	}
}

// IsExceeded returns true if the budget has been exceeded.
func (b *TokenBudget) IsExceeded() bool {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.exceeded
}

// Remaining returns the remaining tokens in the budget.
// Returns 0 if no limit is set or if the budget is exceeded.
func (b *TokenBudget) Remaining() int64 {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.maxTokens <= 0 {
		return 0
	}

	remaining := b.maxTokens - b.usage.TotalTokens
	if remaining < 0 {
		return 0
	}
	return remaining
}

// CurrentUsage returns the current token usage.
func (b *TokenBudget) CurrentUsage() TokenUsage {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.usage
}

// String returns a human-readable representation of the budget status.
func (b *TokenBudget) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.maxTokens <= 0 {
		return fmt.Sprintf("TokenBudget{usage: %d tokens, unlimited}", b.usage.TotalTokens)
	}
	remaining := b.maxTokens - b.usage.TotalTokens
	if remaining < 0 {
		remaining = 0
	}
	return fmt.Sprintf("TokenBudget{usage: %d/%d tokens, remaining: %d}", b.usage.TotalTokens, b.maxTokens, remaining)
}

// ConvertFromLLMUsage converts an interfaces.LLMUsage to TokenUsage.
// Returns zero TokenUsage for nil input.
func ConvertFromLLMUsage(usage *interfaces.LLMUsage) TokenUsage {
	if usage == nil {
		return TokenUsage{}
	}
	return TokenUsage{
		PromptTokens:     usage.PromptTokens,
		CompletionTokens: usage.CompletionTokens,
		TotalTokens:      usage.TotalTokens,
	}
}
