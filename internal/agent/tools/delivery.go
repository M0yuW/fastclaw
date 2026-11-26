package tools

import (
	"context"
	"encoding/json"
	"errors"
	"slices"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

type deliveryOptions struct {
	Mode    string   `json:"mode"`
	Targets []string `json:"targets,omitempty"`
	AsOf    string   `json:"asOf,omitempty"`
}

func deliverySchema() map[string]any {
	return map[string]any{
		"type":        "object",
		"description": "Configure before delegation. Use targeted with agent IDs or broadcast for all participants. asOf limits the publication date. Use seal before final synthesis.",
		"properties": map[string]any{
			"mode":    map[string]any{"enum": []string{"summary", "targeted", "broadcast", "seal"}},
			"targets": map[string]any{"type": "array", "items": map[string]string{"type": "string"}},
			"asOf":    map[string]string{"type": "string", "format": "date-time"},
		},
		"required": []string{"mode"},
	}

}
func configureDelivery(ctx context.Context, opt deliveryOptions) (string, error) {
	state, _ := evidenceFor(ctx)
	if state == nil || len(bus.InternalCallPathFromContext(ctx)) > 1 {
		return "", errors.New("delivery requires a coordinator task")
	}
	state.mu.Lock()
	defer state.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if opt.Mode == "seal" && len(opt.Targets) == 0 && opt.AsOf == "" {
		state.sealed = true
		data, _ := json.Marshal(map[string]int{"cutoff": len(state.events) + 1})
		return string(data), nil
	}
	if state.started || state.sealed {
		return "", errors.New("configure delivery before delegation")
	}
	if (opt.Mode != "summary" && opt.Mode != "targeted" && opt.Mode != "broadcast") || ((opt.Mode == "targeted") != (len(opt.Targets) > 0)) || slices.Contains(opt.Targets, "") {
		return "", errors.New("invalid delivery mode or targets")
	}
	var cutoff time.Time
	if opt.AsOf != "" {
		var err error
		cutoff, err = time.Parse(time.RFC3339, opt.AsOf)
		if err != nil {
			return "", err
		}
	}
	state.delivery = opt
	state.asOf = cutoff
	return "Evidence delivery configured", nil
}
func CloseTaskEvidence(ctx context.Context) {
	state, _ := evidenceFor(ctx)
	if state != nil && len(bus.InternalCallPathFromContext(ctx)) <= 1 {
		state.mu.Lock()
		state.sealed = true
		state.mu.Unlock()
	}
}
