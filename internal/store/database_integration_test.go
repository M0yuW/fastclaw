package store

import (
	"context"
	"errors"
	"path/filepath"
	"testing"
	"time"
)

func TestIntegrationSQLitePersistenceAndUserCascade(t *testing.T) {
	ctx := context.Background()
	dsn := "file:" + filepath.Join(t.TempDir(), "store.db") + "?_fk=1"
	dataStore, err := New(&StorageConfig{
		Type:        StorageSQLite,
		DSN:         dsn,
		AutoMigrate: true,
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}

	user := &UserRecord{
		ID:           "user-1",
		Username:     "developer",
		Email:        "developer@example.com",
		PasswordHash: "hash",
		Role:         "user",
		Status:       "active",
	}
	if err := dataStore.CreateUser(ctx, user); err != nil {
		t.Fatal(err)
	}
	agent := &AgentRecord{ID: "agent-1", UserID: user.ID, Name: "tester"}
	if err := dataStore.SaveAgent(ctx, agent); err != nil {
		t.Fatal(err)
	}
	if err := dataStore.SaveSession(ctx, user.ID, agent.ID, "web_case", &SessionRecord{
		Messages: []SessionMessage{{Role: "user", Content: "persist me"}},
	}); err != nil {
		t.Fatal(err)
	}
	if err := dataStore.SaveAgentFile(ctx, agent.ID, user.ID, "MEMORY.md", []byte("remember me")); err != nil {
		t.Fatal(err)
	}
	apiKey := &APIKeyRecord{
		ID:        "key-1",
		UserID:    user.ID,
		Name:      "integration",
		KeyHash:   "hashed-token",
		KeyPrefix: "fc_example",
		CreatedAt: time.Now().UTC(),
	}
	if err := dataStore.CreateAPIKey(ctx, apiKey); err != nil {
		t.Fatal(err)
	}
	if err := dataStore.SetAPIKeyAgents(ctx, apiKey.ID, []string{agent.ID}); err != nil {
		t.Fatal(err)
	}

	if err := dataStore.Close(); err != nil {
		t.Fatal(err)
	}
	reopened, err := New(&StorageConfig{
		Type:        StorageSQLite,
		DSN:         dsn,
		AutoMigrate: false,
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := reopened.Close(); err != nil {
			t.Error(err)
		}
	})

	session, err := reopened.GetSession(ctx, user.ID, agent.ID, "web_case")
	if err != nil || len(session.Messages) != 1 || session.Messages[0].Content != "persist me" {
		t.Fatalf("reopened session=%+v err=%v", session, err)
	}
	file, err := reopened.GetAgentFile(ctx, agent.ID, user.ID, "MEMORY.md")
	if err != nil || string(file) != "remember me" {
		t.Fatalf("reopened file=%q err=%v", file, err)
	}
	allowed, err := reopened.APIKeyCanAccessAgent(ctx, apiKey.ID, agent.ID)
	if err != nil || !allowed {
		t.Fatalf("reopened API key ACL=%v err=%v", allowed, err)
	}

	if err := reopened.DeleteUser(ctx, user.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := reopened.GetAgent(ctx, agent.ID); !errors.Is(err, ErrNotFound) {
		t.Fatalf("agent survived user cascade: %v", err)
	}
	if _, err := reopened.GetSession(ctx, user.ID, agent.ID, "web_case"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("session survived user cascade: %v", err)
	}
	if _, err := reopened.LookupAPIKeyByHash(ctx, apiKey.KeyHash); !errors.Is(err, ErrNotFound) {
		t.Fatalf("API key survived user cascade: %v", err)
	}
}
