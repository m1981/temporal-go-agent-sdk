// Package obs wires the SDK's OTel observability (pkg/observability) into
// the email assistant (ADR-008).
//
// Telemetry is off by default: with no OTEL_EXPORTER_OTLP_ENDPOINT configured
// every recorder is a no-op, so cmd/digest and the worker run identically
// with or without a collector. Metric names live here — one place for code
// and dashboards to agree on.
package obs

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/m1981/temporal-go-agent-sdk/pkg/observability"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
)

// Metric catalog. Per-run quantities are histograms because the SDK's
// Metrics interface exposes increment-by-one counters only; histograms also
// give percentiles for free.
const (
	MetricStageTotal      = "email_digest.stage_total"            // counter; attrs: stage, status
	MetricStageDuration   = "email_digest.stage_duration_seconds" // histogram; attrs: stage
	MetricEmailsPerRun    = "email_digest.emails_per_run"         // histogram
	MetricUrgentPerRun    = "email_digest.urgent_per_run"         // histogram
	MetricNewUrgentRuns   = "email_digest.new_urgent_runs_total"  // counter
	MetricQuietSkips      = "email_digest.quiet_skips_total"      // counter
	MetricLLMTokensPerRun = "email_digest.llm_tokens_per_run"     // histogram; attrs: direction
)

// Stage attribute values for MetricStageTotal / MetricStageDuration.
const (
	StagePipeline = "pipeline"
	StageAgent    = "agent"
)

// Telemetry bundles the metrics and tracer handles used across the app.
// Active is false when telemetry export is disabled (no-op implementations).
type Telemetry struct {
	Metrics interfaces.Metrics
	Tracer  interfaces.Tracer
	Active  bool
}

// Noop returns telemetry whose every recorder does nothing.
func Noop() *Telemetry {
	return &Telemetry{Metrics: &observability.NoopMetrics{}, Tracer: &observability.NoopTracer{}}
}

// New builds OTLP-backed telemetry from settings; when Settings.OTLPEndpoint
// is empty it returns Noop() so callers never branch on configuration.
func New(cfg *config.Settings, service string) (*Telemetry, error) {
	if cfg.OTLPEndpoint == "" {
		return Noop(), nil
	}
	proto := observability.ProtocolGRPC
	if cfg.OTLPProtocol == "http" {
		proto = observability.ProtocolHTTP
	}
	opts := []observability.Option{
		observability.WithEndpoint(cfg.OTLPEndpoint),
		observability.WithName(service),
		observability.WithProtocol(proto),
		observability.WithInsecure(cfg.OTLPInsecure),
		observability.WithDeploymentEnvironment(cfg.Environment),
	}
	metrics, err := observability.NewMetrics(opts...)
	if err != nil {
		return nil, fmt.Errorf("obs: metrics: %w", err)
	}
	tracer, err := observability.NewTracer(opts...)
	if err != nil {
		_ = metrics.Shutdown(context.Background())
		return nil, fmt.Errorf("obs: tracer: %w", err)
	}
	return &Telemetry{Metrics: metrics, Tracer: tracer, Active: true}, nil
}

// Shutdown flushes both exporters; safe on no-op telemetry.
func (t *Telemetry) Shutdown(ctx context.Context) error {
	return errors.Join(t.Metrics.Shutdown(ctx), t.Tracer.Shutdown(ctx))
}

// Attr builds an interfaces.Attribute.
func Attr(key string, value any) interfaces.Attribute {
	return interfaces.Attribute{Key: key, Value: value}
}

// RecordStage records one stage execution: outcome counter + duration histogram.
func (t *Telemetry) RecordStage(ctx context.Context, stage string, start time.Time, err error) {
	status := "ok"
	if err != nil {
		status = "error"
	}
	t.Metrics.IncrementCounter(ctx, MetricStageTotal, Attr("stage", stage), Attr("status", status))
	t.Metrics.RecordHistogram(ctx, MetricStageDuration, time.Since(start).Seconds(), Attr("stage", stage))
}

// RecordDigest records the deterministic pipeline's per-run quantities.
func (t *Telemetry) RecordDigest(ctx context.Context, total, urgent int, newUrgent bool) {
	t.Metrics.RecordHistogram(ctx, MetricEmailsPerRun, float64(total))
	t.Metrics.RecordHistogram(ctx, MetricUrgentPerRun, float64(urgent))
	if newUrgent {
		t.Metrics.IncrementCounter(ctx, MetricNewUrgentRuns)
	}
}

// RecordTokens records LLM token usage for one narrative run.
func (t *Telemetry) RecordTokens(ctx context.Context, input, output int64) {
	t.Metrics.RecordHistogram(ctx, MetricLLMTokensPerRun, float64(input), Attr("direction", "input"))
	t.Metrics.RecordHistogram(ctx, MetricLLMTokensPerRun, float64(output), Attr("direction", "output"))
}

// RecordQuietSkip counts a run suppressed by the quiet-hours gate.
func (t *Telemetry) RecordQuietSkip(ctx context.Context) {
	t.Metrics.IncrementCounter(ctx, MetricQuietSkips)
}
