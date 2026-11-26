package gateway

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	"github.com/fastclaw-ai/fastclaw/internal/config"
	"github.com/fastclaw-ai/fastclaw/internal/provider"
)

func TestTelegramConcurrentQuestionsAndReplyRetries(t *testing.T) {
	f := newSubagentGatewayFixture(t, "owner", []string{"coord"}, map[string]string{"coord": "owner"}, false)
	space, err := f.gateway.users.getOrLoad(context.Background(), "owner")
	if err != nil {
		t.Fatal(err)
	}
	space.Config.Teams = map[string]config.TeamEntry{"team": {Agents: []string{"coord"}, DefaultAgent: "coord", GroupBehavior: "default-agent"}}
	inputs := make(chan []provider.Message, 4)
	release := make(chan struct{})
	f.provider.script = func(ctx context.Context, m []provider.Message, _ string) (*provider.Response, error) {
		inputs <- append([]provider.Message(nil), m...)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-release:
		}
		for _, msg := range m {
			if msg.Role == "user" && (msg.Content == "A-only" || msg.Content == "B-only") {
				return &provider.Response{Content: "answer to " + msg.Content}, nil
			}
		}
		return &provider.Response{Content: "obsolete draft"}, nil
	}
	send := func(who, id, parent, text string) {
		t.Helper()
		f.gateway.bus.Inbound <- bus.InboundMessage{OwnerUserID: "owner", Channel: "telegram", PeerKind: "group", AccountID: "bot", ChatID: "G", UserID: who, MessageID: id, ReplyToMsgID: parent, Text: text}
	}
	read := func() []provider.Message {
		t.Helper()
		select {
		case m := <-inputs:
			return m
		case <-time.After(3 * time.Second):
			t.Fatal("missing provider request")
			return nil
		}
	}
	receipt := func(who, id, parent, text string) string {
		t.Helper()
		send(who, id, parent, text)
		select {
		case reply := <-f.gateway.bus.Outbound:
			if reply.ReplyToMsgID != id {
				t.Fatal(reply)
			}
			return reply.Text
		case <-time.After(2 * time.Second):
			t.Fatal("missing receipt")
			return ""
		}
	}
	send("A", "101", "", "same question")
	read()
	send("B", "102", "", "same question")
	if !strings.Contains(receipt("B", "103", "101", "forbidden"), "只有") {
		t.Fatal("foreign edit accepted")
	}
	ack := receipt("A", "104", "101", "A-only")
	if ack != receipt("A", "104", "101", "A-only") || !strings.Contains(ack, "第 1 条") {
		t.Fatal(ack)
	}
	if got := receipt("B", "105", "102", "B-only"); got == ack || !strings.Contains(got, "第 1 条") {
		t.Fatal(got)
	}
	close(release)
	for _, want := range []string{"A-only", "B-only"} {
		seen := map[string]int{}
		for _, msg := range read() {
			if msg.Role == "user" {
				seen[msg.Content]++
			}
		}
		if seen[want] != 1 || seen["A-only"]+seen["B-only"] != 1 || seen["forbidden"] != 0 {
			t.Fatal(want, seen)
		}
	}
	deadline := time.Now().Add(2 * time.Second)
	for {
		tasks := f.gateway.taskQueue.RecentTasks(10)
		if len(tasks) == 2 && tasks[0].DoneAt != nil && tasks[1].DoneAt != nil {
			for _, task := range tasks {
				if task.Result != "answer to "+task.Message.UserID+"-only" {
					t.Fatalf("unexpected final answer for %s: %q", task.Message.UserID, task.Result)
				}
			}
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("tasks did not finish")
		}
		time.Sleep(time.Millisecond)
	}
	if ack != receipt("A", "104", "101", "A-only") {
		t.Fatal("lost receipt after completion")
	}
	if !strings.Contains(receipt("A", "106", "101", "too late"), "已结束") {
		t.Fatal("late edit accepted")
	}
}
