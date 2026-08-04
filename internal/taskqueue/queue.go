package taskqueue

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"sort"
	"sync"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

// TaskStatus represents the current state of a task.
type TaskStatus string

const (
	TaskPending   TaskStatus = "pending"
	TaskRunning   TaskStatus = "running"
	TaskDone      TaskStatus = "done"
	TaskFailed    TaskStatus = "failed"
	TaskCancelled TaskStatus = "cancelled"
)

type ResponseMode uint8

const (
	ResponseExternal ResponseMode = iota
	ResponseInternal
)

type TaskResult struct {
	TaskID string
	Value  string
	Err    error
}

type InternalTaskSpec struct {
	AgentID       string
	OwnerUserID   string
	SourceAgentID string
	CorrelationID string
	ChatKey       string
	ParentChatKey string
	Message       bus.InboundMessage
	CallPath      []string
}

// Task represents a unit of work to be processed.
type Task struct {
	ID            string
	AgentID       string
	OwnerUserID   string // owner of the agent (for user-space lookup)
	ChatKey       string // channel:chatID — serialization key
	Message       bus.InboundMessage
	AccountID     string
	Status        TaskStatus
	CreatedAt     time.Time
	StartedAt     *time.Time
	DoneAt        *time.Time
	Result        string
	Error         error
	ResponseMode  ResponseMode
	CorrelationID string
	SourceAgentID string
	CallPath      []string
	ParentChatKey string
	requestCtx    context.Context
	completion    func(TaskResult)
	completeOnce  sync.Once
	internalSlot  bool
}

// TaskHandler processes a task and returns a result or error.
type TaskHandler func(ctx context.Context, task *Task) (string, error)

// chatQueue is a per-chat FIFO queue with its own processing goroutine.
type chatQueue struct {
	ch       chan *Task
	lastUsed time.Time
}

// Queue manages task submission, per-chat serialization, and global concurrency.
type Queue struct {
	maxConcurrent int
	taskTimeout   time.Duration
	idleTimeout   time.Duration

	mu            sync.Mutex
	tasks         map[string]*Task      // taskID -> Task
	chatQueues    map[string]*chatQueue // chatKey -> chatQueue
	sem           chan struct{}         // counting semaphore for root executions
	internalSlots chan struct{}         // bounds queued/running internal tasks
	handler       TaskHandler
	seq           uint64 // task ID sequence
	ctx           context.Context
	cancel        context.CancelFunc
}

// NewQueue creates a new task queue.
func NewQueue(maxConcurrent int, taskTimeout time.Duration, handler TaskHandler) *Queue {
	if maxConcurrent <= 0 {
		maxConcurrent = 10
	}
	if taskTimeout <= 0 {
		taskTimeout = 5 * time.Minute
	}

	ctx, cancel := context.WithCancel(context.Background())

	q := &Queue{
		maxConcurrent: maxConcurrent,
		taskTimeout:   taskTimeout,
		idleTimeout:   5 * time.Minute,
		tasks:         make(map[string]*Task),
		chatQueues:    make(map[string]*chatQueue),
		sem:           make(chan struct{}, maxConcurrent),
		internalSlots: make(chan struct{}, 256),
		handler:       handler,
		ctx:           ctx,
		cancel:        cancel,
	}

	// Start idle cleanup goroutine
	go q.cleanupIdleQueues()

	return q
}

// Submit adds an external task to the queue for processing.
func (q *Queue) Submit(agentID, chatKey string, msg bus.InboundMessage, accountID string) string {
	task := &Task{
		AgentID:      agentID,
		OwnerUserID:  msg.OwnerUserID,
		ChatKey:      chatKey,
		Message:      msg,
		AccountID:    accountID,
		ResponseMode: ResponseExternal,
	}
	id, _ := q.submit(context.Background(), task)
	return id
}

// SubmitInternal queues a trusted internal task and completes it exactly once.
func (q *Queue) SubmitInternal(ctx context.Context, spec InternalTaskSpec, complete func(TaskResult)) (string, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	if q.handler == nil {
		return "", fmt.Errorf("taskqueue: handler is required")
	}
	if spec.AgentID == "" || spec.OwnerUserID == "" || spec.SourceAgentID == "" || spec.CorrelationID == "" {
		return "", fmt.Errorf("taskqueue: incomplete internal task spec")
	}
	if spec.ChatKey == "" || spec.ChatKey == spec.ParentChatKey {
		return "", fmt.Errorf("taskqueue: invalid reentrant internal chat key")
	}
	select {
	case q.internalSlots <- struct{}{}:
	case <-ctx.Done():
		return "", ctx.Err()
	case <-q.ctx.Done():
		return "", fmt.Errorf("taskqueue: stopped")
	default:
		return "", fmt.Errorf("taskqueue: internal capacity reached")
	}
	task := &Task{
		AgentID:       spec.AgentID,
		OwnerUserID:   spec.OwnerUserID,
		ChatKey:       spec.ChatKey,
		Message:       spec.Message,
		ResponseMode:  ResponseInternal,
		CorrelationID: spec.CorrelationID,
		SourceAgentID: spec.SourceAgentID,
		CallPath:      append([]string(nil), spec.CallPath...),
		ParentChatKey: spec.ParentChatKey,
		requestCtx:    ctx,
		completion:    complete,
		internalSlot:  true,
	}
	id, err := q.submit(ctx, task)
	return id, err
}

