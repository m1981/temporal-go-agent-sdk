package base

import (
	"sync"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/internal/types"
)

// approvalEntry holds a channel and its expiration time.
type approvalEntry struct {
	ch        chan types.ApprovalStatus
	expiresAt time.Time
}

// ApprovalStore manages approval tokens with TTL-based expiration.
// This prevents memory leaks when approvals are never resolved (e.g., agent crash).
type ApprovalStore struct {
	mu      sync.RWMutex
	entries map[string]approvalEntry
	ttl     time.Duration
}

// NewApprovalStore creates a new ApprovalStore with the specified TTL.
func NewApprovalStore(ttl time.Duration) *ApprovalStore {
	return &ApprovalStore{
		entries: make(map[string]approvalEntry),
		ttl:     ttl,
	}
}

// Store adds a new approval token with the associated channel.
// The entry will expire after the configured TTL.
func (s *ApprovalStore) Store(token string, ch chan types.ApprovalStatus) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.entries[token] = approvalEntry{
		ch:        ch,
		expiresAt: time.Now().Add(s.ttl),
	}
}

// Load retrieves the channel for an approval token.
// Returns false if the token doesn't exist or has expired.
// Expired entries are automatically cleaned up on access.
func (s *ApprovalStore) Load(token string) (chan types.ApprovalStatus, bool) {
	s.mu.RLock()
	entry, exists := s.entries[token]
	s.mu.RUnlock()

	if !exists {
		return nil, false
	}

	// Check if expired
	if time.Now().After(entry.expiresAt) {
		// Clean up expired entry
		s.Delete(token)
		return nil, false
	}

	return entry.ch, true
}

// Delete removes an approval token.
func (s *ApprovalStore) Delete(token string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.entries, token)
}

// CleanupExpired removes all expired entries and returns the count of removed entries.
func (s *ApprovalStore) CleanupExpired() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	now := time.Now()
	cleaned := 0

	for token, entry := range s.entries {
		if now.After(entry.expiresAt) {
			delete(s.entries, token)
			cleaned++
		}
	}

	return cleaned
}

// Size returns the number of entries in the store (including potentially expired ones).
func (s *ApprovalStore) Size() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.entries)
}

// StartCleanupWorker starts a background goroutine that periodically cleans up expired entries.
// It returns a stop function that should be called when the store is no longer needed.
func (s *ApprovalStore) StartCleanupWorker(interval time.Duration) func() {
	stopCh := make(chan struct{})
	var once sync.Once

	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-stopCh:
				return
			case <-ticker.C:
				s.CleanupExpired()
			}
		}
	}()

	return func() {
		once.Do(func() { close(stopCh) })
	}
}
