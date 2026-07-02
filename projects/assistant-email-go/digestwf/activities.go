package digestwf

import (
	"context"
	"fmt"
	"sort"
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
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/prompt"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/tools"
)

// Activities holds worker-scoped dependencies. Settings is loaded once at
// worker start; Gmail is injectable for tests (nil ⇒ real gmcli client).
type Activities struct {
	Settings *config.Settings
	Gmail    tools.GmailClient
}

// NewActivities builds the production activity set.
func NewActivities(cfg *config.Settings) *Activities {
	return &Activities{Settings: cfg}
}

func (a *Activities) gmailClient() tools.GmailClient {
	if a.Gmail != nil {
		return a.Gmail
	}
	return gmail.NewClient(a.Settings.UserEmail)
}

// InQuietHours reports whether the current wall-clock time falls inside the
// configured quiet window. Kept as an activity so the check is visible in
// workflow history and the workflow itself stays deterministic.
func (a *Activities) InQuietHours(ctx context.Context) (bool, error) {
	return a.Settings.QuietHours.Contains(time.Now()), nil
}

// RunDigestPipeline executes the deterministic pass: fetch → classify →
// memory diff → render → persist.
func (a *Activities) RunDigestPipeline(ctx context.Context, in Input) (PipelineReport, error) {
	store, err := memory.Open(a.Settings.MemoryPath)
	if err != nil {
		return PipelineReport{}, fmt.Errorf("open thread store: %w", err)
	}
	defer store.Close()

	dig := pipeline.Digest{
		Gmail:      a.gmailClient(),
		Classifier: classify.UrgencyClassifier{Rules: a.Settings.Rules},
		Formatter:  notify.Formatter{},
		Memory:     store,
	}
	res, err := dig.Run(ctx, in.Query, in.MaxResults)
	if err != nil {
		return PipelineReport{}, err
	}

	ids := make([]string, 0, len(res.NewThreadIDs))
	for id := range res.NewThreadIDs {
		ids = append(ids, id)
	}
	sort.Strings(ids)

	return PipelineReport{
		Rendered:     res.Rendered,
		Total:        res.Summary.Total,
		UrgentCount:  res.Summary.UrgentCount(),
		NewUrgent:    res.HasNewUrgent(),
		NewThreadIDs: ids,
	}, nil
}

// RunAgentNarrative runs the SDK agent in-process and returns its prose
// summary. The agent's own iteration and token budgets (ADR-004) bound the
// call; Temporal's activity timeout is the outer hard stop.
func (a *Activities) RunAgentNarrative(ctx context.Context) (string, error) {
	llmClient, err := anthropic.NewClient(
		llm.WithAPIKey(a.Settings.AnthropicAPIKey),
		llm.WithModel(a.Settings.Model),
	)
	if err != nil {
		return "", fmt.Errorf("llm client: %w", err)
	}

	gm := a.gmailClient()
	reg := agent.NewToolRegistry()
	if err := agent.RegisterTools(reg,
		&tools.GmailReader{Client: gm},
		&tools.GmailSender{Client: gm},
	); err != nil {
		return "", fmt.Errorf("register tools: %w", err)
	}

	ag, err := agent.NewAgent(
		agent.WithName("email-assistant"),
		agent.WithDescription("Gmail digest assistant (Temporal activity run)"),
		agent.WithSystemPrompt(prompt.System(a.Settings.UserEmail)),
		agent.WithLLMClient(llmClient),
		agent.WithToolRegistry(reg),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()),
		agent.WithMaxIterations(a.Settings.MaxIterations),
		agent.WithMaxTokens(a.Settings.TokenBudget),
		agent.WithLogLevel(a.Settings.LogLevel),
	)
	if err != nil {
		return "", fmt.Errorf("create agent: %w", err)
	}
	defer ag.Close()

	result, err := ag.Run(ctx, prompt.DefaultUserQuery, nil)
	if err != nil {
		return "", fmt.Errorf("agent run: %w", err)
	}
	return result.Content, nil
}