func (q *Queue) submit(ctx context.Context, task *Task) (string, error) {
	q.mu.Lock()
	select {
	case <-q.ctx.Done():
		q.mu.Unlock()
		err := fmt.Errorf("taskqueue: stopped")
		q.finishTask(task, "", err)
		return "", err
	default:
	}

	q.seq++
	taskID := fmt.Sprintf("task-%d-%d", time.Now().UnixMilli(), q.seq)
	task.ID = taskID
	task.Status = TaskPending
	task.CreatedAt = time.Now()
	q.tasks[taskID] = task

	cq, ok := q.chatQueues[task.ChatKey]
	if !ok {
		cq = &chatQueue{ch: make(chan *Task, 100), lastUsed: time.Now()}
		q.chatQueues[task.ChatKey] = cq
		go q.processChatQueue(task.ChatKey, cq)
	}
	cq.lastUsed = time.Now()
	pendingCount := len(cq.ch)
	q.mu.Unlock()

	slog.Info("task submitted", "task_id", taskID, "chat_key", task.ChatKey,
		"agent_id", task.AgentID, "queue_depth", pendingCount+1,
		"internal", task.ResponseMode == ResponseInternal)

	select {
	case cq.ch <- task:
		return taskID, nil
	case <-ctx.Done():
		q.failBeforeRun(task, ctx.Err())
		return "", ctx.Err()
	case <-q.ctx.Done():
		err := fmt.Errorf("taskqueue: stopped")
		q.failBeforeRun(task, err)
		return "", err
	}
}

// processChatQueue drains tasks for a single chat, running them serially.
func (q *Queue) processChatQueue(chatKey string, cq *chatQueue) {
	for {
		select {
		case <-q.ctx.Done():
			return
		case task, ok := <-cq.ch:
			if !ok {
				return
			}
			q.executeTask(task)

			q.mu.Lock()
			cq.lastUsed = time.Now()
			q.mu.Unlock()
		}
	}
}

// executeTask runs a single task with concurrency control and timeout.
func (q *Queue) executeTask(task *Task) {
	requestCtx := task.requestCtx
	if requestCtx == nil {
		requestCtx = q.ctx
	}
	inheritedExecution := bus.InternalExecutionIDFromContext(requestCtx)
	acquired := false
	if inheritedExecution == "" {
		select {
		case q.sem <- struct{}{}:
			acquired = true
		case <-requestCtx.Done():
			q.finishTask(task, "", requestCtx.Err())
			return
		case <-q.ctx.Done():
			q.finishTask(task, "", fmt.Errorf("taskqueue: stopped"))
			return
		}
		inheritedExecution = task.ID
	}
	if acquired {
		defer func() { <-q.sem }()
	}

	now := time.Now()
	q.mu.Lock()
	task.Status = TaskRunning
	task.StartedAt = &now
	concurrent := len(q.sem)
	q.mu.Unlock()

	slog.Info("task started", "task_id", task.ID, "agent_id", task.AgentID,
		"chat_key", task.ChatKey, "concurrent_count", concurrent,
		"execution_id", inheritedExecution, "internal", task.ResponseMode == ResponseInternal)

	baseCtx, baseCancel := context.WithCancel(context.WithoutCancel(requestCtx))
	stopQueue := context.AfterFunc(q.ctx, baseCancel)
	stopRequest := context.AfterFunc(requestCtx, baseCancel)
	defer func() {
		stopQueue()
		stopRequest()
		baseCancel()
	}()
	ctx, cancel := context.WithTimeout(baseCtx, q.taskTimeout)
	defer cancel()
	ctx = bus.ContextWithInternalExecution(ctx, inheritedExecution)
	if len(task.CallPath) > 0 {
		ctx = bus.ContextWithInternalCallPath(ctx, task.CallPath)
	}

	var result string
	var err error
	func() {
		defer func() {
			if recovered := recover(); recovered != nil {
				err = fmt.Errorf("task panic: %v", recovered)
			}
		}()
		result, err = q.handler(ctx, task)
	}()
	if err == nil && ctx.Err() != nil {
		err = ctx.Err()
	}
	q.finishTask(task, result, err)
}

