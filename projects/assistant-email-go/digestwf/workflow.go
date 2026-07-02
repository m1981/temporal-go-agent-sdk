// Package digestwf is the Temporal workflow for the scheduled email digest
// (ADR-007). The workflow is pure orchestration — deterministic and
// replay-safe; all I/O (config, gmcli, SQLite, the LLM agent) lives in
// Activities so Temporal owns retries, timeouts, and visibility per step.
package digestwf

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

const (
	// WorkflowName is the registered workflow type; the Schedule targets it.
	WorkflowName = "EmailDigestWorkflow"
	// ScheduleID identifies the recurring digest schedule on the server.
	ScheduleID = "email-digest"

	defaultQuery      = "newer_than:2h"
	defaultMaxResults = 50
)

// Input parameterizes one digest run. Zero values select the defaults above.
type Input struct {
	Query      string
	MaxResults int
}

// PipelineReport is the serializable outcome of the deterministic pipeline.
type PipelineReport struct {
	Rendered     string
	Total        int
	UrgentCount  int
	NewUrgent    bool
	NewThreadIDs []string
}

// Outcome is the workflow result recorded in Temporal history.
type Outcome struct {
	Skipped   bool // true when quiet hours suppressed the run
	Pipeline  PipelineReport
	Narrative string // the LLM's prose summary
}

// DigestWorkflow runs one digest pass: quiet-hours gate → deterministic
// pipeline → LLM narrative.
func DigestWorkflow(ctx workflow.Context, in Input) (*Outcome, error) {
	if in.Query == "" {
		in.Query = defaultQuery
	}
	if in.MaxResults <= 0 {
		in.MaxResults = defaultMaxResults
	}

	var a *Activities // name-based activity references; never invoked directly

	gateCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	var quiet bool
	if err := workflow.ExecuteActivity(gateCtx, a.InQuietHours).Get(gateCtx, &quiet); err != nil {
		return nil, err
	}
	if quiet {
		workflow.GetLogger(ctx).Info("quiet hours: skipping digest run")
		return &Outcome{Skipped: true}, nil
	}

	pipeCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 2 * time.Minute,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	})
	var report PipelineReport
	if err := workflow.ExecuteActivity(pipeCtx, a.RunDigestPipeline, in).Get(pipeCtx, &report); err != nil {
		return nil, err
	}

	agentCtx := workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 2},
	})
	var narrative string
	if err := workflow.ExecuteActivity(agentCtx, a.RunAgentNarrative).Get(agentCtx, &narrative); err != nil {
		return nil, err
	}

	return &Outcome{Pipeline: report, Narrative: narrative}, nil
}
