package memory

import (
	"path/filepath"
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

var seen = time.Date(2026, 7, 1, 10, 0, 0, 0, time.UTC)

func openStore(t *testing.T, path string) *ThreadStore {
	t.Helper()
	s, err := Open(path)
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func rec(id string) ThreadRecord {
	return ThreadRecord{
		ThreadID:     id,
		Subject:      "subject-" + id,
		Sender:       "s@x.com",
		LastSeenUTC:  seen,
		LastPriority: domain.PriorityUrgent,
	}
}

func TestUpsertGetRoundtrip(t *testing.T) {
	s := openStore(t, filepath.Join(t.TempDir(), "m.sqlite"))
	if err := s.Upsert(rec("t1")); err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	got, err := s.Get("t1")
	if err != nil || got == nil {
		t.Fatalf("Get: %v, %v", got, err)
	}
	if got.Subject != "subject-t1" || got.LastPriority != domain.PriorityUrgent {
		t.Errorf("roundtrip mismatch: %+v", got)
	}
	if !got.LastSeenUTC.Equal(seen) {
		t.Errorf("LastSeenUTC = %v, want %v", got.LastSeenUTC, seen)
	}
	if got.NotifiedUTC != nil {
		t.Errorf("NotifiedUTC should be nil, got %v", got.NotifiedUTC)
	}
}

func TestGetUnknownReturnsNil(t *testing.T) {
	s := openStore(t, filepath.Join(t.TempDir(), "m.sqlite"))
	got, err := s.Get("nope")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got != nil {
		t.Errorf("want nil for unknown id, got %+v", got)
	}
}

func TestUpsertPreservesNotified(t *testing.T) {
	// The de-duplication invariant: re-seeing a thread must not erase the
	// fact that we already alerted the user about it.
	s := openStore(t, filepath.Join(t.TempDir(), "m.sqlite"))
	if err := s.Upsert(rec("t1")); err != nil {
		t.Fatal(err)
	}
	notified := seen.Add(time.Minute)
	if err := s.MarkNotified("t1", notified); err != nil {
		t.Fatal(err)
	}
	// Second run re-upserts the same thread with no notified timestamp.
	if err := s.Upsert(rec("t1")); err != nil {
		t.Fatal(err)
	}
	got, err := s.Get("t1")
	if err != nil || got == nil {
		t.Fatalf("Get: %v, %v", got, err)
	}
	if got.NotifiedUTC == nil || !got.NotifiedUTC.Equal(notified) {
		t.Errorf("NotifiedUTC = %v, want %v (must survive upsert)", got.NotifiedUTC, notified)
	}
}

func TestKnownIDs(t *testing.T) {
	s := openStore(t, filepath.Join(t.TempDir(), "m.sqlite"))
	for _, id := range []string{"a", "b"} {
		if err := s.Upsert(rec(id)); err != nil {
			t.Fatal(err)
		}
	}
	ids, err := s.KnownIDs()
	if err != nil {
		t.Fatal(err)
	}
	if len(ids) != 2 || !ids["a"] || !ids["b"] {
		t.Errorf("KnownIDs = %v", ids)
	}
}

func TestPersistsAcrossReopen(t *testing.T) {
	path := filepath.Join(t.TempDir(), "m.sqlite")
	s, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Upsert(rec("t1")); err != nil {
		t.Fatal(err)
	}
	if err := s.Close(); err != nil {
		t.Fatal(err)
	}

	s2 := openStore(t, path)
	got, err := s2.Get("t1")
	if err != nil || got == nil {
		t.Fatalf("record lost across reopen: %v, %v", got, err)
	}
}