func (q *Queue) finishTask(task *Task, result string, err error) {
	task.completeOnce.Do(func() {
		doneAt := time.Now()
		q.mu.Lock()
		task.DoneAt = &doneAt
		task.Result = result
		task.Error = err
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			task.Status = TaskCancelled
		} else if err != nil {
			task.Status = TaskFailed
		} else {
			task.Status = TaskDone
		}
		started := task.StartedAt
		completion := task.completion
		task.completion = nil
		task.requestCtx = nil
		q.mu.Unlock()

		duration := time.Duration(0)
		if started != nil {
			duration = doneAt.Sub(*started)
		}
		if err != nil {
			slog.Error("task failed", "task_id", task.ID, "agent_id", task.AgentID,
				"chat_key", task.ChatKey, "duration_ms", duration.Milliseconds(), "error", err)
		} else {
			slog.Info("task completed", "task_id", task.ID, "agent_id", task.AgentID,
				"chat_key", task.ChatKey, "duration_ms", duration.Milliseconds())
		}
		if completion != nil {
			func() {
				defer func() {
					if recovered := recover(); recovered != nil {
						slog.Error("task completion callback panicked", "task_id", task.ID, "panic", recovered)
					}
				}()
				completion(TaskResult{TaskID: task.ID, Value: result, Err: err})
			}()
		}
		if task.internalSlot {
			<-q.internalSlots
		}
	})
}

func (q *Queue) failBeforeRun(task *Task, err error) {
	q.finishTask(task, "", err)
}

// cleanupIdleQueues removes chat queues that have been idle too long.
func (q *Queue) cleanupIdleQueues() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-q.ctx.Done():
			return
		case <-ticker.C:
			q.mu.Lock()
			now := time.Now()
			for key, cq := range q.chatQueues {
				if now.Sub(cq.lastUsed) > q.idleTimeout && len(cq.ch) == 0 {
					close(cq.ch)
					delete(q.chatQueues, key)
					slog.Debug("idle chat queue removed", "chat_key", key)
				}
			}
			q.mu.Unlock()
		}
	}
}

// RecentTasks returns recent tasks for observability, newest first.
func (q *Queue) RecentTasks(limit int) []*Task {
	q.mu.Lock()
	defer q.mu.Unlock()

	all := make([]*Task, 0, len(q.tasks))
	for _, t := range q.tasks {
		all = append(all, snapshotTask(t))
	}

	sort.Slice(all, func(i, j int) bool {
		return all[i].CreatedAt.After(all[j].CreatedAt)
	})

	if limit > 0 && len(all) > limit {
		all = all[:limit]
	}

	// Prune old completed tasks (keep last 200)
	if len(q.tasks) > 200 {
		go q.pruneOldTasks()
	}

	return all
}

func snapshotTask(task *Task) *Task {
	message := task.Message
	message.Mentions = append([]string(nil), task.Message.Mentions...)
	message.PhotoURLs = append([]string(nil), task.Message.PhotoURLs...)
	return &Task{
		ID:            task.ID,
		AgentID:       task.AgentID,
		OwnerUserID:   task.OwnerUserID,
		ChatKey:       task.ChatKey,
		Message:       message,
		AccountID:     task.AccountID,
		Status:        task.Status,
		CreatedAt:     task.CreatedAt,
		StartedAt:     copyTime(task.StartedAt),
		DoneAt:        copyTime(task.DoneAt),
		Result:        task.Result,
		Error:         task.Error,
		ResponseMode:  task.ResponseMode,
		CorrelationID: task.CorrelationID,
		SourceAgentID: task.SourceAgentID,
		CallPath:      append([]string(nil), task.CallPath...),
		ParentChatKey: task.ParentChatKey,
	}
}

func copyTime(value *time.Time) *time.Time {
	if value == nil {
		return nil
	}
	copy := *value
	return &copy
}

// pruneOldTasks removes completed tasks beyond the retention limit.
func (q *Queue) pruneOldTasks() {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.tasks) <= 200 {
		return
	}

	// Collect completed tasks sorted by creation time
	type entry struct {
		id        string
		createdAt time.Time
	}
	var completed []entry
	for id, t := range q.tasks {
		if t.Status == TaskDone || t.Status == TaskFailed || t.Status == TaskCancelled {
			completed = append(completed, entry{id, t.CreatedAt})
		}
	}

	sort.Slice(completed, func(i, j int) bool {
		return completed[i].createdAt.Before(completed[j].createdAt)
	})

	// Remove oldest completed tasks to get below 200
	toRemove := len(q.tasks) - 200
	for i := 0; i < toRemove && i < len(completed); i++ {
		delete(q.tasks, completed[i].id)
	}
}

// Stop shuts down the queue.
func (q *Queue) Stop() {
	q.cancel()
	q.mu.Lock()
	var pending []*Task
	for _, task := range q.tasks {
		if task.Status == TaskPending {
			pending = append(pending, task)
		}
	}
	q.mu.Unlock()
	for _, task := range pending {
		q.finishTask(task, "", context.Canceled)
	}
}
