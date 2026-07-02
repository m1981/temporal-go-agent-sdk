// Package tools exposes Gmail operations to the LLM via the SDK's
// interfaces.Tool contract (ADR-002: one tool per operation type).
package tools

import (
	"context"
	"fmt"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	sdktools "github.com/m1981/temporal-go-agent-sdk/pkg/tools"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

const (
	defaultQuery      = "newer_than:1d"
	defaultMaxResults = 20
)

// GmailClient is the seam between LLM tools and the gmcli transport.
// *gmail.Client satisfies it; tests inject fakes.
type GmailClient interface {
	Search(ctx context.Context, query string, maxResults int) ([]domain.Email, error)
	Thread(ctx context.Context, threadID string) (string, error)
	Send(ctx context.Context, to, subject, body, threadID string) (string, error)
}

var _ interfaces.Tool = (*GmailReader)(nil)

// GmailReader searches Gmail and reads full threads. Two actions
// ("search", "thread") behind one tool keep the LLM's inventory small.
type GmailReader struct {
	Client GmailClient
}

func (*GmailReader) Name() string        { return "gmail_reader" }
func (*GmailReader) DisplayName() string { return "Gmail Reader" }

func (*GmailReader) Description() string {
	return "Search and read emails from Gmail. Use this to find recent emails, " +
		"search by sender, subject, or date. Returns a list with id, date, " +
		"sender, subject, and labels. To read a full thread, call again with " +
		"action='thread' and the thread_id from a prior search."
}

func (*GmailReader) Parameters() interfaces.JSONSchema {
	return sdktools.Params(
		map[string]interfaces.JSONSchema{
			"action": sdktools.ParamEnum(
				"'search' to find emails, 'thread' to read a full thread.",
				"search", "thread",
			),
			"query": sdktools.ParamString(
				"Gmail search query (e.g. 'newer_than:2h', 'from:boss@company.com', " +
					"'is:unread subject:urgent'). Defaults to '" + defaultQuery + "'.",
			),
			"thread_id":   sdktools.ParamString("Thread ID (required when action='thread')."),
			"max_results": sdktools.ParamInteger(fmt.Sprintf("Max emails to return (default %d, max 100).", defaultMaxResults)),
		},
		"action",
	)
}

func (t *GmailReader) Execute(ctx context.Context, args map[string]any) (any, error) {
	switch action := stringArg(args, "action"); action {
	case "search":
		return t.search(ctx, args)
	case "thread":
		return t.thread(ctx, args)
	default:
		return nil, fmt.Errorf("unknown action %q (expected 'search' or 'thread')", action)
	}
}

func (t *GmailReader) search(ctx context.Context, args map[string]any) (any, error) {
	query := stringArg(args, "query")
	if query == "" {
		query = defaultQuery
	}
	maxResults := intArg(args, "max_results", defaultMaxResults)
	if maxResults < 1 {
		maxResults = 1
	}
	if maxResults > 100 {
		maxResults = 100
	}
	emails, err := t.Client.Search(ctx, query, maxResults)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"query":       query,
		"total_count": len(emails),
		"emails":      emails,
	}, nil
}

func (t *GmailReader) thread(ctx context.Context, args map[string]any) (any, error) {
	threadID := stringArg(args, "thread_id")
	if threadID == "" {
		return nil, fmt.Errorf("thread_id is required for action='thread'")
	}
	content, err := t.Client.Thread(ctx, threadID)
	if err != nil {
		return nil, err
	}
	return map[string]any{"thread_id": threadID, "content": content}, nil
}

// stringArg reads a trimmed string argument, "" when absent or wrong type.
func stringArg(args map[string]any, key string) string {
	s, _ := args[key].(string)
	return strings.TrimSpace(s)
}

// intArg reads an integer argument; JSON decoding delivers numbers as float64.
func intArg(args map[string]any, key string, fallback int) int {
	switch v := args[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	case int64:
		return int(v)
	default:
		return fallback
	}
}
