package base_test

import (
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/internal/types"
)

// TestApprovalStore_StoreAndLoad tests basic store and load operations.
func TestApprovalStore_StoreAndLoad(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	loaded, ok := store.Load("token-1")
	if !ok {
		t.Error("expected to find token-1")
	}
	if loaded != ch {
		t.Error("loaded channel should be the same as stored channel")
	}
}

// TestApprovalStore_LoadNonExistent tests loading non-existent token.
func TestApprovalStore_LoadNonExistent(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	_, ok := store.Load("non-existent")
	if ok {
		t.Error("should not find non-existent token")
	}
}

// TestApprovalStore_Delete tests deleting tokens.
func TestApprovalStore_Delete(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	store.Delete("token-1")

	_, ok := store.Load("token-1")
	if ok {
		t.Error("should not find deleted token")
	}
}

// TestApprovalStore_TTLExpiry tests that tokens expire after TTL.
func TestApprovalStore_TTLExpiry(t *testing.T) {
	store := base.NewApprovalStore(100 * time.Millisecond)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	// Should exist immediately
	_, ok := store.Load("token-1")
	if !ok {
		t.Error("expected to find token-1 immediately after store")
	}

	// Wait for TTL to expire
	time.Sleep(150 * time.Millisecond)

	// Should be expired
	_, ok = store.Load("token-1")
	if ok {
		t.Error("token-1 should have expired")
	}
}

// TestApprovalStore_Cleanup tests manual cleanup of expired entries.
func TestApprovalStore_Cleanup(t *testing.T) {
	store := base.NewApprovalStore(100 * time.Millisecond)

	// Store multiple tokens
	store.Store("token-1", make(chan types.ApprovalStatus, 1))
	store.Store("token-2", make(chan types.ApprovalStatus, 1))
	store.Store("token-3", make(chan types.ApprovalStatus, 1))

	// Wait for expiry
	time.Sleep(150 * time.Millisecond)

	// Cleanup should remove all expired entries
	cleaned := store.CleanupExpired()
	if cleaned != 3 {
		t.Errorf("CleanupExpired() = %v, want 3", cleaned)
	}

	// All tokens should be gone
	_, ok1 := store.Load("token-1")
	_, ok2 := store.Load("token-2")
	_, ok3 := store.Load("token-3")
	if ok1 || ok2 || ok3 {
		t.Error("all tokens should be cleaned up")
	}
}

// TestApprovalStore_Size tests size reporting.
func TestApprovalStore_Size(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	if store.Size() != 0 {
		t.Errorf("Size() = %v, want 0", store.Size())
	}

	store.Store("token-1", make(chan types.ApprovalStatus, 1))
	store.Store("token-2", make(chan types.ApprovalStatus, 1))

	if store.Size() != 2 {
		t.Errorf("Size() = %v, want 2", store.Size())
	}
}

// TestApprovalStore_ConcurrentAccess tests concurrent access safety.
func TestApprovalStore_ConcurrentAccess(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	done := make(chan bool, 10)

	// Concurrent stores
	for i := 0; i < 10; i++ {
		go func(i int) {
			store.Store("token-"+string(rune('0'+i)), make(chan types.ApprovalStatus, 1))
			done <- true
		}(i)
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}

	if store.Size() != 10 {
		t.Errorf("Size() = %v, want 10", store.Size())
	}
}
