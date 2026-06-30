// Package a2a defines skill-filter shapes for A2A agent connections.
//
// Use these types with [github.com/m1981/temporal-go-agent-sdk/pkg/agent.WithA2AConfig] ([github.com/m1981/temporal-go-agent-sdk/pkg/agent.A2AConfig].SkillFilter),
// [github.com/m1981/temporal-go-agent-sdk/pkg/a2a/client.NewClient], and related APIs. Definitions live in internal/types/a2a.go.
package a2a

import "github.com/m1981/temporal-go-agent-sdk/internal/types"

// Type aliases for A2A skill filtering ([github.com/m1981/temporal-go-agent-sdk/pkg/agent.A2AConfig], client constructors).

type (
	A2ASkillSpec   = types.A2ASkillSpec
	A2ASkillFilter = types.A2ASkillFilter
)
