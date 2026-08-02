package provider

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
)

// OpenAIProvider implements the Provider interface for OpenAI-compatible APIs.
type OpenAIProvider struct {
	apiKey  string
	apiBase string
	client  *http.Client
}

// NewOpenAI creates a new OpenAI-compatible provider. apiBase is taken
// verbatim — the operator's configured URL is the only source of truth.
// We intentionally do NOT default to "https://api.openai.com/v1" when
// apiBase is empty: that silent default produced "why is it calling
// OpenAI" mysteries when users had only a deepseek provider configured
// but the resolution path picked up an empty cfg. An empty apiBase now
// causes calls to fail loudly, which is what we want.
func NewOpenAI(apiKey, apiBase string) *OpenAIProvider {
	apiBase = strings.TrimRight(apiBase, "/")
	return &OpenAIProvider{
		apiKey:  apiKey,
		apiBase: apiBase,
		client:  &http.Client{},
	}
}

// apiMessage is the wire format for a message sent to the OpenAI API.
// It uses json.RawMessage for Content to support both string and array formats.
type apiMessage struct {
	Role             string          `json:"role"`
	Content          json.RawMessage `json:"content,omitempty"`
	ReasoningContent string          `json:"reasoning_content,omitempty"`
	ToolCalls        []ToolCall      `json:"tool_calls,omitempty"`
	ToolCallID       string          `json:"tool_call_id,omitempty"`
	Name             string          `json:"name,omitempty"`
}

type chatRequest struct {
	Model           string            `json:"model"`
	Messages        []json.RawMessage `json:"messages"`
	Tools           []Tool            `json:"tools,omitempty"`
	MaxTokens       int               `json:"max_tokens,omitempty"`
	Temperature     float64           `json:"temperature,omitempty"`
	Stream          bool              `json:"stream"`
	StreamOptions   *streamOptions    `json:"stream_options,omitempty"`
	Thinking        *thinkingConfig   `json:"thinking,omitempty"`
	ReasoningEffort string            `json:"reasoning_effort,omitempty"`
}

type thinkingConfig struct {
	Type string `json:"type"`
}

type streamOptions struct {
	IncludeUsage bool `json:"include_usage"`
}

// toAPIMessages converts provider Messages to wire-format apiMessages,
// handling ContentParts for multimodal messages.
func toAPIMessages(msgs []Message) []json.RawMessage {
	out := make([]json.RawMessage, len(msgs))
	for i, m := range msgs {
		// For assistant messages with cached raw JSON, use it directly
		// to guarantee prompt cache hits (byte-identical prefix).
		if m.Role == "assistant" && len(m.RawAssistant) > 0 {
			out[i] = m.RawAssistant
			continue
		}

		am := apiMessage{
			Role:             m.Role,
			ReasoningContent: m.Thinking,
			ToolCalls:        m.ToolCalls,
			ToolCallID:       m.ToolCallID,
			Name:             m.Name,
		}
		if len(m.ContentParts) > 0 {
			am.Content, _ = json.Marshal(m.ContentParts)
		} else {
			am.Content, _ = json.Marshal(m.Content)
		}
		out[i], _ = json.Marshal(am)
	}
	return out
}

// sseDelta mirrors the OpenAI streaming delta structure including tool call index.
type sseToolCallDelta struct {
	Index    int          `json:"index"`
	ID       string       `json:"id,omitempty"`
	Type     string       `json:"type,omitempty"`
	Function FunctionCall `json:"function"`
}

type sseDelta struct {
	Role             string             `json:"role,omitempty"`
	Content          string             `json:"content,omitempty"`
	ReasoningContent string             `json:"reasoning_content,omitempty"`
	ToolCalls        []sseToolCallDelta `json:"tool_calls,omitempty"`
}

type sseChoice struct {
	Delta        sseDelta `json:"delta"`
	FinishReason string   `json:"finish_reason"`
}

type sseResponse struct {
	Choices []sseChoice `json:"choices"`
	Usage   *struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
		PromptDetails    struct {
			CachedTokens int `json:"cached_tokens"`
		} `json:"prompt_tokens_details"`
	} `json:"usage,omitempty"`
}

