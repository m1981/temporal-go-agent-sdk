package tools

import (
	"context"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

type fakeGmail struct {
	searchQuery string
	searchMax   int
	sendArgs    []string
	threadID    string
}

func (f *fakeGmail) Search(_ context.Context, query string, maxResults int) ([]domain.Email, error) {
	f.searchQuery, f.searchMax = query, maxResults
	return []domain.Email{{ID: "t1", Sender: "a@b.com", Subject: "hi"}}, nil
}

func (f *fakeGmail) Thread(_ context.Context, threadID string) (string, error) {
	f.threadID = threadID
	return "full thread body", nil
}

func (f *fakeGmail) Send(_ context.Context, to, subject, body, threadID string) (string, error) {
	f.sendArgs = []string{to, subject, body, threadID}
	return "ok", nil
}

func TestReaderSearchDefaults(t *testing.T) {
	fake := &fakeGmail{}
	r := &GmailReader{Client: fake}
	out, err := r.Execute(context.Background(), map[string]any{"action": "search"})
	if err != nil {
		t.Fatal(err)
	}
	if fake.searchQuery != defaultQuery || fake.searchMax != defaultMaxResults {
		t.Errorf("defaults not applied: query=%q max=%d", fake.searchQuery, fake.searchMax)
	}
	m := out.(map[string]any)
	if m["total_count"] != 1 {
		t.Errorf("total_count = %v, want 1", m["total_count"])
	}
}

func TestReaderSearchClampsMaxResults(t *testing.T) {
	fake := &fakeGmail{}
	r := &GmailReader{Client: fake}
	// JSON numbers arrive as float64.
	if _, err := r.Execute(context.Background(), map[string]any{"action": "search", "max_results": float64(500)}); err != nil {
		t.Fatal(err)
	}
	if fake.searchMax != 100 {
		t.Errorf("max_results not clamped: %d", fake.searchMax)
	}
}

func TestReaderThreadRequiresID(t *testing.T) {
	r := &GmailReader{Client: &fakeGmail{}}
	if _, err := r.Execute(context.Background(), map[string]any{"action": "thread"}); err == nil {
		t.Fatal("want error when thread_id missing")
	}
}

func TestReaderUnknownAction(t *testing.T) {
	r := &GmailReader{Client: &fakeGmail{}}
	if _, err := r.Execute(context.Background(), map[string]any{"action": "delete_all"}); err == nil {
		t.Fatal("want error for unknown action")
	}
}

func TestSenderRequiresAllFields(t *testing.T) {
	s := &GmailSender{Client: &fakeGmail{}}
	_, err := s.Execute(context.Background(), map[string]any{"to": "x@y.com", "subject": "s"})
	if err == nil {
		t.Fatal("want error when body missing")
	}
}

func TestSenderPassesArgs(t *testing.T) {
	fake := &fakeGmail{}
	s := &GmailSender{Client: fake}
	out, err := s.Execute(context.Background(), map[string]any{
		"to": "x@y.com", "subject": "s", "body": "b", "thread_id": "thr",
	})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"x@y.com", "s", "b", "thr"}
	for i := range want {
		if fake.sendArgs[i] != want[i] {
			t.Fatalf("sendArgs = %v, want %v", fake.sendArgs, want)
		}
	}
	if out.(map[string]any)["status"] != "sent" {
		t.Errorf("status missing in result: %v", out)
	}
}

func TestToolSchemasDeclareRequiredFields(t *testing.T) {
	reader, sender := &GmailReader{}, &GmailSender{}
	if req := reader.Parameters()["required"].([]string); len(req) != 1 || req[0] != "action" {
		t.Errorf("reader required = %v", req)
	}
	if req := sender.Parameters()["required"].([]string); len(req) != 3 {
		t.Errorf("sender required = %v", req)
	}
}
