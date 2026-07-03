# ADR-008: OpenTelemetry Observability via the SDK

## Status

**Accepted** - 2026-07-02

## Context

ADR-007 made runs durable and *individually* inspectable in the Temporal
UI. What remains invisible is everything across runs: urgent-email volume,
LLM token spend, gmcli/LLM latency, failure rates over weeks of scheduled
executions. The Python plan deferred this ("wire to Prometheus"); the repo
already ships an OTel implementation (`pkg/observability`) that the email
assistant should dogfood rather than reinvent.

## Decision

Wire `pkg/observability` into the Go assistant behind a small `obs`
package that is a **no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set** —
zero configuration keeps zero overhead and no code branches on "is
telemetry on".

- **Metrics** are recorded inside the digestwf activities, so the one-shot
  `cmd/digest` (which now reuses the same activities) and the Temporal
  worker emit identical series. Catalog (single source: `obs` package):
  `stage_total{stage,status}`, `stage_duration_seconds{stage}`,
  `emails_per_run`, `urgent_per_run`, `new_urgent_runs_total`,
  `quiet_skips_total`, `llm_tokens_per_run{direction}`.
- **Per-run quantities are histograms**, because the SDK's `Metrics`
  interface exposes increment-by-one counters only — and histograms give
  percentiles for free.
- **Traces**: the worker installs Temporal's OTel tracing interceptor
  (workflow + activity spans), and the SDK agent receives
  `agent.WithTracer`/`WithMetrics` so its internal LLM/tool spans join the
  same export.
- **Token usage is now workflow output**: `RunAgentNarrative` returns a
  `NarrativeReport` (narrative + input/output tokens), so spend is visible
  in Temporal history even without a collector.

## Consequences

### Positive
- Trends and alerting (Prometheus/Grafana via any OTLP collector) on top
  of Temporal's per-run visibility; ADR-004's budget can be checked
  against real measured spend.
- One instrumentation point serves both execution modes.

### Negative
- A metrics-interface limitation (no add-N counters) shapes the catalog;
  totals must be derived from histogram sums.
- Log export (`observability.NewLogs`) is not wired yet — logs stay local.

## Related Decisions

- ADR-004 (budgets this makes measurable), ADR-007 (Temporal layer this
  instruments).
