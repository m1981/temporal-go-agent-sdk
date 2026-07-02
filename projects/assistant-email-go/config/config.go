// Package config is the single point of environment access. Downstream code
// receives an immutable Settings value and never calls os.Getenv itself.
package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/classify"
)

const (
	defaultModel         = "claude-haiku-4-5"
	defaultMaxIterations = 10
	defaultTokenBudget   = 50_000
	defaultMemoryPath    = ".data/memory.sqlite"
	defaultQuietHours    = "22-07"
)

// QuietHours is a validated [start,end) window of whole hours, wrap-around
// allowed ("22-07"). Start == End disables the window.
type QuietHours struct {
	Start int
	End   int
}

// ParseQuietHours parses "HH-HH" (24h clock) and validates ranges at load
// time so a typo surfaces at startup, not at 2 a.m.
func ParseQuietHours(s string) (QuietHours, error) {
	parts := strings.Split(strings.TrimSpace(s), "-")
	if len(parts) != 2 {
		return QuietHours{}, fmt.Errorf("QUIET_HOURS must be 'HH-HH', got %q", s)
	}
	start, err1 := strconv.Atoi(strings.TrimSpace(parts[0]))
	end, err2 := strconv.Atoi(strings.TrimSpace(parts[1]))
	if err1 != nil || err2 != nil || start < 0 || start > 23 || end < 0 || end > 23 {
		return QuietHours{}, fmt.Errorf("QUIET_HOURS hours must be 0-23, got %q", s)
	}
	return QuietHours{Start: start, End: end}, nil
}

// Contains reports whether t falls inside the quiet window.
func (q QuietHours) Contains(t time.Time) bool {
	h := t.Hour()
	switch {
	case q.Start == q.End:
		return false // disabled
	case q.Start < q.End:
		return h >= q.Start && h < q.End
	default: // wraps midnight, e.g. 22-07
		return h >= q.Start || h < q.End
	}
}

// Settings is all runtime configuration, resolved once at startup.
type Settings struct {
	AnthropicAPIKey string
	UserEmail       string
	Model           string
	MaxIterations   int
	TokenBudget     int64
	MemoryPath      string
	QuietHours      QuietHours
	Rules           classify.Rules
	LogLevel        string

	// Temporal runtime selection (AGENT_RUNTIME=temporal enables it).
	AgentRuntime      string
	TemporalHost      string
	TemporalPort      int
	TemporalNamespace string
	TemporalTaskQueue string
	DigestInterval    time.Duration

	// Observability (ADR-008). An empty OTLPEndpoint disables all export.
	OTLPEndpoint string
	OTLPProtocol string // "grpc" or "http"
	OTLPInsecure bool
	Environment  string
}

// UseTemporal reports whether the agent should run on the Temporal runtime.
func (s *Settings) UseTemporal() bool { return s.AgentRuntime == "temporal" }

// TemporalAddress is the host:port target for client.Dial.
func (s *Settings) TemporalAddress() string {
	return fmt.Sprintf("%s:%d", s.TemporalHost, s.TemporalPort)
}

// Load reads env vars, optionally seeding from ./.env (never overriding real
// env). It fails fast with a descriptive error on missing or invalid values.
func Load() (*Settings, error) {
	_ = godotenv.Load() // best-effort; absence of .env is fine

	apiKey := strings.TrimSpace(os.Getenv("ANTHROPIC_API_KEY"))
	if apiKey == "" {
		return nil, fmt.Errorf("ANTHROPIC_API_KEY is required (set it in .env or the environment)")
	}
	userEmail := strings.TrimSpace(os.Getenv("USER_EMAIL"))
	if userEmail == "" {
		return nil, fmt.Errorf("USER_EMAIL is required")
	}

	maxIterations, err := intEnv("MAX_ITERATIONS", defaultMaxIterations)
	if err != nil {
		return nil, err
	}
	tokenBudget, err := intEnv("TOKEN_BUDGET", defaultTokenBudget)
	if err != nil {
		return nil, err
	}
	quietHours, err := ParseQuietHours(envDefault("QUIET_HOURS", defaultQuietHours))
	if err != nil {
		return nil, err
	}
	temporalPort, err := intEnv("TEMPORAL_PORT", 7233)
	if err != nil {
		return nil, err
	}
	digestInterval, err := durationEnv("DIGEST_INTERVAL", 2*time.Hour)
	if err != nil {
		return nil, err
	}
	otlpProtocol := strings.ToLower(envDefault("OTLP_PROTOCOL", "grpc"))
	if otlpProtocol != "grpc" && otlpProtocol != "http" {
		return nil, fmt.Errorf("OTLP_PROTOCOL must be 'grpc' or 'http', got %q", otlpProtocol)
	}

	return &Settings{
		AnthropicAPIKey: apiKey,
		UserEmail:       userEmail,
		Model:           envDefault("ANTHROPIC_MODEL", defaultModel),
		MaxIterations:   maxIterations,
		TokenBudget:     int64(tokenBudget),
		MemoryPath:      envDefault("MEMORY_PATH", defaultMemoryPath),
		QuietHours:      quietHours,
		Rules: classify.Rules{
			BossSenders:   listEnv("BOSS_SENDERS"),
			FamilySenders: listEnv("FAMILY_SENDERS"),
			ClientSenders: listEnv("CLIENT_SENDERS"),
		},
		LogLevel:          strings.ToLower(envDefault("LOG_LEVEL", "info")),
		AgentRuntime:      strings.ToLower(strings.TrimSpace(os.Getenv("AGENT_RUNTIME"))),
		TemporalHost:      envDefault("TEMPORAL_HOST", "localhost"),
		TemporalPort:      temporalPort,
		TemporalNamespace: envDefault("TEMPORAL_NAMESPACE", "default"),
		TemporalTaskQueue: envDefault("TEMPORAL_TASK_QUEUE", "email-assistant"),
		DigestInterval:    digestInterval,
		OTLPEndpoint:      strings.TrimSpace(os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")),
		OTLPProtocol:      otlpProtocol,
		OTLPInsecure:      boolEnv("OTLP_INSECURE"),
		Environment:       envDefault("DEPLOY_ENV", "dev"),
	}, nil
}

func envDefault(name, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(name)); v != "" {
		return v
	}
	return fallback
}

func intEnv(name string, fallback int) (int, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer, got %q", name, raw)
	}
	return v, nil
}

func boolEnv(name string) bool {
	switch strings.ToLower(strings.TrimSpace(os.Getenv(name))) {
	case "1", "true", "yes", "on":
		return true
	}
	return false
}

func durationEnv(name string, fallback time.Duration) (time.Duration, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	d, err := time.ParseDuration(raw)
	if err != nil || d <= 0 {
		return 0, fmt.Errorf("%s must be a positive duration like '2h', got %q", name, raw)
	}
	return d, nil
}

func listEnv(name string) []string {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return nil
	}
	var out []string
	for _, p := range strings.Split(raw, ",") {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}
