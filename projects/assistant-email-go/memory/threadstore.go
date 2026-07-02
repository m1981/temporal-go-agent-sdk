// Package memory persists per-thread state in SQLite.
//
// Why SQLite: zero-ops (single file), transactional writes safe under
// mid-run kills, trivial to migrate to Postgres later. Uses the pure-Go
// modernc.org/sqlite driver so builds stay CGO-free.
//
// Schema and semantics are a 1:1 port of the Python ThreadStore — including
// the load-bearing detail that notified_utc is preserved across upserts, so
// alert de-duplication survives repeated runs.
package memory

import (
	"database/sql"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	_ "modernc.org/sqlite"

	"github.com/m1981/temporal-go-agent-sdk/projects/assistant-email-go/domain"
)

const schema = `
CREATE TABLE IF NOT EXISTS threads (
    thread_id       TEXT PRIMARY KEY,
    subject         TEXT NOT NULL,
    sender          TEXT NOT NULL,
    last_seen_utc   TEXT NOT NULL,
    last_priority   TEXT NOT NULL,
    notified_utc    TEXT
);
CREATE INDEX IF NOT EXISTS ix_threads_last_seen ON threads(last_seen_utc);
`

// ThreadRecord is one row in the threads table.
type ThreadRecord struct {
	ThreadID     string
	Subject      string
	Sender       string
	LastSeenUTC  time.Time
	LastPriority domain.Priority
	NotifiedUTC  *time.Time // nil = never notified
}

// ThreadStore is the persistent record of every thread the assistant has processed.
type ThreadStore struct {
	mu sync.Mutex
	db *sql.DB
}

// Open creates parent directories, opens (or creates) the database, and
// applies the schema.
func Open(path string) (*ThreadStore, error) {
	if dir := filepath.Dir(path); dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return nil, fmt.Errorf("threadstore: create dir: %w", err)
		}
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("threadstore: open: %w", err)
	}
	// A single connection serializes writes; ample for the 2-hourly digest.
	db.SetMaxOpenConns(1)
	if _, err := db.Exec(schema); err != nil {
		db.Close()
		return nil, fmt.Errorf("threadstore: apply schema: %w", err)
	}
	return &ThreadStore{db: db}, nil
}

func (s *ThreadStore) Close() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.db.Close()
}

// Upsert inserts or updates a thread. notified_utc is preserved when the
// incoming record does not set it.
func (s *ThreadStore) Upsert(rec ThreadRecord) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	var notified any
	if rec.NotifiedUTC != nil {
		notified = iso(*rec.NotifiedUTC)
	}
	_, err := s.db.Exec(`
        INSERT INTO threads
            (thread_id, subject, sender, last_seen_utc, last_priority, notified_utc)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(thread_id) DO UPDATE SET
            subject        = excluded.subject,
            sender         = excluded.sender,
            last_seen_utc  = excluded.last_seen_utc,
            last_priority  = excluded.last_priority,
            notified_utc   = COALESCE(excluded.notified_utc, threads.notified_utc)`,
		rec.ThreadID, rec.Subject, rec.Sender, iso(rec.LastSeenUTC), string(rec.LastPriority), notified,
	)
	if err != nil {
		return fmt.Errorf("threadstore: upsert %s: %w", rec.ThreadID, err)
	}
	return nil
}

// Get returns the record for a thread, or (nil, nil) when unknown.
func (s *ThreadStore) Get(threadID string) (*ThreadRecord, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	row := s.db.QueryRow(
		`SELECT thread_id, subject, sender, last_seen_utc, last_priority, notified_utc
         FROM threads WHERE thread_id = ?`, threadID)

	var rec ThreadRecord
	var lastSeen string
	var priority string
	var notified sql.NullString
	err := row.Scan(&rec.ThreadID, &rec.Subject, &rec.Sender, &lastSeen, &priority, &notified)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("threadstore: get %s: %w", threadID, err)
	}
	if rec.LastSeenUTC, err = parseISO(lastSeen); err != nil {
		return nil, fmt.Errorf("threadstore: get %s: %w", threadID, err)
	}
	rec.LastPriority = domain.Priority(priority)
	if notified.Valid {
		t, err := parseISO(notified.String)
		if err != nil {
			return nil, fmt.Errorf("threadstore: get %s: %w", threadID, err)
		}
		rec.NotifiedUTC = &t
	}
	return &rec, nil
}

// KnownIDs returns the full set of thread IDs the store has ever seen.
func (s *ThreadStore) KnownIDs() (map[string]bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rows, err := s.db.Query(`SELECT thread_id FROM threads`)
	if err != nil {
		return nil, fmt.Errorf("threadstore: known ids: %w", err)
	}
	defer rows.Close()
	ids := make(map[string]bool)
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			return nil, fmt.Errorf("threadstore: known ids: %w", err)
		}
		ids[id] = true
	}
	return ids, rows.Err()
}

// MarkNotified records that the user has been alerted about a thread.
// A zero when means "now".
func (s *ThreadStore) MarkNotified(threadID string, when time.Time) error {
	if when.IsZero() {
		when = time.Now().UTC()
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	_, err := s.db.Exec(`UPDATE threads SET notified_utc = ? WHERE thread_id = ?`, iso(when), threadID)
	if err != nil {
		return fmt.Errorf("threadstore: mark notified %s: %w", threadID, err)
	}
	return nil
}

func iso(t time.Time) string { return t.UTC().Format(time.RFC3339Nano) }

func parseISO(s string) (time.Time, error) { return time.Parse(time.RFC3339Nano, s) }
