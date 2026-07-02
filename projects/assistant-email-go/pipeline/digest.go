// Package pipeline composes the deterministic digest (Phase 3 integration).
//
// The agent's job is to *talk*. This pipeline's job is to *record*: classify
// every fetched email against user rules, persist thread memory, and render
// a stable Markdown summary. The two run side-by-side so there is always a
// ground-truth audit trail regardless of what the LLM wrote.
package pipeline

import (
	"context"
	"fmt"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/classify"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/memory"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/notify"
)

// Searcher is the slice of the Gmail client the pipeline needs.
type Searcher interface {
	Search(ctx context.Context, query string, maxResults int) ([]domain.Email, error)
}

// Store is the slice of the thread store the pipeline needs.
type Store interface {
	Upsert(rec memory.ThreadRecord) error
	KnownIDs() (map[string]bool, error)
}

// Result is what one deterministic pass over the inbox produced.
type Result struct {
	Summary      notify.Summary
	Rendered     string
	NewThreadIDs map[string]bool
}

// HasNewUrgent reports whether any urgent email was seen for the first time
// this run — the trigger condition for an immediate alert per brief.md.
func (r Result) HasNewUrgent() bool {
	for _, e := range r.Summary.ByPriority[domain.PriorityUrgent] {
		if r.NewThreadIDs[e.ID] {
			return true
		}
	}
	return false
}

// Digest wires the three Phase-3 features into one pass over the inbox.
// Every collaborator is injectable so tests hand in fakes.
type Digest struct {
	Gmail      Searcher
	Classifier classify.UrgencyClassifier
	Formatter  notify.Formatter
	Memory     Store
	Now        func() time.Time // nil ⇒ time.Now
}

// Run fetches, classifies, diffs against memory, renders, and persists.
func (d Digest) Run(ctx context.Context, query string, maxResults int) (Result, error) {
	emails, err := d.Gmail.Search(ctx, query, maxResults)
	if err != nil {
		return Result{}, fmt.Errorf("digest: search: %w", err)
	}
	classified := d.Classifier.ClassifyAll(emails)

	known, err := d.Memory.KnownIDs()
	if err != nil {
		return Result{}, fmt.Errorf("digest: known ids: %w", err)
	}
	newIDs := make(map[string]bool)
	for _, e := range classified {
		if !known[e.ID] {
			newIDs[e.ID] = true
		}
	}

	summary, rendered := d.Formatter.SummarizeAndRender(classified)

	now := time.Now().UTC()
	if d.Now != nil {
		now = d.Now()
	}
	for _, e := range classified {
		p := e.Priority
		if p == "" {
			p = domain.PriorityLow
		}
		if err := d.Memory.Upsert(memory.ThreadRecord{
			ThreadID:     e.ID,
			Subject:      e.Subject,
			Sender:       e.Sender,
			LastSeenUTC:  now,
			LastPriority: p,
		}); err != nil {
			return Result{}, fmt.Errorf("digest: persist: %w", err)
		}
	}

	return Result{Summary: summary, Rendered: rendered, NewThreadIDs: newIDs}, nil
}
