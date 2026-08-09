package agent

import "context"

type modelOverrideContextKey struct{}

// ContextWithModelOverride applies an explicit provider-facing model to the
// current turn and all internal sub-agent calls that inherit its context. It is
// wired only for authenticated eval requests.
func ContextWithModelOverride(ctx context.Context, model string) context.Context {
	if ctx == nil || model == "" {
		return ctx
	}
	return context.WithValue(ctx, modelOverrideContextKey{}, model)
}

func modelFromContext(ctx context.Context, fallback string) string {
	if ctx != nil {
		if model, ok := ctx.Value(modelOverrideContextKey{}).(string); ok && model != "" {
			return model
		}
	}
	return fallback
}
