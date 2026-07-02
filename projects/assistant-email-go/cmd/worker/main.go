// Command worker hosts the Temporal worker for the email digest: it
// registers DigestWorkflow and its activities and blocks until interrupted.
//
// When OTEL_EXPORTER_OTLP_ENDPOINT is set (ADR-008), workflow/activity
// execution is traced via the Temporal OTel interceptor and digest metrics
// are exported through the SDK's observability package.
//
// Exit codes: 0 clean shutdown, 1 worker/client failure, 2 config error.
package main

import (
	"context"
	"fmt"
	"os"
	"time"

	"go.temporal.io/sdk/client"
	temporalotel "go.temporal.io/sdk/contrib/opentelemetry"
	"go.temporal.io/sdk/interceptor"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/digestwf"
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

	tel, err := obs.New(cfg, "email-assistant-worker")
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: observability:", err)
		return 1
	}
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = tel.Shutdown(ctx)
	}()

	c, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalAddress(),
		Namespace: cfg.TemporalNamespace,
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: temporal dial:", err)
		return 1
	}
	defer c.Close()

	workerOpts := worker.Options{}
	if ot, ok := tel.Tracer.(interfaces.OTelTracer); ok && tel.Active {
		ti, err := temporalotel.NewTracingInterceptor(temporalotel.TracerOptions{
			Tracer: ot.OTelTracer(),
		})
		if err != nil {
			fmt.Fprintln(os.Stderr, "ERROR: tracing interceptor:", err)
			return 1
		}
		workerOpts.Interceptors = []interceptor.WorkerInterceptor{ti}
	}

	w := worker.New(c, cfg.TemporalTaskQueue, workerOpts)
	w.RegisterWorkflowWithOptions(digestwf.DigestWorkflow, workflow.RegisterOptions{
		Name: digestwf.WorkflowName,
	})
	w.RegisterActivity(digestwf.NewActivities(cfg, tel))

	fmt.Printf("email-digest worker: queue=%s temporal=%s telemetry=%v\n",
		cfg.TemporalTaskQueue, cfg.TemporalAddress(), tel.Active)
	if err := w.Run(worker.InterruptCh()); err != nil {
		fmt.Fprintln(os.Stderr, "ERROR: worker:", err)
		return 1
	}
	return 0
}
