package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"math"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	"github.com/fastclaw-ai/fastclaw/internal/auth"
	"github.com/fastclaw-ai/fastclaw/internal/config"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

type traceIntegrationProvider struct {
	mu        sync.Mutex
	callCount int
	tools     []provider.Tool
}

func (providerStub *traceIntegrationProvider) Chat(
	context.Context,
	[]provider.Message,
	[]provider.Tool,
	string,
	int,
	float64,
) (*provider.Response, error) {
	return nil, errors.New("Chat must not be called")
}

func (providerStub *traceIntegrationProvider) ChatStream(
	_ context.Context,
	_ []provider.Message,
	tools []provider.Tool,
	_ string,
	_ int,
	_ float64,
) (*provider.StreamReader, error) {
	providerStub.mu.Lock()
	defer providerStub.mu.Unlock()
	providerStub.callCount++
	providerStub.tools = append([]provider.Tool(nil), tools...)

	chunks := make(chan provider.StreamChunk)
	close(chunks)
	reader := provider.NewStreamReader(chunks)
	if providerStub.callCount == 1 {
		reader.Complete(&provider.Response{
			Usage: provider.Usage{PromptTokens: 100, CompletionTokens: 10},
			ToolCalls: []provider.ToolCall{
				{
					ID:   "call-1",
					Type: "function",
					Function: provider.FunctionCall{
						Name:      "math.gcd",
						Arguments: `{"num1":40,"num2":50}`,
					},
				},
			},
		}, nil)
	} else {
		reader.Complete(&provider.Response{
			Content: "The result is 10.",
			Usage:   provider.Usage{PromptTokens: 120, CompletionTokens: 20},
		}, nil)
	}
	return reader, nil
}

type traceIntegrationResolver struct {
	manager *agent.Manager
}

func withAPIIdentity(request *http.Request, userID string, agents ...string) *http.Request {
	identity := auth.Identity{
		UserID:       userID,
		AuthMethod:   "apikey",
		APIKeyID:     "test-key",
		APIKeyAgents: append([]string(nil), agents...),
	}
	return request.WithContext(auth.WithIdentity(request.Context(), identity))
}

func (resolver *traceIntegrationResolver) UserSpaceFor(userID string) (*UserSpaceView, error) {
	return &UserSpaceView{UserID: userID, Agents: resolver.manager}, nil
}

func (resolver *traceIntegrationResolver) LocalAgentManager() *agent.Manager {
	return resolver.manager
}

func (resolver *traceIntegrationResolver) IsCloudMode() bool {
	return false
}

