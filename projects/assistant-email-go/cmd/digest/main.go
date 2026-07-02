// Command digest runs one email-assistant pass: the deterministic pipeline
// (classify → memory diff → render) alongside the SDK agent's LLM narrative.
// It reuses the same digestwf activities the Temporal worker runs, so
// one-shot and scheduled modes share one code path — including metrics
// (ADR-008) when OTEL_EXPORTER_OTLP_ENDPOINT is set.
//
// Exit codes: 0 ok / quiet hours, 1 unexpected, 2 config, 3 gmail, 4 LLM or agent.
package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/digestwf"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/gmail"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/obs"
)

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

	tel, err := obs.New(cfg, "email-assistant-digest")
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: observability:", err)
		return 1
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = tel.Shutdown(ctx)
	}()

	acts := digestwf.NewActivities(cfg, tel)
	ctx := context.Background()

	report, err := acts.RunDigestPipeline(ctx, digestwf.Input{})
	if err != nil {
		var cliErr *gmail.CLIError
		if errors.As(err, &cliErr) {
			fmt.Fprintln(os.Stderr, "ERROR: gmail:", err)
			return 3
		}
		fmt.Fprintln(os.Stderr, "ERROR:", err)
		return 1
	}

	narrative, err := acts.RunAgentNarrative(ctx)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: agent run:", err)
		return 4
	}

	printReport(narrative, report)
	return 0
}

func printReport(nr digestwf.NarrativeReport, report digestwf.PipelineReport) {
	bar := strings.Repeat("=", 60)
	fmt.Printf("\n%s\nDETERMINISTIC DIGEST\n%s\n", bar, bar)
	fmt.Print(report.Rendered)
	fmt.Printf("%s\nLLM NARRATIVE\n%s\n", bar, bar)
	fmt.Println(nr.Narrative)
	fmt.Println(bar)
	fmt.Printf("tokens=%d (in=%d out=%d) new_urgent=%v\n",
		nr.InputTokens+nr.OutputTokens, nr.InputTokens, nr.OutputTokens, report.NewUrgent)
}
