package tools

import (
	"context"
	"fmt"
	"os/exec"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// GmailSenderTool sends emails using gmcli.
type GmailSenderTool struct {
	userEmail string
}

// NewGmailSenderTool creates a new GmailSenderTool.
func NewGmailSenderTool(userEmail string) *GmailSenderTool {
	return &GmailSenderTool{
		userEmail: userEmail,
	}
}

// Name returns the tool name.
func (t *GmailSenderTool) Name() string {
	return "gmail_sender"
}

// DisplayName returns the display name.
func (t *GmailSenderTool) DisplayName() string {
	return "Gmail Sender"
}

// Description returns the tool description.
func (t *GmailSenderTool) Description() string {
	return `Send an email using Gmail.
Use this tool ONLY when the user explicitly asks to send an email.
Always confirm the recipient, subject, and body before sending.`
}

// Parameters returns the tool parameters.
func (t *GmailSenderTool) Parameters() interfaces.JSONSchema {
	return interfaces.JSONSchema{
		"type": "object",
		"properties": map[string]any{
			"to": map[string]any{
				"type":        "string",
				"description": "Recipient email address(es), comma-separated",
			},
			"subject": map[string]any{
				"type":        "string",
				"description": "Email subject line",
			},
			"body": map[string]any{
				"type":        "string",
				"description": "Email body content",
			},
			"thread_id": map[string]any{
				"type":        "string",
				"description": "Thread ID to reply to (optional)",
			},
		},
		"required": []string{"to", "subject", "body"},
	}
}

// Execute runs the tool.
func (t *GmailSenderTool) Execute(ctx context.Context, args map[string]any) (any, error) {
	to, ok := args["to"].(string)
	if !ok || to == "" {
		return nil, fmt.Errorf("to parameter is required")
	}

	subject, ok := args["subject"].(string)
	if !ok || subject == "" {
		return nil, fmt.Errorf("subject parameter is required")
	}

	body, ok := args["body"].(string)
	if !ok || body == "" {
		return nil, fmt.Errorf("body parameter is required")
	}

	// Build gmcli command
	cmdArgs := []string{
		t.userEmail,
		"send",
		"--to", to,
		"--subject", subject,
		"--body", body,
	}

	// Add thread_id if provided (for replies)
	threadID, _ := args["thread_id"].(string)
	if threadID != "" {
		cmdArgs = append(cmdArgs, "--thread", threadID)
	}

	// Execute gmcli send
	cmd := exec.CommandContext(ctx, "gmcli", cmdArgs...)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("gmcli send failed: %v\nOutput: %s", err, string(output))
	}

	return map[string]any{
		"success":  true,
		"to":       to,
		"subject":  subject,
		"message":  "Email sent successfully",
		"output":   string(output),
	}, nil
}
