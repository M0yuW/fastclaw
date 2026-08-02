package provider

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"sync"
	"testing"
)

type failingReader struct {
	data []byte
	err  error
}

func (r *failingReader) Read(p []byte) (int, error) {
	if len(r.data) > 0 {
		n := copy(p, r.data)
		r.data = r.data[n:]
		return n, nil
	}
	return 0, r.err
}

func openAIFixture() string {
	return strings.Join([]string{
		`data: {"choices":[{"delta":{"role":"assistant","reasoning_content":"rea","content":"hel"},"finish_reason":""}]}`,
		`data: {"choices":[{"delta":{"reasoning_content":"son","content":"lo","tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"get_","arguments":"{\"x\":"}}]},"finish_reason":""}]}`,
		`data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"weather","arguments":"1}"}}]},"finish_reason":"tool_calls"}]}`,
		`data: {"choices":[],"usage":{"prompt_tokens":120,"completion_tokens":18,"prompt_tokens_details":{"cached_tokens":40}}}`,
		`data: [DONE]`, "",
	}, "\n")
}

func anthropicFixture() string {
	return strings.Join([]string{
		`data: {"type":"message_start","message":{"usage":{"input_tokens":90,"output_tokens":0,"cache_read_input_tokens":30,"cache_creation_input_tokens":10}}}`,
		`data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking"}}`,
		`data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"reason"}}`,
		`data: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"sig"}}`,
		`data: {"type":"content_block_start","index":1,"content_block":{"type":"text","text":"hel"}}`,
		`data: {"type":"content_block_delta","index":1,"delta":{"type":"text_delta","text":"lo"}}`,
		`data: {"type":"content_block_start","index":2,"content_block":{"type":"tool_use","id":"tool_1","name":"lookup","input":{}}}`,
		`data: {"type":"content_block_delta","index":2,"delta":{"type":"input_json_delta","partial_json":"{\"q\":"}}`,
		`data: {"type":"content_block_delta","index":2,"delta":{"type":"input_json_delta","partial_json":"1}"}}`,
		`data: {"type":"message_delta","usage":{"output_tokens":22}}`,
		`data: {"type":"message_stop"}`, "",
	}, "\n")
}

func collectEmitted(t *testing.T, parse func(func(StreamChunk) error) (*Response, error)) (*Response, []StreamChunk) {
	t.Helper()
	var chunks []StreamChunk
	got, err := parse(func(chunk StreamChunk) error { chunks = append(chunks, chunk); return nil })
	if err != nil {
		t.Fatal(err)
	}
	return got, chunks
}

func TestOpenAISSEStreamingResultEqualsChatResult(t *testing.T) {
	fixture := openAIFixture()
	chat, err := parseOpenAISSE(context.Background(), strings.NewReader(fixture), nil)
	if err != nil {
		t.Fatal(err)
	}
	stream, chunks := collectEmitted(t, func(emit func(StreamChunk) error) (*Response, error) {
		return parseOpenAISSE(context.Background(), strings.NewReader(fixture), emit)
	})
	if !reflect.DeepEqual(chat, stream) {
		t.Fatalf("results differ:\nchat=%+v\nstream=%+v", chat, stream)
	}
	if stream.Content != "hello" || stream.Thinking != "reason" || len(stream.ToolCalls) != 1 || stream.ToolCalls[0].Function.Arguments != `{"x":1}` {
		t.Fatalf("unexpected result: %+v", stream)
	}
	if stream.Usage.PromptTokens != 120 || stream.Usage.CompletionTokens != 18 || stream.Usage.CacheReadTokens != 40 {
		t.Fatalf("unexpected usage: %+v", stream.Usage)
	}
	if len(stream.RawAssistant) == 0 {
		t.Fatal("missing raw assistant")
	}
	if len(chunks) != 3 || !chunks[2].Done {
		t.Fatalf("unexpected chunks: %+v", chunks)
	}
}

func TestOpenAIProviderAppliesExplicitDeepSeekThinkingMode(t *testing.T) {
	openAIProvider := NewOpenAI("test-key", "https://api.deepseek.com")
	request, err := openAIProvider.buildRequestWithUsage(
		ContextWithThinkingMode(t.Context(), "off"),
		[]Message{{Role: "user", Content: "hello"}},
		nil,
		"deepseek/deepseek-v4-flash",
		100,
		0,
		true,
		true,
	)
	if err != nil {
		t.Fatal(err)
	}
	var body map[string]any
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	thinking, _ := body["thinking"].(map[string]any)
	if thinking["type"] != "disabled" {
		t.Fatalf("thinking = %+v", body["thinking"])
	}
	if _, exists := body["reasoning_effort"]; exists {
		t.Fatalf("disabled request unexpectedly set reasoning_effort: %+v", body)
	}
}

func TestOpenAIProviderPreservesThinkingDefaultForOtherProviders(t *testing.T) {
	openAIProvider := NewOpenAI("test-key", "https://example.com/v1")
	request, err := openAIProvider.buildRequestWithUsage(
		ContextWithThinkingMode(t.Context(), "off"),
		[]Message{{Role: "user", Content: "hello"}},
		nil,
		"compatible-model",
		100,
		0,
		true,
		true,
	)
	if err != nil {
		t.Fatal(err)
	}
	var body map[string]any
	if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if _, exists := body["thinking"]; exists {
		t.Fatalf("non-DeepSeek request unexpectedly set thinking: %+v", body)
	}
}

