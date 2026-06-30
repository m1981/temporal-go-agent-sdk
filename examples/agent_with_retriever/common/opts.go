package common

import (
	"fmt"

	excfg "github.com/m1981/temporal-go-agent-sdk/examples"
	"github.com/m1981/temporal-go-agent-sdk/pkg/agent"
	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
	"github.com/m1981/temporal-go-agent-sdk/pkg/logger"
)

// AgentOptions builds shared agent options: runtime, LLM, retriever mode, and system prompt.
// backendLabel is shown in the agent name/description (e.g. "weaviate" or "pgvector").
func AgentOptions(
	cfg *excfg.Config,
	llmClient interfaces.LLMClient,
	log logger.Logger,
	settings *Settings,
	backendLabel string,
) []agent.Option {
	mode := settings.RetrieverMode
	prompt := fmt.Sprintf(
		"You are a helpful assistant with access to a %s knowledge base (%s mode). "+
			"Use retrieved documents to answer questions accurately. "+
			"When in agentic or hybrid mode, call the retriever tool when you need facts from the knowledge base. "+
			"Cite sources when possible.",
		backendLabel,
		mode,
	)
	opts := []agent.Option{
		agent.WithName(fmt.Sprintf("agent-with-retriever-%s", backendLabel)),
		agent.WithDescription(fmt.Sprintf("Agent with %s retriever (%s)", backendLabel, mode)),
		agent.WithSystemPrompt(prompt),
		agent.WithLLMClient(llmClient),
		agent.WithLogger(log),
		agent.WithRetrieverMode(mode),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()),
	}
	return append(opts, excfg.RuntimeOption(cfg)...)
}
