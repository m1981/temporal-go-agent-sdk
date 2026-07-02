# Email Assistant - Project Brief

## Intention

Build a **personal email assistant** that:
1. Monitors inbox continuously
2. Classifies emails by urgency
3. Sends summaries every 2 hours
4. Alerts immediately for urgent emails
5. Preserves thread context for continuity

## Architecture Overview

```mermaid
graph TB
    subgraph "Email Assistant System"
        MAIN[main.go<br/>Entry Point]
        AGENT[Agent<br/>Claude Haiku]
        
        subgraph "Tools"
            READER[GmailReaderTool]
            SENDER[GmailSenderTool]
        end
        
        subgraph "External Services"
            GMAIL[Gmail API<br/>via gmcli]
            ANTHROPIC[Anthropic API<br/>Claude Haiku]
        end
        
        subgraph "Storage (Future)"
            MEMORY[Memory<br/>pgvector]
            CONV[Conversation<br/>Redis]
        end
    end
    
    MAIN --> AGENT
    AGENT --> READER
    AGENT --> SENDER
    READER --> GMAIL
    SENDER --> GMAIL
    AGENT --> ANTHROPIC
    
    AGENT -.-> MEMORY
    AGENT -.-> CONV
    
    style MAIN fill:#e1f5fe
    style AGENT fill:#fff3e0
    style READER fill:#e8f5e9
    style SENDER fill:#e8f5e9
    style GMAIL fill:#fce4ec
    style ANTHROPIC fill:#fce4ec
    style MEMORY fill:#f3e5f5
    style CONV fill:#f3e5f5
```

## Core Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent
    participant R as GmailReader
    participant S as GmailSender
    participant G as Gmail
    
    Note over U,G: Every 2 Hours (Scheduled)
    
    U->>A: Check emails
    A->>R: search("newer_than:2h")
    R->>G: gmcli search
    G-->>R: Email list
    R-->>A: Parsed emails
    
    A->>A: Classify urgency
    
    alt Urgent emails found
        A->>S: send(summary, URGENT)
        S->>G: gmcli send
        G-->>U: 📧 Immediate alert
    else No urgent emails
        A->>S: send(summary, NORMAL)
        S->>G: gmcli send
        G-->>U: 📧 2-hour summary
    end
```

## Priority Classification

```mermaid
graph LR
    subgraph "Email Input"
        E[New Email]
    end
    
    subgraph "Classification Rules"
        R1{From Boss?}
        R2{Family?}
        R3{Deadline today?}
        R4{Meeting < 2h?}
        R5{Client?}
    end
    
    subgraph "Priority Levels"
        URGENT[🚨 URGENT<br/>Immediate]
        IMPORTANT[⭐ IMPORTANT<br/>In summary]
        LOW[📋 LOW<br/>Batch]
    end
    
    E --> R1
    R1 -->|Yes| URGENT
    R1 -->|No| R2
    R2 -->|Yes| URGENT
    R2 -->|No| R3
    R3 -->|Yes| URGENT
    R3 -->|No| R4
    R4 -->|Yes| URGENT
    R4 -->|No| R5
    R5 -->|Yes| IMPORTANT
    R5 -->|No| LOW
    
    style URGENT fill:#ffcdd2
    style IMPORTANT fill:#fff9c4
    style LOW fill:#c8e6c9
```

## Tool Architecture

```mermaid
classDiagram
    class Tool {
        <<interface>>
        +Name() string
        +DisplayName() string
        +Description() string
        +Parameters() JSONSchema
        +Execute(ctx, args) any
    }
    
    class GmailReaderTool {
        -userEmail string
        +Name() "gmail_reader"
        +searchEmails(ctx, args)
        +readThread(ctx, args)
    }
    
    class GmailSenderTool {
        -userEmail string
        +Name() "gmail_sender"
        +Execute(ctx, args)
    }
    
    Tool <|.. GmailReaderTool
    Tool <|.. GmailSenderTool
    
    GmailReaderTool --> gmcli : exec
    GmailSenderTool --> gmcli : exec
