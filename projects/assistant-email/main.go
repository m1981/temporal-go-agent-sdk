package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email/tools"
	"github.com/m1981/temporal-go-agent-sdk/pkg/agent"
	"github.com/m1981/temporal-go-agent-sdk/pkg/llm"
	"github.com/m1981/temporal-go-agent-sdk/pkg/llm/anthropic"
)

func main() {
	// Get Anthropic API key from environment
	apiKey := os.Getenv("ANTHROPIC_API_KEY")
	if apiKey == "" {
		log.Fatal("ANTHROPIC_API_KEY environment variable is required")
	}

	// Get user email from environment or default
	userEmail := os.Getenv("USER_EMAIL")
	if userEmail == "" {
		userEmail = "m.nakiewicz@gmail.com"
	}

	// Create Anthropic LLM client
	llmClient, err := anthropic.NewClient(
		llm.WithAPIKey(apiKey),
		llm.WithModel("claude-haiku-4-5"),
	)
	if err != nil {
		log.Fatalf("Failed to create Anthropic client: %v", err)
	}

	// Create tools
	gmailReader := tools.NewGmailReaderTool(userEmail)
	gmailSender := tools.NewGmailSenderTool(userEmail)

	// Create agent
	a, err := agent.NewAgent(
		agent.WithName("email-assistant"),
		agent.WithLLMClient(llmClient),
		agent.WithTools(gmailReader, gmailSender),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()),
		agent.WithMaxTokens(50000),
		agent.WithMaxIterations(10),
		agent.WithSystemPrompt(getSystemPrompt(userEmail)),
	)
	if err != nil {
		log.Fatalf("Failed to create agent: %v", err)
	}
	defer a.Close()

	// Run the agent
	ctx := context.Background()
	query := `Please check my recent emails and provide a summary. 
Focus on:
1. Any urgent or important emails
2. Emails that need a response
3. Group similar emails together
4. Ignore newsletters and promotions unless they seem important`

	result, err := a.Run(ctx, query, nil)
	if err != nil {
		log.Fatalf("Agent run failed: %v", err)
	}

	// Print the result
	fmt.Println("\n" + strings.Repeat("=", 60))
	fmt.Println("EMAIL SUMMARY")
	fmt.Println(strings.Repeat("=", 60))
	fmt.Println(result.Content)
	fmt.Println(strings.Repeat("=", 60))
}

func getSystemPrompt(userEmail string) string {
	return fmt.Sprintf(`You are an email assistant for %s.

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
- User: %s
- Checking: Recent emails (last 24 hours)

Remember: Be concise. The user wants a quick overview, not a detailed analysis of every email.`, userEmail, userEmail)
}
