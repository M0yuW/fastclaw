package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"sync"
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

func TestIntegrationSQLiteBusyWriterWaits(t *testing.T) {
	path := filepath.Join(t.TempDir(), "busy.db")
	controlDSN := "file:" + path +
		"?_pragma=journal_mode(WAL)&_pragma=foreign_keys(1)&_pragma=busy_timeout(0)&_txlock=immediate"
	controlWriter, err := sql.Open("sqlite", controlDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer controlWriter.Close()
	controlContender, err := sql.Open("sqlite", controlDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer controlContender.Close()
	controlWriter.SetMaxOpenConns(1)
	controlContender.SetMaxOpenConns(1)
	if _, err := controlWriter.Exec(`CREATE TABLE busy_probe (id INTEGER PRIMARY KEY)`); err != nil {
		t.Fatal(err)
	}
	transaction, err := controlWriter.Begin()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := transaction.Exec(`INSERT INTO busy_probe (id) VALUES (1)`); err != nil {
		t.Fatal(err)
	}
	if _, err := controlContender.Exec(`INSERT INTO busy_probe (id) VALUES (2)`); err == nil ||
		!strings.Contains(strings.ToLower(err.Error()), "locked") {
		t.Fatalf("zero-timeout control write error = %v, want locked", err)
	}
	if err := transaction.Rollback(); err != nil {
		t.Fatal(err)
	}
	if err := controlWriter.Close(); err != nil {
		t.Fatal(err)
	}
	if err := controlContender.Close(); err != nil {
		t.Fatal(err)
	}

	normalizedDSN, err := sqliteDSNWithDefaults("file:" + path)
	if err != nil {
		t.Fatal(err)
	}
	waitingWriter, err := sql.Open("sqlite", normalizedDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer waitingWriter.Close()
	waitingContender, err := sql.Open("sqlite", normalizedDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer waitingContender.Close()
	waitingWriter.SetMaxOpenConns(1)
	waitingContender.SetMaxOpenConns(1)
	transaction, err = waitingWriter.Begin()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := transaction.Exec(`INSERT INTO busy_probe (id) VALUES (1)`); err != nil {
		t.Fatal(err)
	}
	writeDone := make(chan error, 1)
	go func() {
		_, writeErr := waitingContender.Exec(`INSERT INTO busy_probe (id) VALUES (2)`)
		writeDone <- writeErr
	}()
	time.Sleep(50 * time.Millisecond)
	if err := transaction.Commit(); err != nil {
		t.Fatal(err)
	}
	select {
	case writeErr := <-writeDone:
		if writeErr != nil {
			t.Fatalf("concurrent SQLite writer did not wait: %v", writeErr)
		}
	case <-time.After(time.Second):
		t.Fatal("concurrent SQLite writer did not resume")
	}
}

func TestSQLiteDSNWithDefaults(t *testing.T) {
	tests := []struct {
		name    string
		dsn     string
		want    []string
		notWant []string
	}{
		{
			name: "path text does not suppress timeout",
			dsn:  "file:/tmp/busy_timeout.db",
			want: []string{"_pragma=busy_timeout(5000)", "_pragma=journal_mode(WAL)", "_pragma=foreign_keys(1)", "_txlock=immediate"},
		},
		{
			name:    "encoded explicit pragmas are preserved",
			dsn:     "file:test.db?_pragma=busy_timeout%28123%29&_pragma=journal_mode%28DELETE%29&_pragma=foreign_keys%280%29&_txlock=deferred",
			notWant: []string{"busy_timeout(5000)", "journal_mode(WAL)", "foreign_keys(1)", "_txlock=immediate"},
		},
		{
			name: "ignored legacy aliases receive real pragmas",
			dsn:  "file:test.db?_journal=DELETE&_fk=0",
			want: []string{
				"_pragma=journal_mode(WAL)",
				"_pragma=foreign_keys(1)",
				"_pragma=busy_timeout(5000)",
				"_txlock=immediate",
			},
		},
		{
			name: "existing query receives ampersand",
			dsn:  "file:test.db?cache=shared",
			want: []string{"cache=shared&_pragma=journal_mode(WAL)"},
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			got, err := sqliteDSNWithDefaults(test.dsn)
			if err != nil {
				t.Fatal(err)
			}
			for _, value := range test.want {
				if !strings.Contains(got, value) {
					t.Fatalf("DSN %q does not contain %q", got, value)
				}
			}
			for _, value := range test.notWant {
				if strings.Contains(got, value) {
					t.Fatalf("DSN %q unexpectedly contains %q", got, value)
				}
			}
		})
	}
}

func TestIntegrationSQLiteImmediateTransactionsAvoidBusySnapshot(t *testing.T) {
	controlPath := filepath.Join(t.TempDir(), "deferred.db")
	controlDSN := "file:" + controlPath +
		"?_pragma=journal_mode(WAL)&_pragma=foreign_keys(1)&_pragma=busy_timeout(5000)"
	controlReader, err := sql.Open("sqlite", controlDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer controlReader.Close()
	controlWriter, err := sql.Open("sqlite", controlDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer controlWriter.Close()
	if _, err := controlReader.Exec(`CREATE TABLE snapshot_probe (id INTEGER PRIMARY KEY)`); err != nil {
		t.Fatal(err)
	}
	controlTx, err := controlReader.Begin()
	if err != nil {
		t.Fatal(err)
	}
	var count int
	if err := controlTx.QueryRow(`SELECT COUNT(*) FROM snapshot_probe`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	if _, err := controlWriter.Exec(`INSERT INTO snapshot_probe (id) VALUES (1)`); err != nil {
		t.Fatal(err)
	}
	startedAt := time.Now()
	_, controlErr := controlTx.Exec(`DELETE FROM snapshot_probe WHERE id = 1`)
	if controlErr == nil || !strings.Contains(strings.ToLower(controlErr.Error()), "locked") {
		t.Fatalf("deferred read-to-write control error = %v, want locked", controlErr)
	}
	if elapsed := time.Since(startedAt); elapsed > time.Second {
		t.Fatalf("busy snapshot unexpectedly waited %s", elapsed)
	}
	if err := controlTx.Rollback(); err != nil {
		t.Fatal(err)
	}

	treatmentPath := filepath.Join(t.TempDir(), "immediate.db")
	treatmentDSN, err := sqliteDSNWithDefaults("file:" + treatmentPath)
	if err != nil {
		t.Fatal(err)
	}
	treatmentReader, err := sql.Open("sqlite", treatmentDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer treatmentReader.Close()
	treatmentWriter, err := sql.Open("sqlite", treatmentDSN)
	if err != nil {
		t.Fatal(err)
	}
	defer treatmentWriter.Close()
	if _, err := treatmentReader.Exec(`CREATE TABLE snapshot_probe (id INTEGER PRIMARY KEY)`); err != nil {
		t.Fatal(err)
	}
	treatmentTx, err := treatmentReader.Begin()
	if err != nil {
		t.Fatal(err)
	}
	if err := treatmentTx.QueryRow(`SELECT COUNT(*) FROM snapshot_probe`).Scan(&count); err != nil {
		t.Fatal(err)
	}
	writeDone := make(chan error, 1)
	go func() {
		_, writeErr := treatmentWriter.Exec(`INSERT INTO snapshot_probe (id) VALUES (1)`)
		writeDone <- writeErr
	}()
	time.Sleep(50 * time.Millisecond)
	if _, err := treatmentTx.Exec(`INSERT INTO snapshot_probe (id) VALUES (2)`); err != nil {
		t.Fatalf("immediate read-to-write transaction failed: %v", err)
	}
	if err := treatmentTx.Commit(); err != nil {
		t.Fatal(err)
	}
	select {
	case writeErr := <-writeDone:
		if writeErr != nil {
			t.Fatalf("waiting treatment writer failed: %v", writeErr)
		}
	case <-time.After(time.Second):
		t.Fatal("waiting treatment writer did not resume")
	}
}

func TestIntegrationSQLitePublicStoreConcurrentWrites(t *testing.T) {
	ctx := context.Background()
	dataStore, err := New(&StorageConfig{
		Type:        StorageSQLite,
		DSN:         "file:" + filepath.Join(t.TempDir(), "public-api.db"),
		AutoMigrate: true,
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := dataStore.Close(); err != nil {
			t.Error(err)
		}
	})

	const workers = 12
	for index := 0; index < workers; index++ {
		userID := fmt.Sprintf("user-%02d", index)
		agentID := fmt.Sprintf("agent-%02d", index)
		if err := dataStore.CreateUser(ctx, &UserRecord{
			ID:           userID,
			Username:     userID,
			Email:        userID + "@example.com",
			PasswordHash: "hash",
			Role:         "user",
			Status:       "active",
		}); err != nil {
			t.Fatal(err)
		}
		if err := dataStore.SaveAgent(ctx, &AgentRecord{ID: agentID, UserID: userID, Name: agentID}); err != nil {
			t.Fatal(err)
		}
	}

	start := make(chan struct{})
	errorsByWorker := make(chan error, workers)
	var waitGroup sync.WaitGroup
	for index := 0; index < workers; index++ {
		index := index
		waitGroup.Add(1)
		go func() {
			defer waitGroup.Done()
			<-start
			userID := fmt.Sprintf("user-%02d", index)
			agentID := fmt.Sprintf("agent-%02d", index)
			if err := dataStore.SaveSession(ctx, userID, agentID, "concurrent", &SessionRecord{
				Messages: []SessionMessage{{Role: "user", Content: "probe"}},
			}); err != nil {
				errorsByWorker <- fmt.Errorf("save session %s: %w", userID, err)
				return
			}
			if err := dataStore.SaveAgentFile(ctx, agentID, userID, "MEMORY.md", []byte("probe")); err != nil {
				errorsByWorker <- fmt.Errorf("save file %s: %w", userID, err)
				return
			}
			if err := dataStore.DeleteUser(ctx, userID); err != nil {
				errorsByWorker <- fmt.Errorf("delete user %s: %w", userID, err)
			}
		}()
	}
	close(start)
	waitGroup.Wait()
	close(errorsByWorker)
	for err := range errorsByWorker {
		t.Error(err)
	}
}

func TestDefaultSQLitePragmas(t *testing.T) {
	dataStore, err := New(&StorageConfig{
		Type: StorageSQLite,
		DSN:  "file:" + filepath.Join(t.TempDir(), "custom.db"),
	}, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := dataStore.Close(); err != nil {
			t.Error(err)
		}
	})
	dbStore := dataStore.(*DBStore)
	var journalMode string
	var foreignKeys int
	var busyTimeout int
	if err := dbStore.db.QueryRow(`PRAGMA journal_mode`).Scan(&journalMode); err != nil {
		t.Fatal(err)
	}
	if err := dbStore.db.QueryRow(`PRAGMA foreign_keys`).Scan(&foreignKeys); err != nil {
		t.Fatal(err)
	}
	if err := dbStore.db.QueryRow(`PRAGMA busy_timeout`).Scan(&busyTimeout); err != nil {
		t.Fatal(err)
	}
	if journalMode != "wal" || foreignKeys != 1 || busyTimeout != 5000 {
		t.Fatalf(
			"SQLite pragmas journal=%q foreign_keys=%d busy_timeout=%d",
			journalMode,
			foreignKeys,
			busyTimeout,
		)
	}
}
