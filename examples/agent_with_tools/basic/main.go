package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	config "github.com/m1981/temporal-go-agent-sdk/examples"
	"github.com/m1981/temporal-go-agent-sdk/examples/shared"
	"github.com/m1981/temporal-go-agent-sdk/pkg/agent"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/calculator"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/currenttime"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/echo"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/random"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/search"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/weather"
	"github.com/m1981/temporal-go-agent-sdk/pkg/tools/wikipedia"
)

func main() {
	cfg := config.LoadFromEnv()

	llmClient, err := config.NewLLMClientFromConfig(cfg)
	if err != nil {
		log.Fatalf("failed to create LLM client: %v", err)
	}

	reg := agent.NewToolRegistry()
	if err := agent.RegisterTools(reg,
		echo.New(),
		currenttime.New(),
		random.New(),
		calculator.New(),
		weather.New(),
		wikipedia.New(),
		search.New(),
	); err != nil {
		log.Fatalf("register tools: %v", err)
	}
	opts := []agent.Option{
		agent.WithName("agent-with-tools"),
		agent.WithDescription("Agent with echo, currenttime, random, calculator, weather, wikipedia, search tools"),
		agent.WithSystemPrompt("You are a helpful assistant with access to tools. Use them when appropriate: current time, weather, math, random numbers, Wikipedia, and web search."),
		agent.WithLLMClient(llmClient),
		agent.WithToolRegistry(reg),
		agent.WithToolApprovalPolicy(agent.AutoToolApprovalPolicy()), // allow all tools without approval (default requires approval)
		agent.WithLogger(config.NewLoggerFromLogConfig(cfg)),
	}
	opts = append(opts, config.RuntimeOption(cfg)...)

	a, err := agent.NewAgent(opts...)
	if err != nil {
		log.Fatal(config.FormatNewAgentError("failed to create agent", err))
	}
	defer a.Close()

	prompt := strings.Join(os.Args[1:], " ")
	if prompt == "" {
		prompt = "What's the current time and what's 17 * 23?"
	}

	fmt.Println("user:", prompt)
	result, err := a.Run(context.Background(), prompt, nil)
	if err != nil {
		log.Printf("run failed: %v", err)
		return
	}
	fmt.Println("agent:", result.Content)
	shared.PrintRunFooters(result)
}
