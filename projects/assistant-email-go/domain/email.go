// Package domain holds pure value objects. They do not know about Gmail,
// gmcli, or the LLM — a direct port of the Python email_assistant.domain.
package domain

// Priority classifies an email's urgency (see brief.md > Priority Classification).
type Priority string

const (
	PriorityUrgent    Priority = "URGENT"
	PriorityImportant Priority = "IMPORTANT"
	PriorityLow       Priority = "LOW"
)

// Email is a single parsed email row from `gmcli search`.
// ID is the Gmail thread ID (gmcli's search returns thread-level rows).
// An empty Priority means "not yet classified".
type Email struct {
	ID       string   `json:"id"`
	Date     string   `json:"date"`
	Sender   string   `json:"sender"`
	Subject  string   `json:"subject"`
	Labels   string   `json:"labels"`
	Priority Priority `json:"priority,omitempty"`
}

// WithPriority returns a copy with the priority set (value semantics ⇒ no mutation).
func (e Email) WithPriority(p Priority) Email {
	e.Priority = p
	return e
}
