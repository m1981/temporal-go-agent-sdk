package base_test

import (
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
)

// TestRetryPolicy_LLMCall tests LLM retry policy configuration.
func TestRetryPolicy_LLMCall(t *testing.T) {
	policy := base.NewLLMRetryPolicy()

	if policy.InitialInterval != 1*time.Second {
		t.Errorf("InitialInterval = %v, want %v", policy.InitialInterval, 1*time.Second)
	}
	if policy.BackoffCoefficient != 2.0 {
		t.Errorf("BackoffCoefficient = %v, want %v", policy.BackoffCoefficient, 2.0)
	}
	if policy.MaximumInterval != 1*time.Minute {
		t.Errorf("MaximumInterval = %v, want %v", policy.MaximumInterval, 1*time.Minute)
	}
	if policy.MaximumAttempts != 10 {
		t.Errorf("MaximumAttempts = %v, want %v", policy.MaximumAttempts, 10)
	}
}

// TestRetryPolicy_ToolExecution tests tool execution retry policy.
func TestRetryPolicy_ToolExecution(t *testing.T) {
	policy := base.NewToolRetryPolicy()

	if policy.MaximumAttempts != 3 {
		t.Errorf("MaximumAttempts = %v, want %v", policy.MaximumAttempts, 3)
	}
}

// TestRetryPolicy_Constants tests retry policy constants.
func TestRetryPolicy_Constants(t *testing.T) {
	if base.DefaultLLMMaxAttempts != 10 {
		t.Errorf("DefaultLLMMaxAttempts = %v, want %v", base.DefaultLLMMaxAttempts, 10)
	}
	if base.DefaultToolMaxAttempts != 3 {
		t.Errorf("DefaultToolMaxAttempts = %v, want %v", base.DefaultToolMaxAttempts, 3)
	}
}
