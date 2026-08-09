package gateway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/agent"
	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/config"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
	"github.com/fastclaw-ai/fastclaw/internal/store"
	"github.com/fastclaw-ai/fastclaw/internal/taskqueue"
)

type integrationOwnershipStore struct {
	store.Store
	agents map[string]store.AgentRecord
}

func (s *integrationOwnershipStore) GetAgent(_ context.Context, agentID string) (*store.AgentRecord, error) {
	record, ok := s.agents[agentID]
	if !ok {
		return nil, store.ErrNotFound
	}
	copy := record
	return &copy, nil
}

type integrationProvider struct {
	mu            sync.Mutex
	calls         []string
	blockWorker   bool
	workerStarted chan struct{}
	workerOnce    sync.Once
}

func newIntegrationProvider(blockWorker bool) *integrationProvider {
	return &integrationProvider{
		blockWorker:   blockWorker,
		workerStarted: make(chan struct{}),
	}
}

func (p *integrationProvider) Chat(
	ctx context.Context,
	messages []provider.Message,
	tools []provider.Tool,
	model string,
	_ int,
	_ float64,
) (*provider.Response, error) {
	return p.response(ctx, messages, tools, model)
}

func (p *integrationProvider) ChatStream(
	ctx context.Context,
	messages []provider.Message,
	tools []provider.Tool,
	model string,
	_ int,
	_ float64,
) (*provider.StreamReader, error) {
	response, err := p.response(ctx, messages, tools, model)
	if err != nil {
		return nil, err
	}
	chunks := make(chan provider.StreamChunk)
	reader := provider.NewStreamReader(chunks)
	reader.Complete(response, nil)
	close(chunks)
	return reader, nil
}

func (p *integrationProvider) response(
	ctx context.Context,
	messages []provider.Message,
	_ []provider.Tool,
	model string,
) (*provider.Response, error) {
	p.mu.Lock()
	p.calls = append(p.calls, model)
	p.mu.Unlock()

	switch model {
	case "test/coordinator":
		for _, message := range messages {
			if message.Role == "tool" && message.Name == "spawn_subagent" {
				return &provider.Response{
					Content: "coordinator received: " + message.Content,
					Usage:   provider.Usage{PromptTokens: 100, CompletionTokens: 10},
				}, nil
			}
		}
		return &provider.Response{
			Content: "delegating",
			Usage:   provider.Usage{PromptTokens: 100, CompletionTokens: 10},
			ToolCalls: []provider.ToolCall{{
				ID:   "delegate-1",
				Type: "function",
				Function: provider.FunctionCall{
					Name:      "spawn_subagent",
					Arguments: `{"agentId":"worker","task":"analyze the fixture"}`,
				},
			}},
		}, nil
	case "test/worker":
		if p.blockWorker {
			p.workerOnce.Do(func() { close(p.workerStarted) })
			<-ctx.Done()
			return nil, ctx.Err()
		}
		return &provider.Response{
			Content: "worker result",
			Usage:   provider.Usage{PromptTokens: 50, CompletionTokens: 5},
		}, nil
	default:
		return nil, fmt.Errorf("unexpected model %q", model)
	}
}

func (p *integrationProvider) callSequence() []string {
	p.mu.Lock()
	defer p.mu.Unlock()
	return append([]string(nil), p.calls...)
}

type subagentGatewayFixture struct {
	gateway  *Gateway
	agents   *agent.Manager
	provider *integrationProvider
	cancel   context.CancelFunc
	stopped  chan struct{}
}

