package base

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/m1981/temporal-go-agent-sdk/pkg/interfaces"
)

// Tool-result envelope (AP-05, PAT-003).
//
// Tool output is untrusted input: if it reaches the model as free text it becomes an
// instruction channel. Every tool result therefore enters model-facing message content
// only through the typed, delimited envelope rendered here. This file is the single
// construction site for that framing; both the local loop and the temporal workflow
// consume it. The format is plain text so it is provider-agnostic (anthropic / openai /
// gemini all receive it as ordinary message content).

// ToolResultStatus classifies a tool outcome for the model-facing envelope.
type ToolResultStatus string

const (
	// ToolResultStatusOK marks successfully produced tool output.
	ToolResultStatusOK ToolResultStatus = "ok"
	// ToolResultStatusError marks a failed tool call; the enveloped content is then
	// one of the static Msg* texts from tool_error.go, never a raw error.
	ToolResultStatusError ToolResultStatus = "error"
)

const (
	toolResultClose = "</tool_result>"
	// toolResultCloseEscaped neutralizes a closing delimiter smuggled inside tool
	// output so untrusted content cannot terminate the envelope early.
	toolResultCloseEscaped = "<\\/tool_result>"
)

// RenderToolResultEnvelope frames content as delimited tool-result data.
// Any closing delimiter inside content is escaped so the output contains exactly one
// closing delimiter: the envelope's own.
func RenderToolResultEnvelope(toolName string, status ToolResultStatus, content string) string {
	safe := strings.ReplaceAll(content, toolResultClose, toolResultCloseEscaped)
	return fmt.Sprintf("<tool_result name=%q status=%q>\n%s\n%s", toolName, string(status), safe, toolResultClose)
}

// ToolResultContent converts a tool's Execute result into its string form for enveloping.
// Strings and byte slices pass through; structured values are JSON-encoded so the model
// sees data, not Go formatting.
func ToolResultContent(result any) string {
	switch v := result.(type) {
	case nil:
		return ""
	case string:
		return v
	case []byte:
		return string(v)
	case fmt.Stringer:
		return v.String()
	}
	if b, err := json.Marshal(result); err == nil {
		return string(b)
	}
	return fmt.Sprint(result)
}

// BuildEnvelopedToolResultMessage constructs the tool-role message whose content is the
// typed envelope around content.
func BuildEnvelopedToolResultMessage(toolCallID, toolName string, status ToolResultStatus, content string) interfaces.Message {
	return BuildToolResultMessage(toolCallID, toolName, RenderToolResultEnvelope(toolName, status, content))
}

// ToolFailureContent renders the model-facing content for a failed tool call: the static
// per-class corrective text (PR-02) inside an error-status envelope. The raw err must be
// recorded on harness-only channels (logs / spans) by the caller — it never appears here.
func ToolFailureContent(toolName string, err error) string {
	return RenderToolResultEnvelope(toolName, ToolResultStatusError, ModelFacingToolErrorText(err))
}

// BuildToolErrorResultMessage constructs the tool-role message for a failed tool call
// using ToolFailureContent.
func BuildToolErrorResultMessage(toolCallID, toolName string, err error) interfaces.Message {
	return BuildToolResultMessage(toolCallID, toolName, ToolFailureContent(toolName, err))
}
