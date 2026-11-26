package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestDeliveryBoundary(t *testing.T) {
	for _, mode := range []string{"targeted", "broadcast", "summary"} {
		t.Run(mode, func(t *testing.T) {
			root := ContextWithExecutionScope(bus.ContextWithInternalExecution(context.Background(), "root"), ExecutionScope{UserID: "owner", AgentID: "coord"})
			root = StartTaskEvidence(root, "owner", false)
			opt := deliveryOptions{Mode: mode, AsOf: "2020-01-01T00:00:00Z"}
			if mode == "targeted" {
				opt.Targets = []string{"b"}
			}
			if _, err := configureDelivery(root, opt); err != nil {
				t.Fatal(err)
			}
			child := func(id string) context.Context {
				return ContextWithExecutionScope(bus.ContextWithInternalCallPath(root, []string{"coord", id}), ExecutionScope{UserID: "owner", AgentID: id})
			}
			base := []provider.Message{{Role: "tool", Content: "original"}}
			sent := PrepareEvidenceInput(child("b"), base)
			const prior = "2019-12-31T23:59:59Z"
			makeEvent := func(i int, public string) []byte {
				raw, _ := json.Marshal(fact{Key: fmt.Sprint(i), Content: fmt.Sprintf("announcement-%d", i), Source: "fixture", PublishedAt: public})
				return raw
			}
			for _, public := range []string{"", "2020-01-01T00:00:01Z"} {
				if _, err := publishEvidence(child("a"), makeEvent(9, public)); err == nil {
					t.Fatal("accepted future or undated event")
				}
			}
			canceled, stop := context.WithCancel(child("a"))
			stop()
			if _, err := publishEvidence(canceled, makeEvent(8, prior)); err == nil {
				t.Fatal("accepted cancelled write")
			}
			var wg sync.WaitGroup
			for _, n := range []int{0, 1, 0} {
				wg.Add(1)
				go func() {
					defer wg.Done()
					if _, err := publishEvidence(child("a"), makeEvent(n, prior)); err != nil {
						t.Error(err)
					}
				}()
			}
			wg.Wait()
			if sent[0].Content != "original" {
				t.Fatal("mutated in-flight input")
			}
			for _, id := range []string{"b", "c"} {
				next := PrepareEvidenceInput(child(id), base)
				want := mode == "broadcast" || mode == "targeted" && id == "b"
				if strings.Contains(next[0].Content, "announcement-0") != want || strings.Contains(next[0].Content, "announcement-1") != want {
					t.Fatal(next)
				}
				RecordEvidenceInput(child(id), next, 2)
			}
			cutoff, err := configureDelivery(root, deliveryOptions{Mode: "seal"})
			if err != nil || cutoff != `{"cutoff":3}` {
				t.Fatal(cutoff, err)
			}
			if _, err = publishEvidence(child("a"), makeEvent(2, prior)); err == nil {
				t.Fatal("accepted late event")
			}
			if _, err = publishEvidence(child("a"), makeEvent(0, prior)); err != nil {
				t.Fatal("retry after cutoff", err)
			}
			state, _ := evidenceFor(root)
			if state.events[0].Version != 2 || state.events[1].Version != 3 {
				t.Fatal(state.events)
			}
		})
	}
}
