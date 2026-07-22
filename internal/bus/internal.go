package bus

import (
	"context"
	"errors"
	"fmt"
	"time"
)

var (
	ErrInternalStopped      = errors.New("message bus: internal requests stopped")
	ErrInternalBackpressure = errors.New("message bus: internal request capacity reached")
	ErrInternalCycle        = errors.New("message bus: sub-agent cycle detected")
)

const maxInternalPending = 256

// InternalRequest is a trusted runtime request targeting one specific agent.
type InternalRequest struct {
	OwnerUserID   string
	SourceAgentID string
	TargetAgentID string
	CallPath      []string
	Message       InboundMessage
}

// InternalDelivery is consumed only by the gateway internal router.
type InternalDelivery struct {
	CorrelationID string
	Request       InternalRequest
	Context       context.Context
}

// InternalReply completes one correlated internal request.
type InternalReply struct {
	CorrelationID string
	TaskID        string
	Result        string
	Err           error
}

type internalExecutionKey struct{}
type internalCallPathKey struct{}

// InternalExecutionIDFromContext returns the root queue execution ID, if any.
func InternalExecutionIDFromContext(ctx context.Context) string {
	value, _ := ctx.Value(internalExecutionKey{}).(string)
	return value
}

// ContextWithInternalExecution attaches an internal root execution ID.
func ContextWithInternalExecution(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, internalExecutionKey{}, id)
}

// InternalCallPathFromContext returns a defensive copy of the current path.
func InternalCallPathFromContext(ctx context.Context) []string {
	path, _ := ctx.Value(internalCallPathKey{}).([]string)
	return append([]string(nil), path...)
}

// ContextWithInternalCallPath attaches an immutable delegation path.
func ContextWithInternalCallPath(ctx context.Context, path []string) context.Context {
	return context.WithValue(ctx, internalCallPathKey{}, append([]string(nil), path...))
}

func internalLane(owner, agentID string) string { return owner + ":" + agentID }

// CallInternal publishes a trusted internal request and waits for its reply.
func (b *MessageBus) CallInternal(ctx context.Context, req InternalRequest) (InternalReply, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	if req.OwnerUserID == "" || req.SourceAgentID == "" || req.TargetAgentID == "" {
		return InternalReply{}, fmt.Errorf("message bus: owner, source, and target are required")
	}
	if req.SourceAgentID == req.TargetAgentID {
		return InternalReply{}, fmt.Errorf("%w: %s -> %s", ErrInternalCycle, req.SourceAgentID, req.TargetAgentID)
	}
	for _, id := range req.CallPath {
		if id == req.TargetAgentID {
			return InternalReply{}, fmt.Errorf("%w: %v -> %s", ErrInternalCycle, req.CallPath, req.TargetAgentID)
		}
	}

	correlationID := fmt.Sprintf("internal-%d-%d", time.Now().UnixNano(), b.internalSeq.Add(1))
	response := make(chan InternalReply, 1)
	sourceLane := internalLane(req.OwnerUserID, req.SourceAgentID)
	targetLane := internalLane(req.OwnerUserID, req.TargetAgentID)

	b.internalMu.Lock()
	if b.internalStopped {
		err := b.internalStopErr
		if err == nil {
			err = ErrInternalStopped
		}
		b.internalMu.Unlock()
		return InternalReply{}, err
	}
	if len(b.internalPending) >= maxInternalPending {
		b.internalMu.Unlock()
		return InternalReply{}, ErrInternalBackpressure
	}
	if b.waitPathExistsLocked(targetLane, sourceLane) {
		b.internalMu.Unlock()
		return InternalReply{}, fmt.Errorf("%w: %s -> %s", ErrInternalCycle, req.SourceAgentID, req.TargetAgentID)
	}
	b.internalPending[correlationID] = response
	if b.internalWaits[sourceLane] == nil {
		b.internalWaits[sourceLane] = make(map[string]int)
	}
	b.internalWaits[sourceLane][targetLane]++
	b.internalMu.Unlock()

	defer b.removeInternal(correlationID, sourceLane, targetLane)
	delivery := InternalDelivery{CorrelationID: correlationID, Request: req, Context: ctx}
	select {
	case b.Internal <- delivery:
	case <-ctx.Done():
		return InternalReply{}, ctx.Err()
	default:
		return InternalReply{}, ErrInternalBackpressure
	}

	select {
	case reply := <-response:
		if reply.Err != nil {
			return reply, reply.Err
		}
		return reply, nil
	case <-ctx.Done():
		return InternalReply{}, ctx.Err()
	}
}

// ResolveInternal completes a pending request. Late replies are ignored.
func (b *MessageBus) ResolveInternal(reply InternalReply) bool {
	b.internalMu.Lock()
	ch, ok := b.internalPending[reply.CorrelationID]
	if ok {
		delete(b.internalPending, reply.CorrelationID)
	}
	b.internalMu.Unlock()
	if !ok {
		return false
	}
	select {
	case ch <- reply:
	default:
	}
	return true
}

// StopInternal rejects new requests and releases every pending waiter.
func (b *MessageBus) StopInternal(err error) {
	if err == nil {
		err = ErrInternalStopped
	}
	b.internalMu.Lock()
	if b.internalStopped {
		b.internalMu.Unlock()
		return
	}
	b.internalStopped = true
	b.internalStopErr = err
	pending := b.internalPending
	b.internalPending = make(map[string]chan InternalReply)
	b.internalWaits = make(map[string]map[string]int)
	b.internalMu.Unlock()

	for id, ch := range pending {
		select {
		case ch <- InternalReply{CorrelationID: id, Err: err}:
		default:
		}
	}
}

func (b *MessageBus) removeInternal(correlationID, sourceLane, targetLane string) {
	b.internalMu.Lock()
	delete(b.internalPending, correlationID)
	if targets := b.internalWaits[sourceLane]; targets != nil {
		if targets[targetLane] <= 1 {
			delete(targets, targetLane)
		} else {
			targets[targetLane]--
		}
		if len(targets) == 0 {
			delete(b.internalWaits, sourceLane)
		}
	}
	b.internalMu.Unlock()
}

func (b *MessageBus) waitPathExistsLocked(from, target string) bool {
	seen := make(map[string]bool)
	var visit func(string) bool
	visit = func(node string) bool {
		if node == target {
			return true
		}
		if seen[node] {
			return false
		}
		seen[node] = true
		for next := range b.internalWaits[node] {
			if visit(next) {
				return true
			}
		}
		return false
	}
	return visit(from)
}
