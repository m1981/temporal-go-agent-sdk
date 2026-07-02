// Package classify implements the rule-based urgency classifier.
//
// The rules mirror brief.md's flowchart:
//
//	From Boss?           ─┐
//	From Family?         ─┤─► URGENT
//	Deadline today?      ─┤
//	Meeting <2h away?    ─┘
//	From Client?           ─► IMPORTANT
//	otherwise              ─► LOW
//
// Configuration is data (Rules), so tuning the assistant means editing a
// small struct — no code changes to the classifier itself.
package classify

import (
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

var defaultUrgentKeywords = []string{
	"urgent",
	"asap",
	"immediately",
	"today",
	"deadline",
	"action required",
	"security alert",
	"password",
	"verify",
	"suspended",
	"pilnie",      // PL: urgent
	"natychmiast", // PL: immediately
}

var promotionalLabels = map[string]bool{
	"CATEGORY_PROMOTIONS": true,
	"CATEGORY_SOCIAL":     true,
	"CATEGORY_FORUMS":     true,
	"CATEGORY_UPDATES":    true,
}

// Rules is a data-only description of the user's inbox.
// All sender matching is case-insensitive and substring-based.
type Rules struct {
	BossSenders    []string
	FamilySenders  []string
	ClientSenders  []string
	UrgentKeywords []string // nil ⇒ defaultUrgentKeywords
}

func (r Rules) urgentKeywords() []string {
	if r.UrgentKeywords == nil {
		return defaultUrgentKeywords
	}
	return r.UrgentKeywords
}

// UrgencyClassifier classifies Email values against Rules.
// Stateless and cheap — safe to construct per run.
type UrgencyClassifier struct {
	Rules Rules
}

// Classify returns the priority for a single email.
func (c UrgencyClassifier) Classify(e domain.Email) domain.Priority {
	sender := strings.ToLower(e.Sender)
	subject := strings.ToLower(e.Subject)
	labels := splitLabels(e.Labels)

	// Rules 1-2: identity-based URGENT (boss / family)
	if matchesAny(sender, c.Rules.BossSenders) || matchesAny(sender, c.Rules.FamilySenders) {
		return domain.PriorityUrgent
	}

	// Rules 3-4: keyword-based URGENT (deadlines, security alerts, ...)
	if containsAny(subject, c.Rules.urgentKeywords()) {
		return domain.PriorityUrgent
	}

	// Rule 5: known clients
	if matchesAny(sender, c.Rules.ClientSenders) {
		return domain.PriorityImportant
	}

	// Anything landing in a promo/social/forum bucket is definitively LOW
	for l := range labels {
		if promotionalLabels[l] {
			return domain.PriorityLow
		}
	}

	// Default: important-looking inbox mail is IMPORTANT, else LOW
	if labels["INBOX"] && labels["IMPORTANT"] {
		return domain.PriorityImportant
	}
	return domain.PriorityLow
}

// ClassifyAll returns a new slice with each email's priority set.
func (c UrgencyClassifier) ClassifyAll(emails []domain.Email) []domain.Email {
	out := make([]domain.Email, len(emails))
	for i, e := range emails {
		out[i] = e.WithPriority(c.Classify(e))
	}
	return out
}

func matchesAny(s string, patterns []string) bool {
	for _, p := range patterns {
		p = strings.ToLower(strings.TrimSpace(p))
		if p != "" && strings.Contains(s, p) {
			return true
		}
	}
	return false
}

func containsAny(text string, needles []string) bool {
	for _, n := range needles {
		if n != "" && strings.Contains(text, n) {
			return true
		}
	}
	return false
}

func splitLabels(raw string) map[string]bool {
	labels := make(map[string]bool)
	for _, l := range strings.Split(raw, ",") {
		if l = strings.TrimSpace(l); l != "" {
			labels[l] = true
		}
	}
	return labels
}
