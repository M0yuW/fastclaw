package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/privacy"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

// chatCompletionRequest mirrors the OpenAI chat completion request.
type chatCompletionRequest struct {
	Model    string                  `json:"model"`
	Messages []chatMessage           `json:"messages"`
	Stream   *bool                   `json:"stream,omitempty"`
	Tools    []provider.Tool         `json:"tools,omitempty"`
	FastClaw *fastClawRequestOptions `json:"fastclaw,omitempty"`
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// chatCompletionChunk is a single SSE chunk in streaming mode.
type chatCompletionChunk struct {
	ID      string        `json:"id"`
	Object  string        `json:"object"`
	Created int64         `json:"created"`
	Model   string        `json:"model"`
	Choices []chunkChoice `json:"choices"`
}

type chunkChoice struct {
	Index        int        `json:"index"`
	Delta        chunkDelta `json:"delta"`
	FinishReason *string    `json:"finish_reason"`
}

type chunkDelta struct {
	Role    string `json:"role,omitempty"`
	Content string `json:"content,omitempty"`
}

// chatCompletionResponse is the non-streaming response.
type chatCompletionResponse struct {
	ID       string              `json:"id"`
	Object   string              `json:"object"`
	Created  int64               `json:"created"`
	Model    string              `json:"model"`
	Choices  []completionChoice  `json:"choices"`
	Usage    completionUsage     `json:"usage"`
	FastClaw *completionMetadata `json:"fastclaw,omitempty"`
}

type completionChoice struct {
	Index        int         `json:"index"`
	Message      chatMessage `json:"message"`
	FinishReason string      `json:"finish_reason"`
}

type completionUsage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// HandleChatCompletions handles POST /v1/chat/completions.
func (s *Server) HandleChatCompletions(w http.ResponseWriter, r *http.Request) {
	var req chatCompletionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]string{"message": "invalid request body", "type": "invalid_request_error"},
		})
		return
	}

	if len(req.Messages) == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]string{"message": "messages is required", "type": "invalid_request_error"},
		})
		return
	}

	// Resolve the caller's user space (set by authMiddleware) and pick an
	// agent out of it.
	space, err := s.userSpaceFor(r)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]any{
			"error": map[string]string{"message": err.Error(), "type": "authentication_error"},
		})
		return
	}

	agentID := r.Header.Get("x-fastclaw-agent-id")
	ag := resolveAgent(space, agentID)
	if ag == nil {
		writeJSON(w, http.StatusNotFound, map[string]any{
			"error": map[string]string{"message": "agent not found", "type": "not_found_error"},
		})
		return
	}

	// Build session key from header
	sessionKey := r.Header.Get("x-fastclaw-session-key")
	if sessionKey == "" {
		sessionKey = "api-" + fmt.Sprintf("%d", time.Now().UnixNano())
	}

	// Extract the last user message
	var userText string
	for i := len(req.Messages) - 1; i >= 0; i-- {
		if req.Messages[i].Role == "user" {
			userText = req.Messages[i].Content
			break
		}
	}
	if userText == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]string{"message": "no user message found", "type": "invalid_request_error"},
		})
		return
	}

	// Scan before building the InboundMessage so the payload never reaches the
	// agent loop. Error shape follows the OpenAI spec so existing OpenAI clients
	// can handle it without special-casing this endpoint.
	if threat := privacy.ScanInput(userText); threat != nil {
		slog.Warn("completions blocked: prompt injection detected",
			"threat_type", threat.Type, "pattern", threat.Pattern, "context", threat.Context)
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]string{"message": "message blocked: potential prompt injection detected", "type": "invalid_request_error"},
		})
		return
	}

	// Build inbound message
	msg := bus.InboundMessage{
		Channel:  "api",
		ChatID:   sessionKey,
		UserID:   "api-user",
		Text:     userText,
		PeerKind: "dm",
	}

	slog.Info("chat completion request",
		"agent", ag.Name(),
		"session", sessionKey,
		"stream", req.Stream != nil && *req.Stream,
	)

	model := ag.Model()
	if req.Model != "" {
		model = req.Model
	}
	chatID := fmt.Sprintf("chatcmpl-%d", time.Now().UnixNano())
	now := time.Now().Unix()

	isStream := req.Stream != nil && *req.Stream
	if isStream && req.FastClaw != nil &&
		(req.FastClaw.State != nil || len(req.FastClaw.ToolBehaviors) > 0) {
		writeJSON(w, http.StatusBadRequest, map[string]any{
			"error": map[string]string{"message": "stateful eval tools require stream=false", "type": "invalid_request_error"},
		})
		return
	}
	agentCtx := r.Context()
	var snapshotState func() map[string]any
	var usageCollector *agent.ModelUsageCollector
	if !isStream && req.FastClaw != nil && req.FastClaw.IncludeUsageBreakdown {
		if !req.FastClaw.Eval {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"error": map[string]string{"message": "usage breakdown requires fastclaw.eval=true", "type": "invalid_request_error"},
			})
			return
		}
		usageCollector = agent.NewModelUsageCollector(ag.Name(), req.FastClaw.Pricing)
		agentCtx = agent.ContextWithModelUsageCollector(agentCtx, usageCollector)
	}
	useRequestTools := len(req.Tools) > 0 || (req.FastClaw != nil && req.FastClaw.IsolateTools)
	if useRequestTools {
		if req.FastClaw == nil || !req.FastClaw.Eval {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"error": map[string]string{"message": "isolated request tools require fastclaw.eval=true", "type": "invalid_request_error"},
			})
			return
		}
		registry, snapshot, registryErr := buildRequestToolEnvironment(
			req.Tools,
			req.FastClaw.ToolResults,
			req.FastClaw.State,
			req.FastClaw.ToolBehaviors,
		)
		if registryErr != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{
				"error": map[string]string{"message": registryErr.Error(), "type": "invalid_request_error"},
			})
			return
		}
		agentCtx = agent.ContextWithToolRegistry(agentCtx, registry)
		snapshotState = snapshot
	}
	if isStream {
		s.streamResponseFromAgent(w, r, agentCtx, ag, msg, chatID, model, now)
	} else {
		var finishTrace func() []completionTraceEvent
		if req.FastClaw != nil && req.FastClaw.IncludeTrace {
			agentCtx, finishTrace = startTraceCapture(agentCtx)
		}
		reply := ag.HandleMessage(agentCtx, msg)
		var trace []completionTraceEvent
		if finishTrace != nil {
			trace = finishTrace()
		}
		var state map[string]any
		if snapshotState != nil {
			state = snapshotState()
		}
		var modelCalls []agent.ModelCallUsage
		if usageCollector != nil {
			modelCalls = usageCollector.Snapshot()
		}
		s.fullResponse(w, reply, chatID, model, now, trace, state, modelCalls)
	}
}

