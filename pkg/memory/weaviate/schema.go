package weaviate

import "github.com/m1981/temporal-go-agent-sdk/pkg/memory"

// Default Weaviate class and property names for [Memory].
const (
	DefaultClassName = "AgentMemory"
	DefaultTextField = "text"

	PropKind      = "kind"
	PropMetadata  = "metadata"
	PropScopeTags = "scope_tags"
	PropExpiresAt = "expires_at"
	PropCreatedAt = "created_at"
	PropUpdatedAt = "updated_at"
	PropUserID    = memory.ScopeKeyUserID
	PropTenantID  = memory.ScopeKeyTenantID
	PropAgentID   = memory.ScopeKeyAgentID
)

// DefaultLoadLimit is the maximum memories returned when [interfaces.WithLoadLimit] is zero or negative.
const DefaultLoadLimit = 10

// DefaultMinScore is the default nearText certainty when [interfaces.WithMinScore] is zero.
const DefaultMinScore float32 = 0.35
