package taskqueue

import (
	"context"
	"fmt"
	"sort"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

// TestSmallSyntheticSchedulerLoad measures queue behavior without a model or external tool.
// Timing values are descriptive: only ordering, admission, and completion are asserted.
func TestSmallSyntheticSchedulerLoad(t *testing.T) {
	const (
		chats        = 12
		tasksPerChat = 4
		serviceTime  = 15 * time.Millisecond
	)
	for _, capacity := range []int{1, 4} {
		t.Run(fmt.Sprintf("root_capacity_%d", capacity), func(t *testing.T) {
			var active, peak atomic.Int32
			var orderMu sync.Mutex
			order := make(map[string][]string, chats)
			q := NewQueue(capacity, 5*time.Second, func(ctx context.Context, task *Task) (string, error) {
				current := active.Add(1)
				for old := peak.Load(); current > old; old = peak.Load() {
					if peak.CompareAndSwap(old, current) {
						break
					}
				}
				defer active.Add(-1)

				orderMu.Lock()
				order[task.ChatKey] = append(order[task.ChatKey], task.Message.Text)
				orderMu.Unlock()

				timer := time.NewTimer(serviceTime)
				defer timer.Stop()
				select {
				case <-timer.C:
					return "ok", nil
				case <-ctx.Done():
					return "", ctx.Err()
				}
			})
			t.Cleanup(q.Stop)

			completed := make(chan TaskResult, chats*tasksPerChat)
			started := time.Now()
			for sequence := 0; sequence < tasksPerChat; sequence++ {
				for chat := 0; chat < chats; chat++ {
					chatKey := fmt.Sprintf("load:chat-%02d", chat)
					_, err := q.SubmitInternal(context.Background(), InternalTaskSpec{
						AgentID:       "load-worker",
						OwnerUserID:   "load-user",
						SourceAgentID: "load-root",
						CorrelationID: fmt.Sprintf("load-%02d-%d", chat, sequence),
						ChatKey:       chatKey,
						Message:       bus.InboundMessage{Text: fmt.Sprintf("%d", sequence)},
					}, func(result TaskResult) { completed <- result })
					if err != nil {
						t.Fatalf("submit chat %d sequence %d: %v", chat, sequence, err)
					}
				}
			}
			for i := 0; i < chats*tasksPerChat; i++ {
				select {
				case result := <-completed:
					if result.Err != nil || result.Value != "ok" {
						t.Fatalf("completion %d: %+v", i, result)
					}
				case <-time.After(10 * time.Second):
					t.Fatalf("timed out after %d completions", i)
				}
			}
			elapsed := time.Since(started)

			if got := peak.Load(); got > int32(capacity) || got < 1 {
				t.Fatalf("peak concurrent handlers = %d, capacity = %d", got, capacity)
			}
			for chat := 0; chat < chats; chat++ {
				chatKey := fmt.Sprintf("load:chat-%02d", chat)
				got := order[chatKey]
				if len(got) != tasksPerChat {
					t.Fatalf("%s started %d tasks, want %d", chatKey, len(got), tasksPerChat)
				}
				for sequence, value := range got {
					if value != fmt.Sprintf("%d", sequence) {
						t.Fatalf("%s start order = %v", chatKey, got)
					}
				}
			}

			waits := make([]time.Duration, 0, chats*tasksPerChat)
			for _, task := range q.RecentTasks(0) {
				if task.Status != TaskDone || task.StartedAt == nil || task.DoneAt == nil {
					t.Fatalf("unfinished task: id=%s status=%s", task.ID, task.Status)
				}
				waits = append(waits, task.StartedAt.Sub(task.CreatedAt))
			}
			if len(waits) != chats*tasksPerChat {
				t.Fatalf("recorded %d tasks, want %d", len(waits), chats*tasksPerChat)
			}
			sort.Slice(waits, func(i, j int) bool { return waits[i] < waits[j] })
			percentile := func(p float64) time.Duration {
				index := int(float64(len(waits)-1) * p)
				return waits[index]
			}
			t.Logf("tasks=%d chats=%d capacity=%d peak=%d elapsed=%s throughput=%.1f tasks/s queue_wait_p50=%s queue_wait_p95=%s",
				len(waits), chats, capacity, peak.Load(), elapsed.Round(time.Millisecond),
				float64(len(waits))/elapsed.Seconds(), percentile(0.50).Round(time.Millisecond), percentile(0.95).Round(time.Millisecond))
		})
	}
}
