// Command schedule creates (or with -replace, recreates) the Temporal
// Schedule that triggers DigestWorkflow every DIGEST_INTERVAL (default 2h).
//
// Overlapping runs are skipped rather than queued: digest runs are
// idempotent thanks to thread memory, so a missed tick costs nothing.
//
// Exit codes: 0 ok, 1 schedule/client failure, 2 config error.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	enums "go.temporal.io/api/enums/v1"
	"go.temporal.io/sdk/client"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/digestwf"
)

func main() {
	os.Exit(run())
}

func run() int {
	replace := flag.Bool("replace", false, "delete an existing schedule and recreate it")
	flag.Parse()

	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR:", err)
		return 2
	}

	c, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalAddress(),
		Namespace: cfg.TemporalNamespace,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: temporal dial:", err)
		return 1
	}
	defer c.Close()

	ctx := context.Background()
	sc := c.ScheduleClient()
	handle := sc.GetHandle(ctx, digestwf.ScheduleID)

	if _, err := handle.Describe(ctx); err == nil {
		if !*replace {
			fmt.Fprintf(os.Stderr,
				"schedule %q already exists (rerun with -replace to recreate)\n", digestwf.ScheduleID)
			return 1
		}
		if err := handle.Delete(ctx); err != nil {
			fmt.Fprintln(os.Stderr, "ERROR: delete existing schedule:", err)
			return 1
		}
	}

	_, err = sc.Create(ctx, client.ScheduleOptions{
		ID: digestwf.ScheduleID,
		Spec: client.ScheduleSpec{
			Intervals: []client.ScheduleIntervalSpec{{Every: cfg.DigestInterval}},
		},
		Action: &client.ScheduleWorkflowAction{
			ID:        digestwf.ScheduleID + "-run",
			Workflow:  digestwf.WorkflowName,
			TaskQueue: cfg.TemporalTaskQueue,
			Args:      []any{digestwf.Input{}}, // workflow applies defaults
		},
		Overlap: enums.SCHEDULE_OVERLAP_POLICY_SKIP,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: create schedule:", err)
		return 1
	}

	fmt.Printf("schedule %q created: every %s on queue %s (overlap: skip)\n",
		digestwf.ScheduleID, cfg.DigestInterval, cfg.TemporalTaskQueue)
	return 0
}
