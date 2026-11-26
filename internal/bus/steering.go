package bus

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

// Steering records instructions and retry receipts for one root task.
type Steering struct {
	mu       sync.Mutex
	closed   bool
	messages []string
	receipts map[string]int
}

func (s *Steering) Add(id, text string) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if id == "" || strings.TrimSpace(text) == "" {
		return 0, fmt.Errorf("补充内容或消息编号为空")
	}
	if n := s.receipts[id]; n > 0 {
		if s.messages[n-1] != text {
			return 0, fmt.Errorf("同一消息编号的内容不同")
		}
		return n, nil
	}
	if s.closed {
		return 0, fmt.Errorf("任务已结束，请发起新任务")
	}
	if s.receipts == nil {
		s.receipts = make(map[string]int)
	}
	s.messages = append(s.messages, text)
	n := len(s.messages)
	s.receipts[id] = n
	return n, nil
}

func (s *Steering) Snapshot() []string {
	if s == nil {
		return nil
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]string(nil), s.messages...)
}

func (s *Steering) Current(version int) bool {
	if s == nil {
		return true
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return version == len(s.messages)
}

// Finish closes the task only if the model saw every accepted instruction.
func (s *Steering) Finish(version int) bool {
	if s == nil {
		return true
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if version != len(s.messages) {
		return false
	}
	s.closed = true
	return true
}

func (s *Steering) Close() {
	if s != nil {
		s.mu.Lock()
		s.closed = true
		s.mu.Unlock()
	}
}

type steeringKey struct{}

func WithSteering(ctx context.Context, s *Steering) context.Context {
	return context.WithValue(ctx, steeringKey{}, s)
}
func SteeringFrom(ctx context.Context) *Steering {
	s, _ := ctx.Value(steeringKey{}).(*Steering)
	return s
}