func TestOpenAIProviderFallsBackWhenStreamingUsageIsUnsupported(t *testing.T) {
	for _, status := range []int{http.StatusBadRequest, http.StatusUnprocessableEntity} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			var calls int
			server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
				calls++
				var body map[string]any
				if err := json.NewDecoder(request.Body).Decode(&body); err != nil {
					t.Error(err)
					http.Error(writer, err.Error(), http.StatusBadRequest)
					return
				}
				if _, included := body["stream_options"]; included {
					http.Error(writer, `unsupported field "stream_options"`, status)
					return
				}
				writer.Header().Set("Content-Type", "text/event-stream")
				_, _ = writer.Write([]byte(strings.Join([]string{
					`data: {"choices":[{"delta":{"content":"fallback"},"finish_reason":"stop"}]}`,
					`data: [DONE]`,
					"",
				}, "\n")))
			}))
			defer server.Close()

			openAIProvider := NewOpenAI("test-key", server.URL)
			stream, err := openAIProvider.ChatStream(
				t.Context(),
				[]Message{{Role: "user", Content: "hello"}},
				nil,
				"test-model",
				100,
				0,
			)
			if err != nil {
				t.Fatal(err)
			}
			for {
				if _, ok := stream.Next(); !ok {
					break
				}
			}
			result, err := stream.Result()
			if err != nil {
				t.Fatal(err)
			}
			if calls != 2 || result.Content != "fallback" || result.Usage.TotalTokens() != 0 {
				t.Fatalf("calls=%d result=%+v", calls, result)
			}
		})
	}
}

func TestOpenAIProviderDoesNotRetryAmbiguousStreamingUsageError(t *testing.T) {
	var calls int
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, _ *http.Request) {
		calls++
		http.Error(
			writer,
			"stream_options requires a provider-specific account setting",
			http.StatusBadRequest,
		)
	}))
	defer server.Close()

	openAIProvider := NewOpenAI("test-key", server.URL)
	_, err := openAIProvider.ChatStream(
		t.Context(),
		[]Message{{Role: "user", Content: "hello"}},
		nil,
		"test-model",
		100,
		0,
	)
	if err == nil || !strings.Contains(err.Error(), "stream_options requires") {
		t.Fatalf("ChatStream() error = %v", err)
	}
	if calls != 1 {
		t.Fatalf("calls = %d, want 1", calls)
	}
}

func TestAnthropicSSEStreamingResultEqualsChatResult(t *testing.T) {
	fixture := anthropicFixture()
	chat, err := parseAnthropicSSE(context.Background(), strings.NewReader(fixture), nil)
	if err != nil {
		t.Fatal(err)
	}
	stream, chunks := collectEmitted(t, func(emit func(StreamChunk) error) (*Response, error) {
		return parseAnthropicSSE(context.Background(), strings.NewReader(fixture), emit)
	})
	if !reflect.DeepEqual(chat, stream) {
		t.Fatalf("results differ:\nchat=%+v\nstream=%+v", chat, stream)
	}
	if stream.Content != "hello" || stream.Thinking != "reason" || len(stream.ToolCalls) != 1 || stream.ToolCalls[0].Function.Arguments != `{"q":1}` {
		t.Fatalf("unexpected result: %+v", stream)
	}
	if stream.Usage.PromptTokens != 90 ||
		stream.Usage.CompletionTokens != 22 ||
		stream.Usage.CacheReadTokens != 30 ||
		stream.Usage.CacheCreationTokens != 10 {
		t.Fatalf("unexpected usage: %+v", stream.Usage)
	}
	var raw map[string]any
	if err := json.Unmarshal(stream.RawAssistant, &raw); err != nil || raw["signature"] != "sig" {
		t.Fatalf("bad raw assistant %s: %v", stream.RawAssistant, err)
	}
	if len(chunks) != 3 || !chunks[2].Done || chunks[2].ThinkingSignature != "sig" {
		t.Fatalf("unexpected chunks: %+v", chunks)
	}
}

func TestSSEParsersRejectIncompleteAndReadErrors(t *testing.T) {
	parsers := map[string]func(context.Context, io.Reader) (*Response, error){
		"openai":    func(ctx context.Context, r io.Reader) (*Response, error) { return parseOpenAISSE(ctx, r, nil) },
		"anthropic": func(ctx context.Context, r io.Reader) (*Response, error) { return parseAnthropicSSE(ctx, r, nil) },
	}
	for name, parse := range parsers {
		t.Run(name+" EOF", func(t *testing.T) {
			if result, err := parse(context.Background(), strings.NewReader("data: {}\n")); result != nil || !errors.Is(err, io.ErrUnexpectedEOF) {
				t.Fatalf("result=%+v err=%v", result, err)
			}
		})
		t.Run(name+" scanner", func(t *testing.T) {
			boom := errors.New("boom")
			if result, err := parse(context.Background(), &failingReader{data: []byte("data: {}\n"), err: boom}); result != nil || !errors.Is(err, boom) {
				t.Fatalf("result=%+v err=%v", result, err)
			}
		})
		t.Run(name+" canceled", func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			cancel()
			if result, err := parse(ctx, strings.NewReader(openAIFixture())); result != nil || !errors.Is(err, context.Canceled) {
				t.Fatalf("result=%+v err=%v", result, err)
			}
		})
	}
}

func TestStreamReaderTerminalStateIsConcurrentSafe(t *testing.T) {
	ch := make(chan StreamChunk, 1)
	reader := NewStreamReader(ch)
	want := &Response{Content: "done"}
	reader.setResult(want, nil)
	ch <- StreamChunk{Done: true}
	close(ch)
	var wg sync.WaitGroup
	for range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range 100 {
				got, err := reader.Result()
				if err != nil || got != want || reader.Err() != nil {
					t.Errorf("result=%+v err=%v", got, err)
					return
				}
			}
		}()
	}
	wg.Wait()
	for {
		if _, ok := reader.Next(); !ok {
			break
		}
	}
	if got, err := reader.Result(); got != want || err != nil {
		t.Fatalf("terminal result=%+v err=%v", got, err)
	}
}
