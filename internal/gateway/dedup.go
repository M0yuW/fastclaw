package gateway

import (
	"context"
	"fmt"
	"time"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
)

const dedupTTL = 60 * time.Second

// dedupEntry tracks when a message was first seen.
type dedupEntry struct {
	seenAt time.Time
}

// isDuplicate returns true if this group message has already been seen.
func (g *Gateway) isDuplicate(msg bus.InboundMessage) bool {
	// Telegram supplies a stable message ID. Other adapters retain their text-based fallback.
	if msg.PeerKind != "group" {
		return false
	}
	key := fmt.Sprintf("%s:%s:%s:%x", msg.Channel, msg.ChatID, msg.UserID, hashString(msg.Text))
	if msg.Channel == "telegram" && msg.MessageID != "" {
		key = fmt.Sprintf("%q/%q/%q/%q/%q", msg.OwnerUserID, msg.Channel, msg.AccountID, msg.ChatID, msg.MessageID)
	}
	_, loaded := g.dedup.LoadOrStore(key, dedupEntry{seenAt: time.Now()})
	return loaded
}

// cleanupDedup periodically removes expired entries from the dedup cache.
func (g *Gateway) cleanupDedup(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			now := time.Now()
			g.dedup.Range(func(key, value any) bool {
				entry := value.(dedupEntry)
				if now.Sub(entry.seenAt) > dedupTTL {
					g.dedup.Delete(key)
				}
				return true
			})
		}
	}
}

func hashString(s string) uint32 {
	var h uint32
	for _, c := range s {
		h = h*31 + uint32(c)
	}
	return h
}