func (p *OpenAIProvider) buildRequestWithUsage(
	ctx context.Context,
	messages []Message,
	tools []Tool,
	model string,
	maxTokens int,
	temperature float64,
	stream bool,
	includeUsage bool,
) (*http.Request, error) {
	req := chatRequest{
		Model:       StripProviderPrefix(model),
		Messages:    toAPIMessages(messages),
		MaxTokens:   maxTokens,
		Temperature: temperature,
		Stream:      stream,
	}
	if stream && includeUsage {
		req.StreamOptions = &streamOptions{IncludeUsage: true}
	}
	if len(tools) > 0 {
		req.Tools = tools
	}
	if strings.Contains(p.apiBase, "deepseek.com") {
		switch thinkingModeFromContext(ctx) {
		case "off":
			req.Thinking = &thinkingConfig{Type: "disabled"}
		case "low":
			req.Thinking = &thinkingConfig{Type: "enabled"}
			req.ReasoningEffort = "low"
		case "medium", "high", "adaptive":
			req.Thinking = &thinkingConfig{Type: "enabled"}
			req.ReasoningEffort = "high"
		case "max":
			req.Thinking = &thinkingConfig{Type: "enabled"}
			req.ReasoningEffort = "max"
		}
	}

	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	url := p.apiBase + "/chat/completions"
	thinkingType := "default"
	if req.Thinking != nil {
		thinkingType = req.Thinking.Type
	}
	slog.Info(
		"openai request",
		"url", url,
		"model", req.Model,
		"thinking", thinkingType,
		"reasoning_effort", req.ReasoningEffort,
	)
	httpReq, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+p.apiKey)
	return httpReq, nil
}

func (p *OpenAIProvider) Chat(ctx context.Context, messages []Message, tools []Tool, model string, maxTokens int, temperature float64) (*Response, error) {
	resp, err := p.doChatRequest(ctx, messages, tools, model, maxTokens, temperature)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(respBody))
	}

	return parseOpenAISSE(ctx, resp.Body, nil)
}

// ChatStream returns a StreamReader that yields chunks as they arrive from the LLM.
func (p *OpenAIProvider) ChatStream(ctx context.Context, messages []Message, tools []Tool, model string, maxTokens int, temperature float64) (*StreamReader, error) {
	resp, err := p.doChatRequest(ctx, messages, tools, model, maxTokens, temperature)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(respBody))
	}

	ch := make(chan StreamChunk, 64)
	reader := NewStreamReader(ch)

	go func() {
		defer resp.Body.Close()
		defer close(ch)

		result, parseErr := parseOpenAISSE(ctx, resp.Body, func(chunk StreamChunk) error {
			select {
			case ch <- chunk:
				return nil
			case <-ctx.Done():
				return ctx.Err()
			}
		})
		reader.setResult(result, parseErr)
	}()

	return reader, nil
}

func (p *OpenAIProvider) doChatRequest(
	ctx context.Context,
	messages []Message,
	tools []Tool,
	model string,
	maxTokens int,
	temperature float64,
) (*http.Response, error) {
	httpReq, err := p.buildRequestWithUsage(
		ctx,
		messages,
		tools,
		model,
		maxTokens,
		temperature,
		true,
		true,
	)
	if err != nil {
		return nil, err
	}
	response, err := p.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	if response.StatusCode < http.StatusBadRequest || response.StatusCode >= http.StatusInternalServerError {
		return response, nil
	}
	responseBody, readErr := io.ReadAll(response.Body)
	response.Body.Close()
	if readErr != nil {
		return nil, fmt.Errorf("read API error: %w", readErr)
	}
	if !isUnsupportedStreamingUsageError(response.StatusCode, responseBody) {
		response.Body = io.NopCloser(bytes.NewReader(responseBody))
		return response, nil
	}
	fallbackRequest, err := p.buildRequestWithUsage(
		ctx,
		messages,
		tools,
		model,
		maxTokens,
		temperature,
		true,
		false,
	)
	if err != nil {
		return nil, err
	}
	fallbackResponse, err := p.client.Do(fallbackRequest)
	if err != nil {
		return nil, fmt.Errorf("send request without streaming usage: %w", err)
	}
	return fallbackResponse, nil
}