func (s *Server) streamResponseFromAgent(w http.ResponseWriter, r *http.Request, ctx context.Context, ag *agent.Agent, msg bus.InboundMessage, chatID, model string, created int64) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)

	sr := ag.HandleMessageStream(ctx, msg)

	// Send role chunk
	s.writeSSEChunk(w, chatID, model, created, "assistant", "", nil)
	if ok {
		flusher.Flush()
	}

	// Forward chunks from StreamReader
	for {
		chunk, more := sr.Next()
		if chunk.Content != "" {
			s.writeSSEChunk(w, chatID, model, created, "", chunk.Content, nil)
			if ok {
				flusher.Flush()
			}
		}
		if chunk.Done || !more {
			break
		}
	}

	// Do not report a successful OpenAI terminal chunk for a cancelled or
	// failed agent stream. The connection closes and clients treat it as
	// truncated instead of accepting a partial answer as complete.
	if err := sr.Err(); err != nil {
		slog.Warn("agent stream failed", "chat_id", chatID, "error", err)
		return
	}

	// Send finish chunk
	done := "stop"
	s.writeSSEChunk(w, chatID, model, created, "", "", &done)
	fmt.Fprint(w, "data: [DONE]\n\n")
	if ok {
		flusher.Flush()
	}
}

func (s *Server) writeSSEChunk(w http.ResponseWriter, id, model string, created int64, role, content string, finishReason *string) {
	chunk := chatCompletionChunk{
		ID:      id,
		Object:  "chat.completion.chunk",
		Created: created,
		Model:   model,
		Choices: []chunkChoice{
			{
				Index: 0,
				Delta: chunkDelta{
					Role:    role,
					Content: content,
				},
				FinishReason: finishReason,
			},
		},
	}
	data, _ := json.Marshal(chunk)
	fmt.Fprintf(w, "data: %s\n\n", data)
}

func (s *Server) fullResponse(
	w http.ResponseWriter,
	reply, chatID, model string,
	created int64,
	trace []completionTraceEvent,
	state map[string]any,
	modelCalls []agent.ModelCallUsage,
) {
	usage := completionUsageFromModelCalls(modelCalls)
	resp := chatCompletionResponse{
		ID:      chatID,
		Object:  "chat.completion",
		Created: created,
		Model:   model,
		Choices: []completionChoice{
			{
				Index:        0,
				Message:      chatMessage{Role: "assistant", Content: reply},
				FinishReason: "stop",
			},
		},
		Usage: usage,
	}
	if len(trace) > 0 || state != nil || len(modelCalls) > 0 {
		resp.FastClaw = &completionMetadata{Trace: trace, State: state, ModelCalls: modelCalls}
	}
	writeJSON(w, http.StatusOK, resp)
}

func completionUsageFromModelCalls(calls []agent.ModelCallUsage) completionUsage {
	var usage completionUsage
	for _, call := range calls {
		usage.PromptTokens += call.PromptTokens
		usage.CompletionTokens += call.CompletionTokens
		usage.TotalTokens += call.TotalTokens
	}
	return usage
}

// resolveAgent picks an agent out of the caller's user space, preferring an
// explicit agent ID from the x-fastclaw-agent-id header and falling back to
// the default / first agent.
func resolveAgent(space *UserSpaceView, agentID string) *agent.Agent {
	mgr := space.Agents
	if agentID != "" {
		if ag := mgr.AgentByID(agentID); ag != nil {
			return ag
		}
	}
	if def := mgr.DefaultAgent(); def != nil {
		return def
	}
	all := mgr.All()
	if len(all) > 0 {
		return all[0]
	}
	return nil
}
