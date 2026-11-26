package channels

import (
	"encoding/json"
	"testing"

	"github.com/fastclaw-ai/fastclaw/internal/bus"
	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

func TestTelegramReplyCarriesOriginalAndDeliveryIDs(t *testing.T) {
	var update tgbotapi.Update
	err := json.Unmarshal([]byte(`{"update_id":700,"message":{"message_id":104,"chat":{"id":-50,"type":"supergroup"},"from":{"id":9,"first_name":"A"},"text":"new detail","reply_to_message":{"message_id":101}}}`), &update)
	if err != nil {
		t.Fatal(err)
	}
	mb := bus.New()
	channel := &Telegram{accountID: "team-bot", bus: mb}
	for i := 0; i < 2; i++ {
		channel.handleUpdate(update)
		got := <-mb.Inbound
		if got.PeerKind != "group" || got.AccountID != "team-bot" || got.ChatID != "-50" || got.UserID != "9" || got.MessageID != "104" || got.ReplyToMsgID != "101" || got.Text != "new detail" {
			t.Fatalf("unexpected reply: %+v", got)
		}
	}
}
