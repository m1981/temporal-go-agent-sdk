package config

import (
	"strings"
	"testing"
	"time"
)

func setRequired(t *testing.T) {
	t.Helper()
	t.Setenv("ANTHROPIC_API_KEY", "sk-test")
	t.Setenv("USER_EMAIL", "me@example.com")
}

func TestLoadRequiresAPIKey(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "")
	t.Setenv("USER_EMAIL", "me@example.com")
	if _, err := Load(); err == nil || !strings.Contains(err.Error(), "ANTHROPIC_API_KEY") {
		t.Fatalf("want ANTHROPIC_API_KEY error, got %v", err)
	}
}

func TestLoadRequiresUserEmail(t *testing.T) {
	t.Setenv("ANTHROPIC_API_KEY", "sk-test")
	t.Setenv("USER_EMAIL", "")
	if _, err := Load(); err == nil || !strings.Contains(err.Error(), "USER_EMAIL") {
		t.Fatalf("want USER_EMAIL error, got %v", err)
	}
}

func TestLoadDefaults(t *testing.T) {
	setRequired(t)
	s, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if s.Model != defaultModel || s.MaxIterations != 10 || s.TokenBudget != 50_000 {
		t.Errorf("defaults wrong: %+v", s)
	}
	if s.QuietHours != (QuietHours{Start: 22, End: 7}) {
		t.Errorf("QuietHours = %+v", s.QuietHours)
	}
	if s.UseTemporal() {
		t.Error("temporal runtime should be off by default")
	}
}

func TestLoadDigestInterval(t *testing.T) {
	setRequired(t)
	s, err := Load()
	if err != nil || s.DigestInterval != 2*time.Hour {
		t.Errorf("default DigestInterval = %v, %v; want 2h", s.DigestInterval, err)
	}
	t.Setenv("DIGEST_INTERVAL", "30m")
	if s, err = Load(); err != nil || s.DigestInterval != 30*time.Minute {
		t.Errorf("DigestInterval = %v, %v; want 30m", s.DigestInterval, err)
	}
	for _, bad := range []string{"nope", "-1h", "0s"} {
		t.Setenv("DIGEST_INTERVAL", bad)
		if _, err = Load(); err == nil {
			t.Errorf("DIGEST_INTERVAL=%q: want error", bad)
		}
	}
}

func TestLoadOTLPSettings(t *testing.T) {
	setRequired(t)
	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
	s, err := Load()
	if err != nil || s.OTLPEndpoint != "" || s.OTLPProtocol != "grpc" || s.OTLPInsecure {
		t.Errorf("defaults wrong: %+v, %v", s, err)
	}

	t.Setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
	t.Setenv("OTLP_PROTOCOL", "http")
	t.Setenv("OTLP_INSECURE", "true")
	if s, err = Load(); err != nil || s.OTLPEndpoint != "localhost:4317" || s.OTLPProtocol != "http" || !s.OTLPInsecure {
		t.Errorf("parsed wrong: %+v, %v", s, err)
	}

	t.Setenv("OTLP_PROTOCOL", "carrier-pigeon")
	if _, err = Load(); err == nil {
		t.Error("want error for invalid OTLP_PROTOCOL")
	}
}

func TestParseOTLPHeaders(t *testing.T) {
	if h := parseOTLPHeaders(""); h != nil {
		t.Errorf("empty input: got %v, want nil", h)
	}
	// Single header whose base64 value contains '=' padding — must split on
	// the first '=' only.
	h := parseOTLPHeaders("Authorization=Basic dXNlcjpwYXNz==")
	if h["Authorization"] != "Basic dXNlcjpwYXNz==" {
		t.Errorf("Authorization = %q", h["Authorization"])
	}
	// Multiple headers, percent-encoded value decoded.
	h = parseOTLPHeaders("X-Scope-OrgID=tenant-1,X-Custom=hello%20world")
	if h["X-Scope-OrgID"] != "tenant-1" || h["X-Custom"] != "hello world" {
		t.Errorf("multi-header parse = %v", h)
	}
	// Malformed pair (no '=') is skipped, not fatal.
	h = parseOTLPHeaders("no-equals-sign,Valid=ok")
	if len(h) != 1 || h["Valid"] != "ok" {
		t.Errorf("malformed-pair handling = %v", h)
	}
}

func TestLoadParsesOTLPHeaders(t *testing.T) {
	setRequired(t)
	t.Setenv("OTEL_EXPORTER_OTLP_HEADERS", "Authorization=Basic dGVzdA==")
	s, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if s.OTLPHeaders["Authorization"] != "Basic dGVzdA==" {
		t.Errorf("OTLPHeaders = %v", s.OTLPHeaders)
	}
}

func TestLoadRejectsBadInteger(t *testing.T) {
	setRequired(t)
	t.Setenv("MAX_ITERATIONS", "ten")
	if _, err := Load(); err == nil || !strings.Contains(err.Error(), "MAX_ITERATIONS") {
		t.Fatalf("want MAX_ITERATIONS error, got %v", err)
	}
}

func TestLoadParsesRules(t *testing.T) {
	setRequired(t)
	t.Setenv("BOSS_SENDERS", "boss@x.com, ceo@x.com ,")
	s, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if len(s.Rules.BossSenders) != 2 || s.Rules.BossSenders[1] != "ceo@x.com" {
		t.Errorf("BossSenders = %v", s.Rules.BossSenders)
	}
}

func TestParseQuietHoursValidation(t *testing.T) {
	for _, bad := range []string{"22-", "22", "25-07", "aa-bb", "22-07-01", ""} {
		if _, err := ParseQuietHours(bad); err == nil {
			t.Errorf("ParseQuietHours(%q): want error", bad)
		}
	}
	q, err := ParseQuietHours("09-17")
	if err != nil || q.Start != 9 || q.End != 17 {
		t.Errorf("ParseQuietHours(09-17) = %+v, %v", q, err)
	}
}

func TestQuietHoursContains(t *testing.T) {
	at := func(hour int) time.Time {
		return time.Date(2026, 7, 1, hour, 30, 0, 0, time.UTC)
	}
	wrap := QuietHours{Start: 22, End: 7} // wraps midnight
	cases := []struct {
		q    QuietHours
		hour int
		want bool
	}{
		{wrap, 23, true},
		{wrap, 2, true},
		{wrap, 7, false},
		{wrap, 12, false},
		{QuietHours{Start: 9, End: 17}, 10, true},
		{QuietHours{Start: 9, End: 17}, 8, false},
		{QuietHours{Start: 9, End: 17}, 17, false},
		{QuietHours{Start: 5, End: 5}, 5, false}, // disabled
	}
	for _, tc := range cases {
		if got := tc.q.Contains(at(tc.hour)); got != tc.want {
			t.Errorf("%+v.Contains(%02d:30) = %v, want %v", tc.q, tc.hour, got, tc.want)
		}
	}
}
