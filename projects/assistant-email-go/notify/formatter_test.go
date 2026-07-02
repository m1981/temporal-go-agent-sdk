package notify

import (
	"fmt"
	"strings"
	"testing"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

func email(id string, p domain.Priority) domain.Email {
	return domain.Email{ID: id, Date: "2026-07-01", Sender: "s@x.com", Subject: "subj-" + id, Priority: p}
}

func TestSummarizeCountsAndBuckets(t *testing.T) {
	f := Formatter{}
	s := f.Summarize([]domain.Email{
		email("1", domain.PriorityUrgent),
		email("2", domain.PriorityImportant),
		email("3", ""), // unclassified counts as LOW
	})
	if s.Total != 3 {
		t.Errorf("Total = %d, want 3", s.Total)
	}
	if s.UrgentCount() != 1 || !s.HasUrgent() {
		t.Errorf("UrgentCount = %d, want 1", s.UrgentCount())
	}
	if got := len(s.ByPriority[domain.PriorityLow]); got != 1 {
		t.Errorf("LOW bucket = %d, want 1 (unclassified defaults to LOW)", got)
	}
}

func TestRenderStructureAndOrder(t *testing.T) {
	f := Formatter{}
	_, out := f.SummarizeAndRender([]domain.Email{
		email("1", domain.PriorityLow),
		email("2", domain.PriorityUrgent),
	})
	if !strings.HasPrefix(out, "# Email Summary — 2 emails (1 urgent)") {
		t.Errorf("bad header:\n%s", out)
	}
	urgentIdx := strings.Index(out, "🚨 URGENT")
	lowIdx := strings.Index(out, "📋 LOW")
	if urgentIdx == -1 || lowIdx == -1 || urgentIdx > lowIdx {
		t.Errorf("sections missing or out of order:\n%s", out)
	}
	if strings.Contains(out, "⭐ IMPORTANT") {
		t.Errorf("empty section should be omitted:\n%s", out)
	}
	if !strings.HasSuffix(out, "\n") || strings.HasSuffix(out, "\n\n") {
		t.Errorf("output must end with exactly one newline:\n%q", out)
	}
}

func TestRenderTruncation(t *testing.T) {
	f := Formatter{MaxItemsPerSection: 5}
	var emails []domain.Email
	for i := 0; i < 7; i++ {
		emails = append(emails, email(fmt.Sprint(i), domain.PriorityUrgent))
	}
	_, out := f.SummarizeAndRender(emails)
	if !strings.Contains(out, "- …and 2 more") {
		t.Errorf("missing overflow line:\n%s", out)
	}
	if strings.Contains(out, "subj-5") {
		t.Errorf("item beyond cap should not render:\n%s", out)
	}
}

func TestRenderIsDeterministic(t *testing.T) {
	f := Formatter{}
	in := []domain.Email{email("a", domain.PriorityUrgent), email("b", domain.PriorityLow)}
	_, first := f.SummarizeAndRender(in)
	for i := 0; i < 10; i++ {
		if _, again := f.SummarizeAndRender(in); again != first {
			t.Fatal("render output is not stable across calls")
		}
	}
}
