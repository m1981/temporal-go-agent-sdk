# assistant-email-go

Go port of `projects/assistant-email`, built on the repo's own agent SDK
(`pkg/agent`, `pkg/llm/anthropic`). The Python project remains the executable
spec — same rules, same memory semantics, same digest output — while this
version gains the SDK's tested tool-use loop, budgets, and dual runtime
(in-process or durable on Temporal).

## What lives where

| Package    | Ports (Python)              | Notes                                                    |
|------------|-----------------------------|----------------------------------------------------------|
| `domain`   | `domain/email.py`           | `Email`, `Priority` value types                          |
| `classify` | `classify/urgency.py`       | Rule engine mirroring brief.md's flowchart               |
| `notify`   | `notify/formatter.py`       | Pure Markdown digest renderer                            |
| `memory`   | `memory/thread_store.py`    | SQLite (pure-Go driver); `notified_utc` survives upserts |
| `gmail`    | `gmail/gmcli_client.py`     | The single subprocess seam                               |
| `tools`    | `tools/gmail_*.py`          | `interfaces.Tool` implementations for the SDK agent      |
| `pipeline` | `pipeline.py`               | Deterministic digest run next to the LLM narrative       |
| `config`   | `config.py`                 | Single env seam; quiet hours parsed & validated at load  |
| *(gone)*   | `agent/loop.py`             | Replaced by `agent.NewAgent` — the SDK owns the loop     |

## Run

```bash
cd projects/assistant-email-go
ANTHROPIC_API_KEY=... USER_EMAIL=you@gmail.com go run ./cmd/digest
```

Optional env: `ANTHROPIC_MODEL`, `MAX_ITERATIONS`, `TOKEN_BUDGET`,
`MEMORY_PATH`, `QUIET_HOURS` (e.g. `22-07`; `FORCE_RUN=1` overrides),
`BOSS_SENDERS` / `FAMILY_SENDERS` / `CLIENT_SENDERS` (comma-separated).

## Scheduled, durable mode (Temporal — ADR-007)

`digestwf` packages the digest as a Temporal workflow: quiet-hours gate →
deterministic pipeline → LLM narrative, each an activity with its own
timeout and retry policy.

```bash
go run ./cmd/worker              # hosts EmailDigestWorkflow + activities
go run ./cmd/schedule            # creates the "email-digest" Schedule (every DIGEST_INTERVAL, default 2h)
go run ./cmd/schedule -replace   # recreate after changing the interval
```

Temporal env: `TEMPORAL_HOST` / `TEMPORAL_PORT` / `TEMPORAL_NAMESPACE` /
`TEMPORAL_TASK_QUEUE` (defaults: localhost / 7233 / default /
email-assistant). Overlapping runs are skipped (idempotent thanks to thread
memory), quiet-hour skips are visible in workflow history. `cmd/digest`
remains the one-shot/cron fallback (ADR-005 Phase 1); `AGENT_RUNTIME=temporal`
additionally runs its agent loop on the SDK's Temporal runtime.

## Test

```bash
go test ./...
```

Tests are hermetic: no network, no gmcli binary, no API key.
