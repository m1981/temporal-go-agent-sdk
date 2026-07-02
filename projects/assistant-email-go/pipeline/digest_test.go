package pipeline

import (
	"context"
	"path/filepath"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/classify"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/memory"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/notify"
)

type fakeSearcher struct {
	emails []domain.Email
}

func (f *fakeSearcher) Search(context.Context, string, int) ([]domain.Email, error) {
	return f.emails, nil
}

func newDigest(t *testing.T, emails []domain.Email) Digest {
	t.Helper()
	store, err := memory.Open(filepath.Join(t.TempDir(), "m.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { store.Close() })
	return Digest{
		Gmail:      &fakeSearcher{emails: emails},
		Classifier: classify.UrgencyClassifier{Rules: classify.Rules{BossSenders: []string{"boss@x.com"}}},
		Formatter:  notify.Formatter{},
		Memory:     store,
	}
}

func TestRunDetectsNewUrgentThenDeduplicates(t *testing.T) {
	// This is the notification logic from brief.md: alert on first sight of
	// an urgent thread, stay quiet when the same thread reappears.
	d := newDigest(t, []domain.Email{
		{ID: "u1", Sender: "boss@x.com", Subject: "need this now"},
		{ID: "l1", Sender: "shop@y.com", Subject: "sale", Labels: "CATEGORY_PROMOTIONS"},
	})

	first, err := d.Run(context.Background(), "newer_than:2h", 50)
	if err != nil {
		t.Fatal(err)
	}
	if !first.HasNewUrgent() {
		t.Error("run 1: want HasNewUrgent = true (boss thread is new)")
	}
	if len(first.NewThreadIDs) != 2 {
		t.Errorf("run 1: NewThreadIDs = %v, want both ids", first.NewThreadIDs)
	}

	second, err := d.Run(context.Background(), "newer_than:2h", 50)
	if err != nil {
		t.Fatal(err)
	}
	if second.HasNewUrgent() {
		t.Error("run 2: want HasNewUrgent = false (memory dedup)")
	}
	if len(second.NewThreadIDs) != 0 {
		t.Errorf("run 2: NewThreadIDs = %v, want empty", second.NewThreadIDs)
	}
}

func TestRunSummaryReflectsClassification(t *testing.T) {
	d := newDigest(t, []domain.Email{
		{ID: "u1", Sender: "boss@x.com", Subject: "hi"},
		{ID: "x1", Sender: "rand@z.com", Subject: "hello", Labels: "INBOX"},
	})
	res, err := d.Run(context.Background(), "q", 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Summary.Total != 2 || res.Summary.UrgentCount() != 1 {
		t.Errorf("summary = total %d urgent %d, want 2/1", res.Summary.Total, res.Summary.UrgentCount())
	}
	if res.Rendered == "" {
		t.Error("rendered digest is empty")
	}
}
