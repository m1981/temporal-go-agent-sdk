// Package mcp defines transport and tool-filter shapes for MCP server connections.
//
// Use these types with [github.com/m1981/temporal-go-agent-sdk/pkg/agent.WithMCPConfig] ([github.com/m1981/temporal-go-agent-sdk/pkg/agent.MCPConfig].Transport and ToolFilter),
// [github.com/m1981/temporal-go-agent-sdk/pkg/mcp/client.NewClient], and related APIs. Definitions live in internal/types/mcp.go.
package mcp

import "github.com/m1981/temporal-go-agent-sdk/internal/types"

// Type aliases for MCP transport and tool filtering ([github.com/m1981/temporal-go-agent-sdk/pkg/agent.MCPConfig], client constructors).

type (
	MCPTransportConfig = types.MCPTransportConfig
	MCPTransportType   = types.MCPTransportType
	MCPStdio           = types.MCPStdio
	MCPStreamableHTTP  = types.MCPStreamableHTTP
	MCPToolFilter      = types.MCPToolFilter
)

const (
	MCPTransportTypeStdio          = types.MCPTransportTypeStdio
	MCPTransportTypeStreamableHTTP = types.MCPTransportTypeStreamableHTTP
)