func isUnsupportedStreamingUsageError(status int, responseBody []byte) bool {
	if status != http.StatusBadRequest && status != http.StatusUnprocessableEntity {
		return false
	}
	lowerBody := strings.ToLower(string(responseBody))
	hasField := strings.Contains(lowerBody, "stream_options") ||
		strings.Contains(lowerBody, "include_usage")
	if !hasField {
		return false
	}
	for _, marker := range []string{
		"unsupported",
		"unknown field",
		"unrecognized",
		"not allowed",
		"not permitted",
		"extra field",
		"extra_forbidden",
		"additional properties",
	} {
		if strings.Contains(lowerBody, marker) {
			return true
		}
	}
	return false
}

func parseOpenAISSE(ctx context.Context, source io.Reader, emit func(StreamChunk) error) (*Response, error) {
	scanner := bufio.NewScanner(source)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	var contentBuilder strings.Builder
	var thinkingBuilder strings.Builder
	toolCalls := make(map[int]*ToolCall)
	var usage Usage
	complete := false

	for scanner.Scan() {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		line := scanner.Text()
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		data := strings.TrimPrefix(line, "data:")
		data = strings.TrimPrefix(data, " ")
		if data == "[DONE]" {
			complete = true
			break
		}

		var chunk sseResponse
		if err := json.Unmarshal([]byte(data), &chunk); err != nil {
			slog.Warn("parse SSE chunk", "error", err, "data", data)
			continue
		}
		if chunk.Usage != nil {
			usage.PromptTokens = chunk.Usage.PromptTokens
			usage.CompletionTokens = chunk.Usage.CompletionTokens
			usage.CacheReadTokens = chunk.Usage.PromptDetails.CachedTokens
			usage.CacheReadIncludedInPrompt = chunk.Usage.PromptDetails.CachedTokens > 0
		}
		if len(chunk.Choices) == 0 {
			continue
		}

		delta := chunk.Choices[0].Delta
		thinkingBuilder.WriteString(delta.ReasoningContent)
		if delta.Content != "" {
			contentBuilder.WriteString(delta.Content)
			if emit != nil {
				if err := emit(StreamChunk{Content: delta.Content}); err != nil {
					return nil, err
				}
			}
		}
		for _, tc := range delta.ToolCalls {
			existing, ok := toolCalls[tc.Index]
			if !ok {
				toolCalls[tc.Index] = &ToolCall{
					ID:   tc.ID,
					Type: tc.Type,
					Function: FunctionCall{
						Name:      tc.Function.Name,
						Arguments: tc.Function.Arguments,
					},
				}
				continue
			}
			if tc.ID != "" {
				existing.ID = tc.ID
			}
			if tc.Type != "" {
				existing.Type = tc.Type
			}
			if tc.Function.Name != "" {
				existing.Function.Name += tc.Function.Name
			}
			existing.Function.Arguments += tc.Function.Arguments
		}
	}

	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("read stream: %w", err)
	}
	if !complete {
		return nil, io.ErrUnexpectedEOF
	}

	result := &Response{Content: contentBuilder.String(), Thinking: thinkingBuilder.String(), Usage: usage}
	for i := 0; i < len(toolCalls); i++ {
		if tc, ok := toolCalls[i]; ok {
			result.ToolCalls = append(result.ToolCalls, *tc)
		}
	}

	rawMsg := apiMessage{Role: "assistant", ReasoningContent: result.Thinking, ToolCalls: result.ToolCalls}
	rawMsg.Content, _ = json.Marshal(result.Content)
	result.RawAssistant, _ = json.Marshal(rawMsg)

	if emit != nil {
		if err := emit(StreamChunk{ToolCalls: result.ToolCalls, Thinking: result.Thinking, Done: true}); err != nil {
			return nil, err
		}
	}
	return result, nil
}

func (p *OpenAIProvider) parseSSE(reader io.Reader) (*Response, error) {
	return parseOpenAISSE(context.Background(), reader, nil)
}
