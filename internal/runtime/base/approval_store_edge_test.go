package base_test

import (
	"sync"
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/internal/runtime/base"
	"github.com/m1981/temporal-go-agent-sdk/internal/types"
)

// TestApprovalStore_ZeroTTL tests behavior with zero TTL.
func TestApprovalStore_ZeroTTL(t *testing.T) {
	store := base.NewApprovalStore(0)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	// With zero TTL, entries expire immediately
	time.Sleep(1 * time.Millisecond)
	_, ok := store.Load("token-1")
	if ok {
		t.Error("zero TTL should expire immediately")
	}
}

// TestApprovalStore_NegativeTTL tests behavior with negative TTL.
func TestApprovalStore_NegativeTTL(t *testing.T) {
	store := base.NewApprovalStore(-1 * time.Second)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	// With negative TTL, entries should be expired immediately
	_, ok := store.Load("token-1")
	if ok {
		t.Error("negative TTL should expire immediately")
	}
}

// TestApprovalStore_VeryLongTTL tests behavior with very long TTL.
func TestApprovalStore_VeryLongTTL(t *testing.T) {
	store := base.NewApprovalStore(24 * time.Hour)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	_, ok := store.Load("token-1")
	if !ok {
		t.Error("should find token with long TTL")
	}
}

// TestApprovalStore_ConcurrentStoreDelete tests concurrent store and delete.
func TestApprovalStore_ConcurrentStoreDelete(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)
	var wg sync.WaitGroup

	// Concurrent stores
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			store.Store("token-"+string(rune('0'+i%10)), make(chan types.ApprovalStatus, 1))
		}(i)
	}

	// Concurrent deletes
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			store.Delete("token-" + string(rune('0'+i%10)))
		}(i)
	}

	wg.Wait()
}

// TestApprovalStore_ConcurrentLoadDelete tests concurrent load and delete.
func TestApprovalStore_ConcurrentLoadDelete(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	// Pre-populate
	for i := 0; i < 10; i++ {
		store.Store("token-"+string(rune('0'+i)), make(chan types.ApprovalStatus, 1))
	}

	var wg sync.WaitGroup

	// Concurrent loads
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			store.Load("token-" + string(rune('0'+i)))
		}(i)
	}

	// Concurrent deletes
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			store.Delete("token-" + string(rune('0'+i)))
		}(i)
	}

	wg.Wait()
}

// TestApprovalStore_LargeNumberOfTokens tests with many tokens.
func TestApprovalStore_LargeNumberOfTokens(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	// Store 1000 tokens
	for i := 0; i < 1000; i++ {
		store.Store("token-"+string(rune(i)), make(chan types.ApprovalStatus, 1))
	}

	if store.Size() != 1000 {
		t.Errorf("Size() = %v, want 1000", store.Size())
	}

	// Cleanup all (none expired)
	cleaned := store.CleanupExpired()
	if cleaned != 0 {
		t.Errorf("CleanupExpired() = %v, want 0", cleaned)
	}
}

// TestApprovalStore_CleanupExpired_Mixed tests cleanup with mix of expired and non-expired.
func TestApprovalStore_CleanupExpired_Mixed(t *testing.T) {
	store := base.NewApprovalStore(100 * time.Millisecond)

	// Store some tokens
	store.Store("token-1", make(chan types.ApprovalStatus, 1))
	store.Store("token-2", make(chan types.ApprovalStatus, 1))

	// Wait for expiry
	time.Sleep(150 * time.Millisecond)

	// Store new token (not expired)
	store.Store("token-3", make(chan types.ApprovalStatus, 1))

	// Cleanup should only remove expired
	cleaned := store.CleanupExpired()
	if cleaned != 2 {
		t.Errorf("CleanupExpired() = %v, want 2", cleaned)
	}

	// New token should still exist
	_, ok := store.Load("token-3")
	if !ok {
		t.Error("token-3 should still exist")
	}
}

// TestApprovalStore_OverwriteToken tests overwriting an existing token.
func TestApprovalStore_OverwriteToken(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	ch1 := make(chan types.ApprovalStatus, 1)
	ch2 := make(chan types.ApprovalStatus, 1)

	store.Store("token-1", ch1)
	store.Store("token-1", ch2)

	loaded, ok := store.Load("token-1")
	if !ok {
		t.Error("should find token-1")
	}
	if loaded != ch2 {
		t.Error("should have the overwritten channel")
	}
}

// TestApprovalStore_DeleteNonExistent tests deleting non-existent token.
func TestApprovalStore_DeleteNonExistent(t *testing.T) {
	store := base.NewApprovalStore(1 * time.Minute)

	// Should not panic
	store.Delete("non-existent")
}

// TestApprovalStore_LoadAfterExpiry tests loading immediately after expiry.
func TestApprovalStore_LoadAfterExpiry(t *testing.T) {
	store := base.NewApprovalStore(50 * time.Millisecond)

	ch := make(chan types.ApprovalStatus, 1)
	store.Store("token-1", ch)

	// Should exist immediately
	_, ok := store.Load("token-1")
	if !ok {
		t.Error("should find token immediately")
	}

	// Wait for expiry
	time.Sleep(60 * time.Millisecond)

	// Should be expired
	_, ok = store.Load("token-1")
	if ok {
		t.Error("should not find expired token")
	}
}

// TestApprovalStore_StartCleanupWorker tests the background cleanup worker.
func TestApprovalStore_StartCleanupWorker(t *testing.T) {
	store := base.NewApprovalStore(50 * time.Millisecond)

	// Store some tokens
	store.Store("token-1", make(chan types.ApprovalStatus, 1))
	store.Store("token-2", make(chan types.ApprovalStatus, 1))

	// Start cleanup worker
	stop := store.StartCleanupWorker(30 * time.Millisecond)
	defer stop()

	// Wait for cleanup to run
	time.Sleep(100 * time.Millisecond)

	// All tokens should be cleaned up
	if store.Size() != 0 {
		t.Errorf("Size() = %v, want 0 after cleanup", store.Size())
	}
}
