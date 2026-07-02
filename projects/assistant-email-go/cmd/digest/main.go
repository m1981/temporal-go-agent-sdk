// Command digest runs one email-assistant pass: the deterministic pipeline
// (classify → memory diff → render) alongside the SDK agent's LLM narrative.
//
// Exit codes: 0 ok / quiet hours, 1 unexpected, 2 config, 3 gmail, 4 LLM or agent.
//
// Set AGENT_RUNTIME=temporal (plus TEMPORAL_HOST/PORT/NAMESPACE/TASK_QUEUE)
// to run the agent durably on Temporal; the default is in-process. Scheduling
// the 2-hourly digest is then a Temporal Schedule (or cron) invoking this
// binary — it is idempotent thanks to thread memory.
package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/pkg/agent"
	"github.com/m1981/temporal-go-agent-sdk/pkg/llm"
	"github.com/m1981/temporal-go-agent-sdk/pkg/llm/anthropic"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/classify"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/gmail"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/memory"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/notify"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/pipeline"
	emailtools "github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/tools"
)

const defaultUserQuery = `Please check my recent emails and provide a summary.
Focus on:
1. Any urgent or important emails
2. Emails that need a response
3. Group similar emails together
4. Ignore newsletters and promotions unless they seem important`

const systemPromptTemplate = `You are an email assistant for %[1]s.

## Your Role
- Check and summarize emails
- Identify urgent/important messages
- Group similar emails together
- Provide actionable insights

## Email Priority Rules
1. URGENT: Boss emails, family emergencies, time-sensitive work deadlines
2. IMPORTANT: Client emails, meeting requests, invoices, action items
3. LOW: Newsletters, promotions, social media notifications

## How to Respond
- Start with a brief overview (X new emails, Y urgent, Z important)
- List urgent items first with clear action needed
- Group similar emails (e.g., "3 newsletters from tech blogs")
- End with recommended actions

## Tools Available
- gmail_reader: Search and read emails
- gmail_sender: Send emails (only if user explicitly asks)

## Current Context
- User: %[1]s
- Checking: Recent emails

Be concise. The user wants a quick overview, not a detailed analysis of every email.`

func main() {
	os.Exit(run())
}

func run() int {
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR:", err)
		return 2
	}

	// Phase 5 quiet-hours guard: scheduled runs stay silent at night.
	if cfg.QuietHours.Contains(time.Now()) && os.Getenv("FORCE_RUN") != "1" {
		fmt.Printf("quiet hours (%02d-%02d): skipping run (set FORCE_RUN=1 to override)\n",
			cfg.QuietHours.Start, cfg.QuietHours.End)
		return 0
	}

	llmClient, err := anthropic.NewClient(
		llm.WithAPIKey(cfg.AnthropicAPIKey),
		llm.WithModel(cfg.Model),
	)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: llm client:", err)
		return 4
	}

	gm := gmail.NewClient(cfg.UserEmail)

	reg := agent.NewToolRegistry()
	if err := agent.RegisterTools(reg,
		&emailtools.GmailReader{Client: gm},
		&emailtools.GmailSender{Client: gm},
	); err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: register tools:", err)
		return 1
	}

	opts := []agent.Option{
		agent.WithName("email-assistant"),
		agent.WithDescription("Gmail digest assistant (Go port of projects/assistant-email)"),
		agent.WithSystemPrompt(fmt.Sprintf(systemPromptTemplate, cfg.UserEmail)),
		agent.WithLLMClient(llmClient),
		agent.WithToolRegistry(reg),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()),
		agent.WithMaxIterations(cfg.MaxIterations),
		agent.WithMaxTokens(cfg.TokenBudget),
		agent.WithLogLevel(cfg.LogLevel),
	}
	if cfg.UseTemporal() {
		opts = append(opts, agent.WithTemporalConfig(&agent.TemporalConfig{
			Host:      cfg.TemporalHost,
			Port:      cfg.TemporalPort,
			Namespace: cfg.TemporalNamespace,
			TaskQueue: cfg.TemporalTaskQueue,
		}))
	}
	a, err := agent.NewAgent(opts...)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: create agent:", err)
		return 4
	}
	defer a.Close()

	store, err := memory.Open(cfg.MemoryPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: thread store:", err)
		return 1
	}
	defer store.Close()

	dig := pipeline.Digest{
		Gmail:      gm,
		Classifier: classify.UrgencyClassifier{Rules: cfg.Rules},
		Formatter:  notify.Formatter{},
		Memory:     store,
	}

	ctx := context.Background()
	digest, err := dig.Run(ctx, "newer_than:2h", 50)
	if err != nil {
		var cliErr *gmail.CLIError
		if errors.As(err, &cliErr) {
			fmt.Fprintln(os.Stderr, "ERROR: gmail:", err)
			return 3
		}
		fmt.Fprintln(os.Stderr, "ERROR:", err)
		return 1
	}

	result, err := a.Run(ctx, defaultUserQuery, nil)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: agent run:", err)
		return 4
	}

	printReport(result, digest)
	return 0
}

func printReport(result *agent.AgentRunResult, digest pipeline.Result) {
	bar := strings.Repeat("=", 60)
	fmt.Printf("\n%s\nDETERMINISTIC DIGEST\n%s\n", bar, bar)
	fmt.Print(digest.Rendered)
	fmt.Printf("%s\nLLM NARRATIVE\n%s\n", bar, bar)
	fmt.Println(result.Content)
	fmt.Println(bar)
	tokens := ""
	if u := result.LLMUsage; u != nil {
		tokens = fmt.Sprintf("tokens=%d (in=%d out=%d) ", u.TotalTokens, u.PromptTokens, u.CompletionTokens)
	}
	fmt.Printf("%snew_urgent=%v\n", tokens, digest.HasNewUrgent())
}
