package tools

import (
	"context"
	"fmt"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	sdktools "github.com/m1981/temporal-go-agent-sdk/pkg/tools"
)

var _ interfaces.Tool = (*GmailSender)(nil)

// GmailSender sends an email (or a reply to a thread) via gmcli.
// Intentionally strict: to/subject/body are all required so a hallucinated
// call fails fast rather than sending garbage.
type GmailSender struct {
	Client GmailClient
}

func (*GmailSender) Name() string        { return "gmail_sender" }
func (*GmailSender) DisplayName() string { return "Gmail Sender" }

func (*GmailSender) Description() string {
	return "Send an email or reply to an existing thread. Only use this when " +
		"the user explicitly asks to send a message. Provide to, subject, and " +
		"body; add thread_id to reply within an existing thread."
}

func (*GmailSender) Parameters() interfaces.JSONSchema {
	return sdktools.Params(
		map[string]interfaces.JSONSchema{
			"to":        sdktools.ParamString("Recipient email address."),
			"subject":   sdktools.ParamString("Email subject line."),
			"body":      sdktools.ParamString("Plain-text email body."),
			"thread_id": sdktools.ParamString("Optional thread ID to reply within."),
		},
		"to", "subject", "body",
	)
}

func (t *GmailSender) Execute(ctx context.Context, args map[string]any) (any, error) {
	to := stringArg(args, "to")
	subject := stringArg(args, "subject")
	body := stringArg(args, "body")
	if to == "" || subject == "" || body == "" {
		return nil, fmt.Errorf("to, subject, and body are all required")
	}
	threadID := stringArg(args, "thread_id")

	out, err := t.Client.Send(ctx, to, subject, body, threadID)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"status":    "sent",
		"to":        to,
		"subject":   subject,
		"thread_id": threadID,
		"output":    out,
	}, nil
}
