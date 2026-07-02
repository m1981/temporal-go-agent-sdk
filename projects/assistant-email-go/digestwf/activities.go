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
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/obs"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/pipeline"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/prompt"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/tools"
)

// Activities holds worker-scoped dependencies. Settings is loaded once at
// worker start; Gmail is injectable for tests (nil ⇒ real gmcli client).
type Activities struct {
	Settings  *config.Settings
	Gmail     tools.GmailClient
	Telemetry *obs.Telemetry
}

// NewActivities builds the production activity set.
func NewActivities(cfg *config.Settings, tel *obs.Telemetry) *Activities {
	return &Activities{Settings: cfg, Telemetry: tel}
}

func (a *Activities) telemetry() *obs.Telemetry {
	if a.Telemetry != nil {
		return a.Telemetry
	}
	return obs.Noop()
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
	quiet := a.Settings.QuietHours.Contains(time.Now())
	if quiet {
		a.telemetry().RecordQuietSkip(ctx)
	}
	return quiet, nil
}

// RunDigestPipeline executes the deterministic pass: fetch → classify →
// memory diff → render → persist.
func (a *Activities) RunDigestPipeline(ctx context.Context, in Input) (report PipelineReport, err error) {
	in = in.WithDefaults()
	start := time.Now()
	defer func() { a.telemetry().RecordStage(ctx, obs.StagePipeline, start, err) }()

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

	report = PipelineReport{
		Rendered:     res.Rendered,
		Total:        res.Summary.Total,
		UrgentCount:  res.Summary.UrgentCount(),
		NewUrgent:    res.HasNewUrgent(),
		NewThreadIDs: ids,
	}
	a.telemetry().RecordDigest(ctx, report.Total, report.UrgentCount, report.NewUrgent)
	return report, nil
}

// RunAgentNarrative runs the SDK agent in-process and returns its prose
// summary plus token usage. The agent's own iteration and token budgets
// (ADR-004) bound the call; Temporal's activity timeout is the outer hard stop.
func (a *Activities) RunAgentNarrative(ctx context.Context) (rep NarrativeReport, err error) {
	tel := a.telemetry()
	start := time.Now()
	defer func() { tel.RecordStage(ctx, obs.StageAgent, start, err) }()

	llmClient, err := anthropic.NewClient(
		llm.WithAPIKey(a.Settings.AnthropicAPIKey),
		llm.WithModel(a.Settings.Model),
	)
	if err != nil {
		return NarrativeReport{}, fmt.Errorf("llm client: %w", err)
	}

	gm := a.gmailClient()
	reg := agent.NewToolRegistry()
	if err := agent.RegisterTools(reg,
		&tools.GmailReader{Client: gm},
		&tools.GmailSender{Client: gm},
	); err != nil {
		return NarrativeReport{}, fmt.Errorf("register tools: %w", err)
	}

	opts := []agent.Option{
		agent.WithName("email-assistant"),
		agent.WithDescription("Gmail digest assistant"),
		agent.WithSystemPrompt(prompt.System(a.Settings.UserEmail)),
		agent.WithLLMClient(llmClient),
		agent.WithToolRegistry(reg),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()),
		agent.WithMaxIterations(a.Settings.MaxIterations),
		agent.WithMaxTokens(a.Settings.TokenBudget),
		agent.WithLogLevel(a.Settings.LogLevel),
		agent.WithMetrics(tel.Metrics),
		agent.WithTracer(tel.Tracer),
	}
	// One-shot mode may additionally run the agent loop on the SDK's
	// Temporal runtime (AGENT_RUNTIME=temporal). Inside a worker this
	// stays unset — the activity already runs under Temporal.
	if a.Settings.UseTemporal() {
		opts = append(opts, agent.WithTemporalConfig(&agent.TemporalConfig{
			Host:      a.Settings.TemporalHost,
			Port:      a.Settings.TemporalPort,
			Namespace: a.Settings.TemporalNamespace,
			TaskQueue: a.Settings.TemporalTaskQueue,
		}))
	}
	ag, err := agent.NewAgent(opts...)
	if err != nil {
		return NarrativeReport{}, fmt.Errorf("create agent: %w", err)
	}
	defer ag.Close()

	result, err := ag.Run(ctx, prompt.DefaultUserQuery, nil)
	if err != nil {
		return NarrativeReport{}, fmt.Errorf("agent run: %w", err)
	}

	rep = NarrativeReport{Narrative: result.Content}
	if u := result.LLMUsage; u != nil {
		rep.InputTokens, rep.OutputTokens = u.PromptTokens, u.CompletionTokens
		tel.RecordTokens(ctx, u.PromptTokens, u.CompletionTokens)
	}
	return rep, nil
}
