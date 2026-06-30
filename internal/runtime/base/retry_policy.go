package base

import "time"

// Retry policy constants for different operation types.
const (
	// DefaultLLMMaxAttempts is the default number of retry attempts for LLM calls.
	// Higher than tool retries because rate limits are transient.
	DefaultLLMMaxAttempts = 10

	// DefaultToolMaxAttempts is the default number of retry attempts for tool execution.
	DefaultToolMaxAttempts = 3

	// DefaultRetrieverMaxAttempts is the default number of retry attempts for retriever operations.
	DefaultRetrieverMaxAttempts = 3

	// DefaultMemoryMaxAttempts is the default number of retry attempts for memory operations.
	DefaultMemoryMaxAttempts = 3

	// DefaultEventMaxAttempts is the default number of retry attempts for event publishing.
	DefaultEventMaxAttempts = 1

	// DefaultConversationMaxAttempts is the default number of retry attempts for conversation operations.
	DefaultConversationMaxAttempts = 1
)

// RetryPolicyConfig holds retry policy configuration.
type RetryPolicyConfig struct {
	// InitialInterval is the initial interval between retries.
	InitialInterval time.Duration
	// BackoffCoefficient is the multiplier for increasing interval between retries.
	BackoffCoefficient float64
	// MaximumInterval is the maximum interval between retries.
	MaximumInterval time.Duration
	// MaximumAttempts is the maximum number of retry attempts.
	MaximumAttempts int32
}

// NewLLMRetryPolicy creates a retry policy optimized for LLM calls.
// LLM calls may fail due to rate limits (429) which require longer backoff.
func NewLLMRetryPolicy() RetryPolicyConfig {
	return RetryPolicyConfig{
		InitialInterval:    1 * time.Second,
		BackoffCoefficient: 2.0,
		MaximumInterval:    1 * time.Minute,
		MaximumAttempts:    DefaultLLMMaxAttempts,
	}
}

// NewToolRetryPolicy creates a retry policy for tool execution.
func NewToolRetryPolicy() RetryPolicyConfig {
	return RetryPolicyConfig{
		InitialInterval:    1 * time.Second,
		BackoffCoefficient: 2.0,
		MaximumInterval:    10 * time.Minute,
		MaximumAttempts:    DefaultToolMaxAttempts,
	}
}

// NewRetrieverRetryPolicy creates a retry policy for retriever operations.
func NewRetrieverRetryPolicy() RetryPolicyConfig {
	return RetryPolicyConfig{
		InitialInterval:    1 * time.Second,
		BackoffCoefficient: 2.0,
		MaximumInterval:    5 * time.Minute,
		MaximumAttempts:    DefaultRetrieverMaxAttempts,
	}
}

// NewMemoryRetryPolicy creates a retry policy for memory operations.
func NewMemoryRetryPolicy() RetryPolicyConfig {
	return RetryPolicyConfig{
		InitialInterval:    1 * time.Second,
		BackoffCoefficient: 2.0,
		MaximumInterval:    5 * time.Minute,
		MaximumAttempts:    DefaultMemoryMaxAttempts,
	}
}

// NewEventRetryPolicy creates a retry policy for event publishing.
// Events are fire-and-forget, so minimal retries.
func NewEventRetryPolicy() RetryPolicyConfig {
	return RetryPolicyConfig{
		InitialInterval:    1 * time.Second,
		BackoffCoefficient: 1.0,
		MaximumInterval:    1 * time.Second,
		MaximumAttempts:    DefaultEventMaxAttempts,
	}
}
