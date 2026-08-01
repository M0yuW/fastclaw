package eval

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type HTTPExecutor struct {
	BaseURL string
	APIKey  string
	Client  *http.Client
}

type chatCompletionRequest struct {
	Model    string                 `json:"model,omitempty"`
	Messages []chatMessage          `json:"messages"`
	Stream   bool                   `json:"stream"`
	Tools    []chatCompletionTool   `json:"tools,omitempty"`
	FastClaw chatCompletionFastClaw `json:"fastclaw"`
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatCompletionResponse struct {
	Model   string `json:"model"`
	Choices []struct {
		Message chatMessage `json:"message"`
	} `json:"choices"`
	Usage    Usage `json:"usage"`
	FastClaw struct {
		Trace      []TraceEvent     `json:"trace"`
		State      map[string]any   `json:"state"`
		ModelCalls []ModelCallUsage `json:"model_calls"`
	} `json:"fastclaw"`
}

type chatCompletionTool struct {
	Type     string                     `json:"type"`
	Function chatCompletionToolFunction `json:"function"`
}

type chatCompletionToolFunction struct {
	Name        string         `json:"name"`
	Description string         `json:"description,omitempty"`
	Parameters  map[string]any `json:"parameters"`
}

type chatCompletionFastClaw struct {
	Eval                  bool                         `json:"eval,omitempty"`
	IncludeTrace          bool                         `json:"include_trace"`
	IncludeUsageBreakdown bool                         `json:"include_usage_breakdown"`
	IsolateTools          bool                         `json:"isolate_tools,omitempty"`
	Pricing               map[string]ModelPricing      `json:"pricing,omitempty"`
	ToolResults           map[string]string            `json:"tool_results,omitempty"`
	State                 map[string]any               `json:"state,omitempty"`
	ToolBehaviors         map[string]StateToolBehavior `json:"tool_behaviors,omitempty"`
}

func (e *HTTPExecutor) Execute(ctx context.Context, request ExecutionRequest) (ExecutionResponse, error) {
	if strings.TrimSpace(e.BaseURL) == "" {
		return ExecutionResponse{}, errors.New("eval base URL is required")
	}
	tools := make([]chatCompletionTool, 0, len(request.Tools))
	toolResults := make(map[string]string, len(request.Tools))
	toolBehaviors := make(map[string]StateToolBehavior, len(request.Tools))
	for _, definition := range request.Tools {
		tools = append(tools, chatCompletionTool{
			Type: "function",
			Function: chatCompletionToolFunction{
				Name:        definition.Name,
				Description: definition.Description,
				Parameters:  definition.Parameters,
			},
		})
		if definition.Result != "" {
			toolResults[definition.Name] = definition.Result
		}
		if definition.Behavior != nil {
			toolBehaviors[definition.Name] = *definition.Behavior
		}
	}
	body, err := json.Marshal(chatCompletionRequest{
		Model: request.Model,
		Messages: []chatMessage{
			{Role: "user", Content: request.Prompt},
		},
		Stream: false,
		Tools:  tools,
		FastClaw: chatCompletionFastClaw{
			Eval:                  true,
			IncludeTrace:          true,
			IncludeUsageBreakdown: true,
			IsolateTools:          request.IsolateTools,
			Pricing:               request.Pricing,
			ToolResults:           toolResults,
			State:                 request.State,
			ToolBehaviors:         toolBehaviors,
		},
	})
	if err != nil {
		return ExecutionResponse{}, fmt.Errorf("encode chat completion request: %w", err)
	}

	endpoint := strings.TrimRight(e.BaseURL, "/") + "/v1/chat/completions"
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return ExecutionResponse{}, fmt.Errorf("create chat completion request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	if e.APIKey != "" {
		httpRequest.Header.Set("Authorization", "Bearer "+e.APIKey)
	}
	if request.AgentID != "" {
		httpRequest.Header.Set("x-fastclaw-agent-id", request.AgentID)
	}
	if request.SessionKey != "" {
		httpRequest.Header.Set("x-fastclaw-session-key", request.SessionKey)
	}

	client := e.Client
	if client == nil {
		client = http.DefaultClient
	}
	response, err := client.Do(httpRequest)
	if err != nil {
		return ExecutionResponse{}, fmt.Errorf("execute chat completion request: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		message, readErr := io.ReadAll(io.LimitReader(response.Body, 64<<10))
		if readErr != nil {
			return ExecutionResponse{}, fmt.Errorf("chat completion returned %s", response.Status)
		}
		return ExecutionResponse{}, fmt.Errorf("chat completion returned %s: %s", response.Status, strings.TrimSpace(string(message)))
	}

	var completion chatCompletionResponse
	if err := json.NewDecoder(response.Body).Decode(&completion); err != nil {
		return ExecutionResponse{}, fmt.Errorf("decode chat completion response: %w", err)
	}
	if len(completion.Choices) == 0 {
		return ExecutionResponse{}, errors.New("chat completion response has no choices")
	}
	execution := ExecutionResponse{
		Output:     completion.Choices[0].Message.Content,
		Model:      completion.Model,
		Usage:      completion.Usage,
		ModelCalls: completion.FastClaw.ModelCalls,
		Trace:      completion.FastClaw.Trace,
		State:      completion.FastClaw.State,
	}
	for _, event := range execution.Trace {
		if event.Type == "error" && strings.TrimSpace(event.Message) != "" {
			return execution, fmt.Errorf("agent turn failed: %s", event.Message)
		}
	}
	return execution, nil
}