func TestIntegrationChatCompletionsReturnsRequestToolTrace(t *testing.T) {
	providerStub := &traceIntegrationProvider{}
	home := t.TempDir()
	manager, err := agent.NewManager(
		[]config.ResolvedAgent{
			{
				ID:                "eval-agent",
				Home:              home,
				Workspace:         home,
				Model:             "fake/model",
				MaxTokens:         128,
				MaxToolIterations: 4,
			},
		},
		providerStub,
		nil,
		agent.WithUserID("user-1"),
	)
	if err != nil {
		t.Fatal(err)
	}
	server := NewServer(&traceIntegrationResolver{manager: manager}, nil, nil)
	body := []byte(`{
		"messages":[{"role":"user","content":"Calculate the GCD of 40 and 50."}],
		"stream":false,
		"tools":[{
			"type":"function",
			"function":{
				"name":"math.gcd",
				"description":"Calculate a GCD.",
				"parameters":{
					"type":"dict",
					"properties":{"num1":{"type":"integer"},"num2":{"type":"integer"}},
					"required":["num1","num2"]
				}
			}
		}],
		"fastclaw":{
			"eval":true,
			"include_trace":true,
			"include_usage_breakdown":true,
			"pricing":{"fake/model":{"input_per_million":1,"output_per_million":2}},
			"tool_results":{"math.gcd":"10"}
		}
	}`)
	request := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
	request = withAPIIdentity(request, "user-1", "eval-agent")
	response := httptest.NewRecorder()

	server.HandleChatCompletions(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	var completion chatCompletionResponse
	if err := json.NewDecoder(response.Body).Decode(&completion); err != nil {
		t.Fatal(err)
	}
	if completion.FastClaw == nil || len(completion.FastClaw.Trace) != 2 {
		t.Fatalf("missing trace: %+v", completion.FastClaw)
	}
	if completion.Usage.TotalTokens != 250 ||
		len(completion.FastClaw.ModelCalls) != 2 ||
		completion.FastClaw.ModelCalls[0].Role != "coordinator" {
		t.Fatalf("unexpected usage breakdown: usage=%+v metadata=%+v", completion.Usage, completion.FastClaw)
	}
	if cost := completion.FastClaw.ModelCalls[0].EstimatedCostUSD +
		completion.FastClaw.ModelCalls[1].EstimatedCostUSD; math.Abs(cost-0.00028) > 1e-12 {
		t.Fatalf("estimated cost = %.8f", cost)
	}
	if completion.FastClaw.Trace[0].Name != "math.gcd" ||
		completion.FastClaw.Trace[0].Arguments != `{"num1":40,"num2":50}` {
		t.Fatalf("unexpected trace: %+v", completion.FastClaw.Trace)
	}
	if len(providerStub.tools) != 1 || providerStub.tools[0].Function.Name != "math.gcd" {
		t.Fatalf("request-scoped tools were not used: %+v", providerStub.tools)
	}
	parameters := providerStub.tools[0].Function.Parameters.(map[string]any)
	if parameters["type"] != "object" {
		t.Fatalf("schema type = %v", parameters["type"])
	}
}

type stateIntegrationProvider struct {
	callCount int
}

func (providerStub *stateIntegrationProvider) Chat(
	context.Context,
	[]provider.Message,
	[]provider.Tool,
	string,
	int,
	float64,
) (*provider.Response, error) {
	return nil, errors.New("Chat must not be called")
}

func (providerStub *stateIntegrationProvider) ChatStream(
	_ context.Context,
	_ []provider.Message,
	_ []provider.Tool,
	_ string,
	_ int,
	_ float64,
) (*provider.StreamReader, error) {
	providerStub.callCount++
	chunks := make(chan provider.StreamChunk)
	close(chunks)
	reader := provider.NewStreamReader(chunks)
	if providerStub.callCount == 1 {
		reader.Complete(&provider.Response{
			ToolCalls: []provider.ToolCall{
				{
					ID:   "call-1",
					Type: "function",
					Function: provider.FunctionCall{
						Name:      "cancel_order",
						Arguments: `{"order_id":"ord-1"}`,
					},
				},
			},
		}, nil)
	} else {
		reader.Complete(&provider.Response{Content: "Order ord-1 was cancelled."}, nil)
	}
	return reader, nil
}

func TestIntegrationChatCompletionsExecutesStatefulEvalTool(t *testing.T) {
	providerStub := &stateIntegrationProvider{}
	home := t.TempDir()
	manager, err := agent.NewManager(
		[]config.ResolvedAgent{
			{
				ID:                "eval-agent",
				Home:              home,
				Workspace:         home,
				Model:             "fake/model",
				MaxTokens:         128,
				MaxToolIterations: 4,
			},
		},
		providerStub,
		nil,
		agent.WithUserID("user-1"),
	)
	if err != nil {
		t.Fatal(err)
	}
	server := NewServer(&traceIntegrationResolver{manager: manager}, nil, nil)
	body := []byte(`{
		"messages":[{"role":"user","content":"I confirm cancellation of ord-1."}],
		"stream":false,
		"tools":[{
			"type":"function",
			"function":{
				"name":"cancel_order",
				"description":"Cancel a pending order.",
				"parameters":{
					"type":"object",
					"properties":{"order_id":{"type":"string"}},
					"required":["order_id"]
				}
			}
		}],
		"fastclaw":{
			"eval":true,
			"include_trace":true,
			"state":{"orders":{"ord-1":{"status":"pending"}}},
			"tool_behaviors":{
				"cancel_order":{
					"conditions":[{
						"path":"orders.{order_id}.status",
						"equals":"pending"
					}],
					"updates":[{
						"path":"orders.{order_id}.status",
						"value":"cancelled"
					}],
					"result_path":"orders.{order_id}"
				}
			}
		}
	}`)
	request := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
	request = withAPIIdentity(request, "user-1", "eval-agent")
	response := httptest.NewRecorder()

	server.HandleChatCompletions(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	var completion chatCompletionResponse
	if err := json.NewDecoder(response.Body).Decode(&completion); err != nil {
		t.Fatal(err)
	}
	if completion.FastClaw == nil {
		t.Fatal("fastclaw metadata is nil")
	}
	status, exists := lookupStatePath(completion.FastClaw.State, "orders.ord-1.status")
	if !exists || status != "cancelled" {
		t.Fatalf("state status = %v, exists = %v", status, exists)
	}
	if len(completion.FastClaw.Trace) != 2 ||
		completion.FastClaw.Trace[1].Result != `{"status":"cancelled"}` {
		t.Fatalf("unexpected trace: %+v", completion.FastClaw.Trace)
	}
}

type isolatedToolsProvider struct {
	toolCount int
}

func (providerStub *isolatedToolsProvider) Chat(
	context.Context,
	[]provider.Message,
	[]provider.Tool,
	string,
	int,
	float64,
) (*provider.Response, error) {
	return nil, errors.New("Chat must not be called")
}

func (providerStub *isolatedToolsProvider) ChatStream(
	_ context.Context,
	_ []provider.Message,
	tools []provider.Tool,
	_ string,
	_ int,
	_ float64,
) (*provider.StreamReader, error) {
	providerStub.toolCount = len(tools)
	chunks := make(chan provider.StreamChunk)
	close(chunks)
	reader := provider.NewStreamReader(chunks)
	reader.Complete(&provider.Response{Content: "solo answer"}, nil)
	return reader, nil
}

func TestIntegrationChatCompletionsCanIsolateAllAgentTools(t *testing.T) {
	providerStub := &isolatedToolsProvider{}
	home := t.TempDir()
	manager, err := agent.NewManager(
		[]config.ResolvedAgent{
			{
				ID:                "eval-agent",
				Home:              home,
				Workspace:         home,
				Model:             "fake/model",
				MaxTokens:         128,
				MaxToolIterations: 4,
			},
		},
		providerStub,
		nil,
		agent.WithUserID("user-1"),
	)
	if err != nil {
		t.Fatal(err)
	}
	server := NewServer(&traceIntegrationResolver{manager: manager}, nil, nil)
	body := []byte(`{
		"messages":[{"role":"user","content":"Answer without tools."}],
		"stream":false,
		"fastclaw":{
			"eval":true,
			"isolate_tools":true
		}
	}`)
	request := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
	request = withAPIIdentity(request, "user-1", "eval-agent")
	response := httptest.NewRecorder()

	server.HandleChatCompletions(response, request)
	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if providerStub.toolCount != 0 {
		t.Fatalf("isolated tool count = %d", providerStub.toolCount)
	}
}

func TestIntegrationChatCompletionsEnforcesResolvedAgentACL(t *testing.T) {
	providerStub := &isolatedToolsProvider{}
	home := t.TempDir()
	manager, err := agent.NewManager(
		[]config.ResolvedAgent{
			{
				ID:                "default-agent",
				Home:              home,
				Workspace:         home,
				Model:             "fake/model",
				MaxTokens:         128,
				MaxToolIterations: 4,
			},
			{
				ID:                "allowed-agent",
				Home:              home,
				Workspace:         home,
				Model:             "fake/model",
				MaxTokens:         128,
				MaxToolIterations: 4,
			},
		},
		providerStub,
		nil,
		agent.WithUserID("user-1"),
	)
	if err != nil {
		t.Fatal(err)
	}
	server := NewServer(&traceIntegrationResolver{manager: manager}, nil, nil)
	body := []byte(`{"messages":[{"role":"user","content":"Answer briefly."}],"stream":false}`)

	tests := []struct {
		name       string
		agentID    string
		agents     []string
		wantStatus int
	}{
		{name: "omitted header cannot reach an inaccessible fallback", wantStatus: http.StatusForbidden},
		{name: "explicit inaccessible agent is denied", agentID: "default-agent", agents: []string{"allowed-agent"}, wantStatus: http.StatusForbidden},
		{name: "unknown explicit agent does not fall back", agentID: "missing-agent", agents: []string{"allowed-agent"}, wantStatus: http.StatusNotFound},
		{name: "explicit authorized agent is allowed", agentID: "allowed-agent", agents: []string{"allowed-agent"}, wantStatus: http.StatusOK},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			request := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", bytes.NewReader(body))
			request = withAPIIdentity(request, "user-1", test.agents...)
			if test.agentID != "" {
				request.Header.Set("x-fastclaw-agent-id", test.agentID)
			}
			response := httptest.NewRecorder()

			server.HandleChatCompletions(response, request)
			if response.Code != test.wantStatus {
				t.Fatalf("status = %d, want %d, body = %s", response.Code, test.wantStatus, response.Body.String())
			}
		})
	}
}
