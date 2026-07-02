package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// GmailReaderTool reads emails using gmcli.
type GmailReaderTool struct {
	userEmail string
}

// NewGmailReaderTool creates a new GmailReaderTool.
func NewGmailReaderTool(userEmail string) *GmailReaderTool {
	return &GmailReaderTool{
		userEmail: userEmail,
	}
}

// Name returns the tool name.
func (t *GmailReaderTool) Name() string {
	return "gmail_reader"
}

// DisplayName returns the display name.
func (t *GmailReaderTool) DisplayName() string {
	return "Gmail Reader"
}

// Description returns the tool description.
func (t *GmailReaderTool) Description() string {
	return `Search and read emails from Gmail. 
Use this tool to find recent emails, search by sender, subject, or date.
Returns a list of emails with their ID, date, sender, subject, and labels.
To read a full email thread, use the thread_id parameter.`
}

// Parameters returns the tool parameters.
func (t *GmailReaderTool) Parameters() interfaces.JSONSchema {
	return interfaces.JSONSchema{
		"type": "object",
		"properties": map[string]any{
			"action": map[string]any{
				"type":        "string",
				"description": "Action to perform: 'search' to find emails, 'thread' to read a full thread",
				"enum":        []string{"search", "thread"},
			},
			"query": map[string]any{
				"type":        "string",
				"description": "Gmail search query (e.g., 'newer_than:1d', 'from:boss@company.com', 'subject:urgent')",
			},
			"thread_id": map[string]any{
				"type":        "string",
				"description": "Thread ID to read (required when action='thread')",
			},
			"max_results": map[string]any{
				"type":        "integer",
				"description": "Maximum number of emails to return (default: 20)",
			},
		},
		"required": []string{"action"},
	}
}

// Execute runs the tool.
func (t *GmailReaderTool) Execute(ctx context.Context, args map[string]any) (any, error) {
	action, ok := args["action"].(string)
	if !ok {
		return nil, fmt.Errorf("action parameter is required")
	}

	switch action {
	case "search":
		return t.searchEmails(ctx, args)
	case "thread":
		return t.readThread(ctx, args)
	default:
		return nil, fmt.Errorf("unknown action: %s", action)
	}
}

// searchEmails searches for emails using gmcli.
func (t *GmailReaderTool) searchEmails(ctx context.Context, args map[string]any) (any, error) {
	query, _ := args["query"].(string)
	if query == "" {
		query = "newer_than:1d"
	}

	maxResults, _ := args["max_results"].(float64)
	if maxResults == 0 {
		maxResults = 20
	}

	// Execute gmcli search
	cmd := exec.CommandContext(ctx, "gmcli", t.userEmail, "search", query)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("gmcli search failed: %v\nOutput: %s", err, string(output))
	}

	// Parse the output
	emails := parseSearchOutput(string(output))

	// Limit results
	if len(emails) > int(maxResults) {
		emails = emails[:int(maxResults)]
	}

	return map[string]any{
		"emails":      emails,
		"total_count": len(emails),
		"query":       query,
	}, nil
}

// readThread reads a full email thread using gmcli.
func (t *GmailReaderTool) readThread(ctx context.Context, args map[string]any) (any, error) {
	threadID, ok := args["thread_id"].(string)
	if !ok || threadID == "" {
		return nil, fmt.Errorf("thread_id parameter is required for thread action")
	}

	// Execute gmcli thread
	cmd := exec.CommandContext(ctx, "gmcli", t.userEmail, "thread", threadID)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("gmcli thread failed: %v\nOutput: %s", err, string(output))
	}

	return map[string]any{
		"thread_id": threadID,
		"content":   string(output),
	}, nil
}

// Email represents a parsed email.
type Email struct {
	ID      string `json:"id"`
	Date    string `json:"date"`
	From    string `json:"from"`
	Subject string `json:"subject"`
	Labels  string `json:"labels"`
}

// parseSearchOutput parses the gmcli search output into Email structs.
func parseSearchOutput(output string) []Email {
	lines := strings.Split(strings.TrimSpace(output), "\n")
	if len(lines) <= 1 {
		return nil
	}

	// Skip header line
	var emails []Email
	for _, line := range lines[1:] {
		if strings.HasPrefix(line, "# Next page:") {
			continue
		}

		parts := strings.SplitN(line, "\t", 5)
		if len(parts) < 5 {
			continue
		}

		emails = append(emails, Email{
			ID:      strings.TrimSpace(parts[0]),
			Date:    strings.TrimSpace(parts[1]),
			From:    strings.TrimSpace(parts[2]),
			Subject: strings.TrimSpace(parts[3]),
			Labels:  strings.TrimSpace(parts[4]),
		})
	}

	return emails
}

// ToJSON converts the tool result to JSON.
func ToJSON(v any) string {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return fmt.Sprintf("error marshaling: %v", err)
	}
	return string(b)
}