```

## Scheduling Strategy

```mermaid
stateDiagram-v2
    [*] --> Idle
    
    Idle --> CheckEmails : Every 2 hours
    
    CheckEmails --> Classify : Emails found
    CheckEmails --> Idle : No emails
    
    Classify --> SendUrgent : Has URGENT
    Classify --> SendSummary : No urgent
    
    SendUrgent --> UpdateMemory
    SendSummary --> UpdateMemory
    
    UpdateMemory --> Idle
    
    note right of SendUrgent
        Immediate notification
        Don't wait for 2h cycle
    end note
```

## Memory Architecture (Future)

```mermaid
graph TB
    subgraph "Memory Types"
        subgraph "Short-term"
            THREAD[Thread Context<br/>Last 50 messages]
        end
        
        subgraph "Long-term"
            USER[User Preferences<br/>Priority rules]
            HISTORY[Email History<br/>Who, what, when]
            PATTERNS[Urgency Patterns<br/>What user marks important]
        end
    end
    
    subgraph "Storage Backends"
        PG[pgvector<br/>Semantic search]
        REDIS[Redis<br/>Fast cache]
    end
    
    THREAD --> REDIS
    USER --> PG
    HISTORY --> PG
    PATTERNS --> PG
    
    style THREAD fill:#e3f2fd
    style USER fill:#f3e5f5
    style HISTORY fill:#e8f5e9
    style PATTERNS fill:#fff3e0
```

## Notification Logic

```mermaid
flowchart TD
    A[Check Emails] --> B{Any URGENT?}
    
    B -->|Yes| C[Send Immediate]
    B -->|No| D{Last summary > 2h?}
    
    D -->|Yes| E[Send Summary]
    D -->|No| F[Wait]
    
    C --> G[Update Memory]
    E --> G
    F --> H[Next Check]
    
    G --> H
    
    subgraph "Summary Content"
        S1[Total emails]
        S2[Urgent count]
        S3[Important count]
        S4[Top 5 items]
        S5[Action items]
    end
    
    E --> S1
    E --> S2
    E --> S3
    E --> S4
    E --> S5
    
    style C fill:#ffcdd2
    style E fill:#c8e6c9
    style F fill:#e0e0e0
```

## Deployment (Future)

```mermaid
graph LR
    subgraph "Local Development"
        LOCAL[./email-assistant]
    end
    
    subgraph "Production"
        TEMPORAL[Temporal Server]
        WORKER[Worker Pod]
        CRON[Cron Schedule]
    end
    
    LOCAL -->|Future| TEMPORAL
    TEMPORAL --> WORKER
    CRON --> WORKER
    
    WORKER --> GMAIL[Gmail API]
    WORKER --> CLAUDE[Claude API]
    
    style LOCAL fill:#e8eaf6
    style TEMPORAL fill:#fff3e0
    style WORKER fill:#e8f5e9
```

## Configuration

| Setting | Value | Notes |
|---|---|---|
| LLM Model | claude-haiku-4-5 | Fast, cheap |
| Max Tokens | 50,000 | Per run budget |
| Max Iterations | 10 | Tool calls per run |
| Check Interval | 2 hours | Temporal cron |
| Quiet Hours | 22:00-07:00 | No notifications |

## Success Metrics

| Metric | Target | How to Measure |
|---|---|---|
| Response time | < 30s | Agent run duration |
| Accuracy | > 90% | User feedback |
| Token usage | < 50K/day | Anthropic dashboard |
| False positive | < 5% | Urgent classification |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Gmail API rate limit | High | Cache, batch requests |
| Token budget exceeded | Medium | MaxTokens limit |
| Wrong classification | Medium | Learn from corrections |
| Privacy concern | High | Local only, no cloud |

## Roadmap

```mermaid
gantt
    title Email Assistant Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1 (Done)
    Walking skeleton     :done, p1, 2026-07-02, 1d
    section Phase 2
    Thread memory        :active, p2, 2026-07-03, 2d
    section Phase 3
    Scheduling           :p3, 2026-07-05, 1d
    section Phase 4
    Smart notifications  :p4, 2026-07-06, 2d
    section Phase 5
    Production deploy    :p5, 2026-07-08, 3d
```
