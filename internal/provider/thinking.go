package provider

import "context"

type thinkingModeContextKey struct{}

// ContextWithThinkingMode carries an agent's explicit provider-level thinking
// preference to compatible providers. An empty mode preserves provider defaults.
func ContextWithThinkingMode(ctx context.Context, mode string) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	return context.WithValue(ctx, thinkingModeContextKey{}, mode)
}

func thinkingModeFromContext(ctx context.Context) string {
	if ctx == nil {
		return ""
	}
	mode, _ := ctx.Value(thinkingModeContextKey{}).(string)
	return mode
}
