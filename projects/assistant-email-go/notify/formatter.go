// Package notify renders the deterministic summary skeleton.
//
// The LLM writes prose; this package writes the block the user can trust to
// always look the same and to reflect ground-truth counts. Kept pure (no I/O).
package notify

import (
	"fmt"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

const defaultMaxItemsPerSection = 5

var sections = []struct {
	priority domain.Priority
	header   string
}{
	{domain.PriorityUrgent, "🚨 URGENT"},
	{domain.PriorityImportant, "⭐ IMPORTANT"},
	{domain.PriorityLow, "📋 LOW"},
}

// Summary is the structured digest — good for tests, logging, and templating.
type Summary struct {
	Total      int
	ByPriority map[domain.Priority][]domain.Email
}

func (s Summary) UrgentCount() int { return len(s.ByPriority[domain.PriorityUrgent]) }
func (s Summary) HasUrgent() bool  { return s.UrgentCount() > 0 }

// Formatter builds a Summary and renders it as Markdown.
// The zero value uses defaultMaxItemsPerSection.
type Formatter struct {
	MaxItemsPerSection int
}

func (f Formatter) maxItems() int {
	if f.MaxItemsPerSection > 0 {
		return f.MaxItemsPerSection
	}
	return defaultMaxItemsPerSection
}

// Summarize buckets emails by priority. Unclassified emails count as LOW.
func (f Formatter) Summarize(emails []domain.Email) Summary {
	buckets := map[domain.Priority][]domain.Email{
		domain.PriorityUrgent:    {},
		domain.PriorityImportant: {},
		domain.PriorityLow:       {},
	}
	for _, e := range emails {
		p := e.Priority
		if p == "" {
			p = domain.PriorityLow
		}
		buckets[p] = append(buckets[p], e)
	}
	return Summary{Total: len(emails), ByPriority: buckets}
}

// Render produces the stable Markdown block.
func (f Formatter) Render(s Summary) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# Email Summary — %d emails (%d urgent)\n\n", s.Total, s.UrgentCount())
	for _, sec := range sections {
		bucket := s.ByPriority[sec.priority]
		if len(bucket) == 0 {
			continue
		}
		fmt.Fprintf(&b, "## %s (%d)\n", sec.header, len(bucket))
		shown := bucket
		if len(shown) > f.maxItems() {
			shown = shown[:f.maxItems()]
		}
		for _, e := range shown {
			fmt.Fprintf(&b, "- **%s** — %s (%s)\n", e.Subject, e.Sender, e.Date)
		}
		if extra := len(bucket) - f.maxItems(); extra > 0 {
			fmt.Fprintf(&b, "- …and %d more\n", extra)
		}
		b.WriteString("\n")
	}
	return strings.TrimRight(b.String(), "\n") + "\n"
}

// SummarizeAndRender is the one-call form used by the pipeline.
func (f Formatter) SummarizeAndRender(emails []domain.Email) (Summary, string) {
	s := f.Summarize(emails)
	return s, f.Render(s)
}
