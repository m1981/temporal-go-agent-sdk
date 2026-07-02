// Package gmail wraps the gmcli binary (ADR-001).
//
// Every piece of process I/O in the project lives here. The agent, the
// tools, and the tests operate on parsed domain.Email values without ever
// touching the shell — swapping gmcli for the Gmail REST API means
// rewriting only this file.
package gmail

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

// gmcli tabular output: id \t date \t from \t subject \t labels.
const searchColumns = 5

// DefaultTimeout is the hard wall-clock limit applied to every invocation.
const DefaultTimeout = 30 * time.Second

// CLIError reports gmcli exiting non-zero, missing, or timing out.
// Callers can match it with errors.As to catch "anything Gmail-shaped".
type CLIError struct {
	Message string
}

func (e *CLIError) Error() string { return e.Message }

func cliErrorf(format string, a ...any) *CLIError {
	return &CLIError{Message: fmt.Sprintf(format, a...)}
}

// Runner executes a command and returns its stdout. Injectable for tests.
type Runner func(ctx context.Context, name string, args ...string) (string, error)

// Client invokes gmcli for a single Gmail account previously registered via
// `gmcli accounts add`. Zero values for Binary, Timeout, and Runner select
// sensible defaults.
type Client struct {
	UserEmail string
	Binary    string        // default "gmcli"
	Timeout   time.Duration // default DefaultTimeout
	Runner    Runner        // default: real subprocess execution
}

// NewClient returns a Client bound to one Gmail account.
func NewClient(userEmail string) *Client {
	return &Client{UserEmail: userEmail}
}

// Search returns recent emails matching a Gmail query (`newer_than:2h`,
// `from:boss@company.com`, ...), truncated to maxResults.
func (c *Client) Search(ctx context.Context, query string, maxResults int) ([]domain.Email, error) {
	raw, err := c.run(ctx, "search", query, "--max", strconv.Itoa(maxResults))
	if err != nil {
		return nil, err
	}
	return parseSearch(raw), nil
}

// Thread returns the raw thread content (all messages, headers, and body).
func (c *Client) Thread(ctx context.Context, threadID string) (string, error) {
	if threadID == "" {
		return "", cliErrorf("thread_id must be non-empty")
	}
	return c.run(ctx, "thread", threadID)
}

// Send sends a message (or a reply when threadID is set) and returns gmcli's output.
func (c *Client) Send(ctx context.Context, to, subject, body, threadID string) (string, error) {
	args := []string{"send", "--to", to, "--subject", subject, "--body", body}
	if threadID != "" {
		args = append(args, "--thread", threadID)
	}
	return c.run(ctx, args...)
}

func (c *Client) run(ctx context.Context, args ...string) (string, error) {
	binary := c.Binary
	if binary == "" {
		binary = "gmcli"
	}
	timeout := c.Timeout
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	runner := c.Runner
	if runner == nil {
		runner = execRunner
	}

	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	full := append([]string{c.UserEmail}, args...)
	out, err := runner(ctx, binary, full...)
	if err != nil {
		return "", cliErrorf("gmcli %s failed: %v", args[0], err)
	}
	return out, nil
}

// execRunner is the only place a real subprocess is spawned.
func execRunner(ctx context.Context, name string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		if ctx.Err() != nil {
			return "", fmt.Errorf("timed out: %w", ctx.Err())
		}
		detail := strings.TrimSpace(stderr.String())
		if detail == "" {
			detail = strings.TrimSpace(stdout.String())
		}
		return "", fmt.Errorf("%w: %s", err, detail)
	}
	return stdout.String(), nil
}

// parseSearch yields Email records from tab-separated gmcli output, skipping
// the header row, blank lines, pagination footers ("# Next page: ..."), and
// malformed rows.
func parseSearch(raw string) []domain.Email {
	lines := strings.Split(strings.TrimSpace(raw), "\n")
	if len(lines) <= 1 {
		return nil
	}
	var emails []domain.Email
	for _, line := range lines[1:] {
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "\t", searchColumns)
		if len(parts) < searchColumns {
			continue
		}
		emails = append(emails, domain.Email{
			ID:      strings.TrimSpace(parts[0]),
			Date:    strings.TrimSpace(parts[1]),
			Sender:  strings.TrimSpace(parts[2]),
			Subject: strings.TrimSpace(parts[3]),
			Labels:  strings.TrimSpace(parts[4]),
		})
	}
	return emails
}
