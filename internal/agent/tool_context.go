package agent

import (
	"context"

	"github.com/fastclaw-ai/fastclaw/internal/agent/tools"
)

type requestToolRegistryKey struct{}

// ContextWithToolRegistry replaces the tools available for one agent turn.
// The registry is request-scoped and does not modify the agent's shared tools.
func ContextWithToolRegistry(ctx context.Context, registry *tools.Registry) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, requestToolRegistryKey{}, registry)
}

func toolRegistryFromContext(ctx context.Context, fallback *tools.Registry) *tools.Registry {
	if ctx != nil {
		if registry, ok := ctx.Value(requestToolRegistryKey{}).(*tools.Registry); ok && registry != nil {
			return registry
		}
	}
	return fallback
}