func newSubagentGatewayFixture(
	t *testing.T,
	ownerUserID string,
	loadedAgentIDs []string,
	ownership map[string]string,
	blockWorker bool,
) *subagentGatewayFixture {
	t.Helper()

	home := t.TempDir()
	t.Setenv("FASTCLAW_HOME", home)
	messageBus := bus.New()
	fakeProvider := newIntegrationProvider(blockWorker)
	records := make(map[string]store.AgentRecord, len(ownership))
	for agentID, userID := range ownership {
		records[agentID] = store.AgentRecord{ID: agentID, UserID: userID, Name: agentID}
	}
	ownershipStore := &integrationOwnershipStore{agents: records}

	resolved := make([]config.ResolvedAgent, 0, len(loadedAgentIDs))
	for _, agentID := range loadedAgentIDs {
		agentHome := filepath.Join(home, "agents", agentID)
		if err := os.MkdirAll(agentHome, 0o755); err != nil {
			t.Fatal(err)
		}
		resolved = append(resolved, config.ResolvedAgent{
			ID:                agentID,
			UserID:            ownerUserID,
			Home:              agentHome,
			Workspace:         filepath.Join(agentHome, "workspace"),
			Model:             "test/" + agentID,
			MaxTokens:         256,
			MaxToolIterations: 4,
		})
	}
	manager, err := agent.NewManager(
		resolved,
		fakeProvider,
		messageBus,
		agent.WithUserID(ownerUserID),
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, runtimeAgent := range manager.All() {
		runtimeAgent.SetSubAgentSpawner(&gatewaySubAgentSpawner{
			bus:           messageBus,
			userID:        ownerUserID,
			sourceAgentID: runtimeAgent.Name(),
		})
	}

	registry := newUserSpaceRegistry(messageBus, ownershipStore, nil)
	registry.spaces[ownerUserID] = &userSpaceEntry{
		space: &UserSpace{
			UserID:   ownerUserID,
			Config:   &config.Config{},
			Provider: fakeProvider,
			Agents:   manager,
		},
		lastUsed: time.Now(),
	}
	gateway := &Gateway{
		bus:   messageBus,
		store: ownershipStore,
		users: registry,
	}
	gateway.taskQueue = taskqueue.NewQueue(1, 5*time.Second, func(ctx context.Context, task *taskqueue.Task) (string, error) {
		space, err := gateway.users.getOrLoad(ctx, task.OwnerUserID)
		if err != nil {
			return "", err
		}
		target := space.Agents.AgentByID(task.AgentID)
		if target == nil {
			return "", fmt.Errorf("agent %q not found", task.AgentID)
		}
		return target.HandleMessage(ctx, task.Message), nil
	})

	routerCtx, cancel := context.WithCancel(context.Background())
	stopped := make(chan struct{})
	go func() {
		defer close(stopped)
		gateway.processInbound(routerCtx)
	}()

	fixture := &subagentGatewayFixture{
		gateway:  gateway,
		agents:   manager,
		provider: fakeProvider,
		cancel:   cancel,
		stopped:  stopped,
	}
	t.Cleanup(func() {
		cancel()
		messageBus.StopInternal(context.Canceled)
		gateway.taskQueue.Stop()
		select {
		case <-stopped:
		case <-time.After(time.Second):
			t.Error("gateway router did not stop")
		}
	})
	return fixture
}

func TestIntegrationSubagentRoundTripThroughGateway(t *testing.T) {
	fixture := newSubagentGatewayFixture(
		t,
		"user-1",
		[]string{"coordinator", "worker"},
		map[string]string{"coordinator": "user-1", "worker": "user-1"},
		false,
	)

	collector := agent.NewModelUsageCollector("coordinator", map[string]agent.ModelPricing{
		"coordinator": {InputPerMillion: 1, OutputPerMillion: 2},
		"worker":      {InputPerMillion: 1, OutputPerMillion: 2},
	})
	ctx := agent.ContextWithModelUsageCollector(context.Background(), collector)
	result := fixture.agents.AgentByID("coordinator").HandleMessage(
		ctx,
		bus.InboundMessage{
			OwnerUserID: "user-1",
			Channel:     "test",
			ChatID:      "integration",
			Text:        "delegate this task",
			PeerKind:    "dm",
		},
	)

	const resultPrefix = "coordinator received: "
	if !strings.HasPrefix(result, resultPrefix) {
		t.Fatalf("result = %q", result)
	}
	var delegation struct {
		AgentID string `json:"agentId"`
		Status  string `json:"status"`
		Result  string `json:"result"`
	}
	if err := json.Unmarshal([]byte(strings.TrimPrefix(result, resultPrefix)), &delegation); err != nil ||
		delegation.AgentID != "worker" || delegation.Status != "success" || delegation.Result != "worker result" {
		t.Fatalf("structured delegation = %+v, err=%v", delegation, err)
	}
	if sequence := strings.Join(fixture.provider.callSequence(), ","); sequence != "test/coordinator,test/worker,test/coordinator" {
		t.Fatalf("provider call sequence = %s", sequence)
	}
	calls := collector.Snapshot()
	if len(calls) != 3 {
		t.Fatalf("model calls = %+v", calls)
	}
	var coordinatorTokens, subAgentTokens int
	for _, call := range calls {
		switch call.Role {
		case "coordinator":
			coordinatorTokens += call.TotalTokens
		case "subagent":
			subAgentTokens += call.TotalTokens
			if path := strings.Join(call.CallPath, ","); path != "coordinator,worker" {
				t.Fatalf("sub-agent usage call path = %q", path)
			}
		}
		if !call.Priced || call.EstimatedCostUSD <= 0 || call.LatencyMS < 0 {
			t.Fatalf("invalid model call metrics: %+v", call)
		}
	}
	if coordinatorTokens != 220 || subAgentTokens != 55 {
		t.Fatalf("token split coordinator=%d subagent=%d", coordinatorTokens, subAgentTokens)
	}

	tasks := fixture.gateway.taskQueue.RecentTasks(10)
	if len(tasks) != 1 {
		t.Fatalf("internal task count = %d, want 1", len(tasks))
	}
	task := tasks[0]
	if task.Status != taskqueue.TaskDone || task.ResponseMode != taskqueue.ResponseInternal {
		t.Fatalf("internal task status=%s mode=%d", task.Status, task.ResponseMode)
	}
	if task.SourceAgentID != "coordinator" || task.AgentID != "worker" {
		t.Fatalf("unexpected route %s -> %s", task.SourceAgentID, task.AgentID)
	}
	if path := strings.Join(task.CallPath, ","); path != "coordinator,worker" {
		t.Fatalf("call path = %s", path)
	}
}

func TestIntegrationSubagentRejectsCrossTenantTarget(t *testing.T) {
	fixture := newSubagentGatewayFixture(
		t,
		"user-1",
		[]string{"coordinator"},
		map[string]string{"coordinator": "user-1", "foreign-worker": "user-2"},
		false,
	)
	spawner := &gatewaySubAgentSpawner{
		bus:           fixture.gateway.bus,
		userID:        "user-1",
		sourceAgentID: "coordinator",
	}

	_, err := spawner.SpawnSubAgent(
		context.Background(),
		"foreign-worker",
		bus.InboundMessage{Text: "should be rejected"},
	)
	if err == nil || !strings.Contains(err.Error(), "target agent unavailable") {
		t.Fatalf("SpawnSubAgent() error = %v", err)
	}
	if tasks := fixture.gateway.taskQueue.RecentTasks(10); len(tasks) != 0 {
		t.Fatalf("cross-tenant request created %d tasks", len(tasks))
	}
}

func TestIntegrationSubagentCancellationPropagatesToTask(t *testing.T) {
	fixture := newSubagentGatewayFixture(
		t,
		"user-1",
		[]string{"coordinator", "worker"},
		map[string]string{"coordinator": "user-1", "worker": "user-1"},
		true,
	)
	spawner := &gatewaySubAgentSpawner{
		bus:           fixture.gateway.bus,
		userID:        "user-1",
		sourceAgentID: "coordinator",
	}
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() {
		_, err := spawner.SpawnSubAgent(ctx, "worker", bus.InboundMessage{Text: "block"})
		result <- err
	}()

	select {
	case <-fixture.provider.workerStarted:
	case <-time.After(time.Second):
		t.Fatal("worker did not start")
	}
	cancel()

	select {
	case err := <-result:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("SpawnSubAgent() error = %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancelled spawn did not return")
	}

	deadline := time.Now().Add(time.Second)
	for {
		tasks := fixture.gateway.taskQueue.RecentTasks(10)
		if len(tasks) == 1 && tasks[0].Status == taskqueue.TaskCancelled {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("task did not become cancelled: %+v", tasks)
		}
		time.Sleep(time.Millisecond)
	}
}
