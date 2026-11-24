package tools

import "context"

type ExecutionScope struct {
	UserID    string
	AgentID   string
	SessionID string
}

type executionScopeKey struct{}

func ContextWithExecutionScope(ctx context.Context, scope ExecutionScope) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, executionScopeKey{}, scope)
}

func ExecutionScopeFromContext(ctx context.Context) (ExecutionScope, bool) {
	if ctx == nil {
		return ExecutionScope{}, false
	}
	scope, ok := ctx.Value(executionScopeKey{}).(ExecutionScope)
	return scope, ok
}
