// Command worker hosts the Temporal worker for the email digest: it
// registers DigestWorkflow and its activities and blocks until interrupted.
//
// Exit codes: 0 clean shutdown, 1 worker/client failure, 2 config error.
package main

import (
	"fmt"
	"os"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/digestwf"
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

	c, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalAddress(),
		Namespace: cfg.TemporalNamespace,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: temporal dial:", err)
		return 1
	}
	defer c.Close()

	w := worker.New(c, cfg.TemporalTaskQueue, worker.Options{})
	w.RegisterWorkflowWithOptions(digestwf.DigestWorkflow, workflow.RegisterOptions{
		Name: digestwf.WorkflowName,
	})
	w.RegisterActivity(digestwf.NewActivities(cfg))

	fmt.Printf("email-digest worker: queue=%s temporal=%s\n",
		cfg.TemporalTaskQueue, cfg.TemporalAddress())
	if err := w.Run(worker.InterruptCh()); err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: worker:", err)
		return 1
	}
	return 0
}
