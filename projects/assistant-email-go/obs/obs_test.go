package obs

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/m1981/temporal-go-agent-sdk/pkg/observability"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/config"
)

type call struct {
	name  string
	value float64
	attrs map[string]any
}

type fakeMetrics struct {
	counters   []call
	histograms []call
}

func attrsMap(attrs []interfaces.Attribute) map[string]any {
	m := map[string]any{}
	for _, a := range attrs {
		m[a.Key] = a.Value
	}
	return m
}

func (f *fakeMetrics) IncrementCounter(_ context.Context, name string, attrs ...interfaces.Attribute) {
	f.counters = append(f.counters, call{name: name, attrs: attrsMap(attrs)})
}

func (f *fakeMetrics) RecordHistogram(_ context.Context, name string, v float64, attrs ...interfaces.Attribute) {
	f.histograms = append(f.histograms, call{name: name, value: v, attrs: attrsMap(attrs)})
}

func (f *fakeMetrics) Shutdown(context.Context) error { return nil }

func capture() (*Telemetry, *fakeMetrics) {
	fm := &fakeMetrics{}
	return &Telemetry{Metrics: fm, Tracer: &observability.NoopTracer{}, Active: true}, fm
}

func TestNoopIsInactiveAndSafe(t *testing.T) {
	tel := Noop()
	if tel.Active {
		t.Error("Noop() must be inactive")
	}
	ctx := context.Background()
	tel.RecordStage(ctx, StagePipeline, time.Now(), errors.New("x"))
	tel.RecordDigest(ctx, 5, 2, true)
	tel.RecordTokens(ctx, 100, 50)
	tel.RecordQuietSkip(ctx)
	if err := tel.Shutdown(ctx); err != nil {
		t.Errorf("noop Shutdown: %v", err)
	}
}

func TestNewWithoutEndpointIsNoop(t *testing.T) {
	tel, err := New(&config.Settings{}, "test")
	if err != nil {
		t.Fatal(err)
	}
	if tel.Active {
		t.Error("empty endpoint must yield inactive telemetry")
	}
}

func TestRecordStage(t *testing.T) {
	tel, fm := capture()
	tel.RecordStage(context.Background(), StageAgent, time.Now(), nil)
	tel.RecordStage(context.Background(), StageAgent, time.Now(), errors.New("boom"))

	if len(fm.counters) != 2 || fm.counters[0].name != MetricStageTotal {
		t.Fatalf("counters = %+v", fm.counters)
	}
	if fm.counters[0].attrs["status"] != "ok" || fm.counters[1].attrs["status"] != "error" {
		t.Errorf("status attrs wrong: %+v", fm.counters)
	}
	if len(fm.histograms) != 2 || fm.histograms[0].name != MetricStageDuration {
		t.Errorf("histograms = %+v", fm.histograms)
	}
}

func TestRecordDigest(t *testing.T) {
	tel, fm := capture()
	tel.RecordDigest(context.Background(), 12, 5, true)
	if len(fm.histograms) != 2 || fm.histograms[0].value != 12 || fm.histograms[1].value != 5 {
		t.Errorf("histograms = %+v", fm.histograms)
	}
	if len(fm.counters) != 1 || fm.counters[0].name != MetricNewUrgentRuns {
		t.Errorf("counters = %+v", fm.counters)
	}

	tel2, fm2 := capture()
	tel2.RecordDigest(context.Background(), 3, 0, false)
	if len(fm2.counters) != 0 {
		t.Errorf("no new-urgent counter expected: %+v", fm2.counters)
	}
}

func TestRecordTokensDirections(t *testing.T) {
	tel, fm := capture()
	tel.RecordTokens(context.Background(), 1000, 200)
	if len(fm.histograms) != 2 {
		t.Fatalf("histograms = %+v", fm.histograms)
	}
	if fm.histograms[0].attrs["direction"] != "input" || fm.histograms[1].attrs["direction"] != "output" {
		t.Errorf("direction attrs wrong: %+v", fm.histograms)
	}
}
